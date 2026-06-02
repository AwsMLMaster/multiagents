"""
Session Health Monitor

Detects and recovers unresponsive AgentCore sessions.

A session is considered unresponsive when:
- No heartbeat received within `heartbeat_timeout` seconds
- An invoke_agent call times out
- The session is explicitly marked unhealthy

Recovery: the monitor terminates the stale session and creates a fresh one,
preserving the user_id so the caller can resume transparently.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class SessionStatus(str, Enum):
    ACTIVE = "active"
    STALE = "stale"          # No heartbeat within threshold
    UNRESPONSIVE = "unresponsive"  # Timed-out on invoke
    RECOVERING = "recovering"
    TERMINATED = "terminated"


@dataclass
class SessionHealth:
    session_id: str
    user_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    invoke_timeouts: int = 0
    total_invocations: int = 0
    recovered_at: Optional[datetime] = None
    replacement_session_id: Optional[str] = None

    def age_seconds(self) -> float:
        return (datetime.utcnow() - self.created_at).total_seconds()

    def seconds_since_heartbeat(self) -> float:
        return (datetime.utcnow() - self.last_heartbeat).total_seconds()

    def is_healthy(self) -> bool:
        return self.status == SessionStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "age_seconds": round(self.age_seconds(), 1),
            "seconds_since_heartbeat": round(self.seconds_since_heartbeat(), 1),
            "invoke_timeouts": self.invoke_timeouts,
            "total_invocations": self.total_invocations,
            "recovered_at": self.recovered_at.isoformat() if self.recovered_at else None,
            "replacement_session_id": self.replacement_session_id,
        }


class SessionHealthMonitor:
    """
    Monitors AgentCore sessions for responsiveness.

    Usage:
        monitor = SessionHealthMonitor(agentcore_client)
        await monitor.start()

        # Register a session after creation
        monitor.register(session_id, user_id)

        # Record activity
        monitor.heartbeat(session_id)

        # Mark a session unresponsive after a timeout
        monitor.mark_unresponsive(session_id)

        # Get a health snapshot
        health = monitor.get_health(session_id)

        # Recover a session
        new_session_id = await monitor.recover(session_id)

        await monitor.stop()
    """

    def __init__(
        self,
        agentcore_client: Any,
        heartbeat_timeout: float = 120.0,   # seconds before stale
        check_interval: float = 30.0,       # how often to scan
        max_session_age: float = 3600.0,    # 1 hour max lifetime
        on_recovery: Optional[Callable[[str, str], None]] = None,
    ):
        self._client = agentcore_client
        self._heartbeat_timeout = heartbeat_timeout
        self._check_interval = check_interval
        self._max_session_age = max_session_age
        self._on_recovery = on_recovery  # callback(old_id, new_id)

        self._sessions: Dict[str, SessionHealth] = {}
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background health-check loop."""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._scan_loop(), name="session-health-monitor")
        logger.info("SessionHealthMonitor started")

    async def stop(self) -> None:
        """Stop the background loop."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SessionHealthMonitor stopped")

    # ── Registration ─────────────────────────────────────────────────────────

    def register(self, session_id: str, user_id: str) -> None:
        self._sessions[session_id] = SessionHealth(
            session_id=session_id,
            user_id=user_id,
        )
        logger.debug(f"Registered session {session_id} for user {user_id}")

    def deregister(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    # ── Activity signals ─────────────────────────────────────────────────────

    def heartbeat(self, session_id: str) -> None:
        """Call this whenever a session receives or responds to a message."""
        health = self._sessions.get(session_id)
        if health:
            health.last_heartbeat = datetime.utcnow()
            if health.status == SessionStatus.STALE:
                health.status = SessionStatus.ACTIVE

    def record_invocation(self, session_id: str, timed_out: bool = False) -> None:
        """Record the outcome of an invoke_agent call."""
        health = self._sessions.get(session_id)
        if not health:
            return
        health.total_invocations += 1
        if timed_out:
            health.invoke_timeouts += 1
            if health.invoke_timeouts >= 2:
                health.status = SessionStatus.UNRESPONSIVE
                logger.warning(
                    f"Session {session_id} marked UNRESPONSIVE "
                    f"({health.invoke_timeouts} consecutive timeouts)"
                )

    def mark_unresponsive(self, session_id: str) -> None:
        health = self._sessions.get(session_id)
        if health:
            health.status = SessionStatus.UNRESPONSIVE

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_health(self, session_id: str) -> Optional[SessionHealth]:
        return self._sessions.get(session_id)

    def all_health(self) -> Dict[str, Dict[str, Any]]:
        return {sid: h.to_dict() for sid, h in self._sessions.items()}

    def summary(self) -> Dict[str, Any]:
        statuses = [h.status for h in self._sessions.values()]
        return {
            "total": len(statuses),
            "active": statuses.count(SessionStatus.ACTIVE),
            "stale": statuses.count(SessionStatus.STALE),
            "unresponsive": statuses.count(SessionStatus.UNRESPONSIVE),
            "recovering": statuses.count(SessionStatus.RECOVERING),
            "terminated": statuses.count(SessionStatus.TERMINATED),
        }

    # ── Recovery ──────────────────────────────────────────────────────────────

    async def recover(self, session_id: str) -> Optional[str]:
        """
        Terminate the given session and create a fresh replacement.

        Returns the new session_id, or None if recovery failed.
        """
        health = self._sessions.get(session_id)
        if not health:
            return None

        async with self._lock:
            if health.status == SessionStatus.RECOVERING:
                return health.replacement_session_id

            health.status = SessionStatus.RECOVERING
            logger.info(f"Recovering session {session_id} for user {health.user_id}")

        try:
            # Best-effort termination — don't let it block recovery
            try:
                await asyncio.wait_for(
                    self._client.end_session(session_id),
                    timeout=5.0,
                )
            except Exception:
                pass

            new_session = await asyncio.wait_for(
                self._client.create_session(health.user_id),
                timeout=10.0,
            )

            async with self._lock:
                health.status = SessionStatus.TERMINATED
                health.replacement_session_id = new_session.session_id
                health.recovered_at = datetime.utcnow()

            self.register(new_session.session_id, health.user_id)
            logger.info(
                f"Session {session_id} replaced by {new_session.session_id}"
            )

            if self._on_recovery:
                try:
                    self._on_recovery(session_id, new_session.session_id)
                except Exception:
                    pass

            return new_session.session_id

        except Exception as e:
            logger.error(f"Failed to recover session {session_id}: {e}")
            async with self._lock:
                health.status = SessionStatus.UNRESPONSIVE
            return None

    # ── Background scan ───────────────────────────────────────────────────────

    async def _scan_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._check_interval)
                await self._scan_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health scan error: {e}")

    async def _scan_once(self) -> None:
        stale_ids = []
        unresponsive_ids = []

        for session_id, health in list(self._sessions.items()):
            if health.status in (SessionStatus.TERMINATED, SessionStatus.RECOVERING):
                continue

            if health.age_seconds() > self._max_session_age:
                logger.info(f"Session {session_id} exceeded max age; terminating")
                await self._client.end_session(session_id)
                health.status = SessionStatus.TERMINATED
                self.deregister(session_id)
                continue

            if health.seconds_since_heartbeat() > self._heartbeat_timeout:
                if health.status == SessionStatus.ACTIVE:
                    health.status = SessionStatus.STALE
                    stale_ids.append(session_id)
                elif health.status == SessionStatus.STALE:
                    unresponsive_ids.append(session_id)

        if stale_ids:
            logger.warning(f"Stale sessions (no heartbeat): {stale_ids}")

        for session_id in unresponsive_ids:
            logger.warning(f"Auto-recovering unresponsive session {session_id}")
            asyncio.create_task(self.recover(session_id))
