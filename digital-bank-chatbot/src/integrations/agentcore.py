"""
AWS Bedrock AgentCore Integration

AgentCore provides:
- Managed memory (short-term and long-term)
- Built-in guardrails
- API Gateway for agent invocation
- Session management
- Tool orchestration
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


class AgentCoreMemoryType(Enum):
    """Memory types supported by AgentCore."""
    SESSION = "SESSION"  # Short-term, within conversation
    SEMANTIC = "SEMANTIC"  # Long-term facts about user
    EPISODIC = "EPISODIC"  # Past interaction summaries


class AgentCoreGuardrailAction(Enum):
    """Actions taken by AgentCore guardrails."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ANONYMIZE = "ANONYMIZE"
    WARN = "WARN"


@dataclass
class AgentCoreMemoryEntry:
    """Memory entry from AgentCore."""
    memory_id: str
    memory_type: AgentCoreMemoryType
    content: Dict[str, Any]
    created_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCoreGuardrailResult:
    """Result from AgentCore guardrail check."""
    action: AgentCoreGuardrailAction
    guardrail_id: str
    matched_policies: List[str] = field(default_factory=list)
    modified_content: Optional[str] = None
    explanation: Optional[str] = None


@dataclass
class AgentCoreSession:
    """AgentCore session information."""
    session_id: str
    agent_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    memory_enabled: bool = True
    guardrails_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentCoreClient:
    """
    Client for AWS Bedrock AgentCore.

    AgentCore provides managed infrastructure for:
    - Multi-turn conversation memory
    - Guardrails enforcement
    - Session management
    - Tool execution gateway
    """

    def __init__(
        self,
        agent_id: str,
        agent_alias_id: str = "TSTALIASID",
        region: str = "us-east-1",
        guardrail_id: Optional[str] = None,
        memory_config: Optional[Dict[str, Any]] = None,
    ):
        self.agent_id = agent_id
        self.agent_alias_id = agent_alias_id
        self.region = region
        self.guardrail_id = guardrail_id
        self.memory_config = memory_config or self._default_memory_config()

        # Configure client with retries
        config = Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=5,
            read_timeout=60,
        )

        self.bedrock_agent = boto3.client(
            "bedrock-agent",
            region_name=region,
            config=config,
        )

        self.bedrock_agent_runtime = boto3.client(
            "bedrock-agent-runtime",
            region_name=region,
            config=config,
        )

        logger.info(f"AgentCore client initialized for agent {agent_id}")

    def _default_memory_config(self) -> Dict[str, Any]:
        """Default memory configuration for banking chatbot."""
        return {
            "session_memory": {
                "enabled": True,
                "max_messages": 50,
                "ttl_seconds": 3600,  # 1 hour
            },
            "semantic_memory": {
                "enabled": True,
                "max_facts": 100,
                "embedding_model": "amazon.titan-embed-text-v2:0",
            },
            "episodic_memory": {
                "enabled": True,
                "max_episodes": 50,
                "summary_model": "anthropic.claude-3-haiku-20240307-v1:0",
            },
        }

    # ==================== Session Management ====================

    async def create_session(
        self,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentCoreSession:
        """Create a new AgentCore session."""
        try:
            response = self.bedrock_agent_runtime.create_session(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionAttributes={
                    "user_id": user_id,
                    **(metadata or {}),
                },
            )

            session = AgentCoreSession(
                session_id=response["sessionId"],
                agent_id=self.agent_id,
                user_id=user_id,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                metadata=metadata or {},
            )

            logger.info(f"Created AgentCore session {session.session_id} for user {user_id}")
            return session

        except Exception as e:
            logger.error(f"Failed to create AgentCore session: {e}")
            raise

    async def get_session(self, session_id: str) -> Optional[AgentCoreSession]:
        """Retrieve existing session information."""
        try:
            response = self.bedrock_agent_runtime.get_session(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
            )

            return AgentCoreSession(
                session_id=session_id,
                agent_id=self.agent_id,
                user_id=response.get("sessionAttributes", {}).get("user_id", ""),
                created_at=response.get("createdAt", datetime.utcnow()),
                last_activity=response.get("lastUpdatedAt", datetime.utcnow()),
                metadata=response.get("sessionAttributes", {}),
            )

        except self.bedrock_agent_runtime.exceptions.ResourceNotFoundException:
            return None
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            raise

    async def end_session(self, session_id: str) -> bool:
        """End an AgentCore session."""
        try:
            self.bedrock_agent_runtime.delete_session(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
            )
            logger.info(f"Ended AgentCore session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to end session {session_id}: {e}")
            return False

    # ==================== Memory Operations ====================

    async def store_memory(
        self,
        session_id: str,
        memory_type: AgentCoreMemoryType,
        content: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> AgentCoreMemoryEntry:
        """Store a memory entry in AgentCore."""
        try:
            memory_input = {
                "memoryType": memory_type.value,
                "content": json.dumps(content),
            }

            if ttl_seconds:
                memory_input["ttlSeconds"] = ttl_seconds

            response = self.bedrock_agent_runtime.put_memory(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                memoryInput=memory_input,
            )

            entry = AgentCoreMemoryEntry(
                memory_id=response.get("memoryId", ""),
                memory_type=memory_type,
                content=content,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() if ttl_seconds else None,
            )

            logger.debug(f"Stored {memory_type.value} memory in session {session_id}")
            return entry

        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            raise

    async def retrieve_memories(
        self,
        session_id: str,
        memory_type: Optional[AgentCoreMemoryType] = None,
        query: Optional[str] = None,
        max_results: int = 10,
    ) -> List[AgentCoreMemoryEntry]:
        """Retrieve memories from AgentCore."""
        try:
            params = {
                "agentId": self.agent_id,
                "agentAliasId": self.agent_alias_id,
                "sessionId": session_id,
                "maxResults": max_results,
            }

            if memory_type:
                params["memoryType"] = memory_type.value

            if query:
                params["query"] = query

            response = self.bedrock_agent_runtime.get_memory(**params)

            memories = []
            for item in response.get("memories", []):
                memories.append(AgentCoreMemoryEntry(
                    memory_id=item.get("memoryId", ""),
                    memory_type=AgentCoreMemoryType(item.get("memoryType", "SESSION")),
                    content=json.loads(item.get("content", "{}")),
                    created_at=item.get("createdAt", datetime.utcnow()),
                    metadata=item.get("metadata", {}),
                ))

            return memories

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return []

    async def get_conversation_history(
        self,
        session_id: str,
        max_messages: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get conversation history from session memory."""
        memories = await self.retrieve_memories(
            session_id=session_id,
            memory_type=AgentCoreMemoryType.SESSION,
            max_results=max_messages,
        )

        return [m.content for m in memories if m.content.get("type") == "message"]

    async def store_user_fact(
        self,
        session_id: str,
        fact_type: str,
        subject: str,
        predicate: str,
        obj: str,
        confidence: float = 1.0,
    ) -> AgentCoreMemoryEntry:
        """Store a semantic fact about the user."""
        content = {
            "type": "fact",
            "fact_type": fact_type,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return await self.store_memory(
            session_id=session_id,
            memory_type=AgentCoreMemoryType.SEMANTIC,
            content=content,
        )

    async def store_interaction_summary(
        self,
        session_id: str,
        summary: str,
        intent: str,
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AgentCoreMemoryEntry:
        """Store an episodic memory of an interaction."""
        content = {
            "type": "episode",
            "summary": summary,
            "intent": intent,
            "outcome": outcome,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        return await self.store_memory(
            session_id=session_id,
            memory_type=AgentCoreMemoryType.EPISODIC,
            content=content,
        )

    # ==================== Guardrails ====================

    async def check_guardrails(
        self,
        content: str,
        content_type: str = "INPUT",  # INPUT or OUTPUT
        session_id: Optional[str] = None,
    ) -> AgentCoreGuardrailResult:
        """Check content against AgentCore guardrails."""
        if not self.guardrail_id:
            return AgentCoreGuardrailResult(
                action=AgentCoreGuardrailAction.ALLOW,
                guardrail_id="none",
            )

        try:
            response = self.bedrock_agent_runtime.apply_guardrail(
                guardrailIdentifier=self.guardrail_id,
                guardrailVersion="DRAFT",
                source=content_type,
                content=[{"text": {"text": content}}],
            )

            action = AgentCoreGuardrailAction(
                response.get("action", "ALLOW")
            )

            matched_policies = []
            modified_content = None

            for assessment in response.get("assessments", []):
                if assessment.get("topicPolicy"):
                    for topic in assessment["topicPolicy"].get("topics", []):
                        if topic.get("action") != "ALLOW":
                            matched_policies.append(f"topic:{topic.get('name')}")

                if assessment.get("contentPolicy"):
                    for filter_result in assessment["contentPolicy"].get("filters", []):
                        if filter_result.get("action") != "ALLOW":
                            matched_policies.append(f"content:{filter_result.get('type')}")

                if assessment.get("wordPolicy"):
                    for word in assessment["wordPolicy"].get("customWords", []):
                        matched_policies.append(f"word:{word.get('match')}")

                if assessment.get("sensitiveInformationPolicy"):
                    for pii in assessment["sensitiveInformationPolicy"].get("piiEntities", []):
                        matched_policies.append(f"pii:{pii.get('type')}")

            # Get modified content if anonymized
            if action == AgentCoreGuardrailAction.ANONYMIZE:
                outputs = response.get("outputs", [])
                if outputs:
                    modified_content = outputs[0].get("text", content)

            return AgentCoreGuardrailResult(
                action=action,
                guardrail_id=self.guardrail_id,
                matched_policies=matched_policies,
                modified_content=modified_content,
            )

        except Exception as e:
            logger.error(f"Guardrail check failed: {e}")
            # Fail open with warning
            return AgentCoreGuardrailResult(
                action=AgentCoreGuardrailAction.WARN,
                guardrail_id=self.guardrail_id,
                explanation=f"Guardrail check failed: {str(e)}",
            )

    # ==================== Agent Invocation (Gateway) ====================

    async def invoke_agent(
        self,
        session_id: str,
        input_text: str,
        enable_trace: bool = True,
        end_session: bool = False,
    ) -> Dict[str, Any]:
        """
        Invoke the agent through AgentCore gateway.

        This handles:
        - Automatic memory retrieval and storage
        - Guardrail enforcement
        - Tool orchestration
        - Response streaming
        """
        try:
            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=input_text,
                enableTrace=enable_trace,
                endSession=end_session,
            )

            # Process streaming response
            completion = ""
            trace_events = []
            citations = []

            for event in response.get("completion", []):
                if "chunk" in event:
                    chunk_text = event["chunk"].get("bytes", b"").decode("utf-8")
                    completion += chunk_text

                if "trace" in event and enable_trace:
                    trace_events.append(event["trace"])

                if "citation" in event:
                    citations.append(event["citation"])

            return {
                "completion": completion,
                "session_id": session_id,
                "traces": trace_events,
                "citations": citations,
                "memory_used": True,
                "guardrails_applied": bool(self.guardrail_id),
            }

        except Exception as e:
            logger.error(f"Agent invocation failed: {e}")
            raise

    async def invoke_agent_with_tools(
        self,
        session_id: str,
        input_text: str,
        tools: List[Dict[str, Any]],
        tool_handler: callable,
    ) -> Dict[str, Any]:
        """
        Invoke agent with custom tool handling.

        AgentCore manages the tool orchestration loop.
        """
        try:
            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=input_text,
                enableTrace=True,
            )

            completion = ""
            tool_results = []

            for event in response.get("completion", []):
                if "chunk" in event:
                    completion += event["chunk"].get("bytes", b"").decode("utf-8")

                # Handle tool use requests from AgentCore
                if "returnControl" in event:
                    invocation = event["returnControl"].get("invocationInputs", [])
                    for tool_input in invocation:
                        if "functionInvocationInput" in tool_input:
                            func_input = tool_input["functionInvocationInput"]
                            tool_name = func_input.get("function", "")
                            tool_params = func_input.get("parameters", {})

                            # Execute tool via handler
                            result = await tool_handler(tool_name, tool_params)
                            tool_results.append({
                                "tool": tool_name,
                                "result": result,
                            })

            return {
                "completion": completion,
                "session_id": session_id,
                "tool_results": tool_results,
            }

        except Exception as e:
            logger.error(f"Agent invocation with tools failed: {e}")
            raise


class AgentCoreMemoryAdapter:
    """
    Adapter to use AgentCore memory with our existing memory interface.

    This allows gradual migration from custom memory to AgentCore.
    """

    def __init__(self, agentcore_client: AgentCoreClient):
        self.client = agentcore_client
        self._session_map: Dict[str, str] = {}  # user_id -> session_id

    async def get_or_create_session(self, user_id: str) -> str:
        """Get existing session or create new one."""
        if user_id in self._session_map:
            session = await self.client.get_session(self._session_map[user_id])
            if session:
                return session.session_id

        # Create new session
        session = await self.client.create_session(user_id)
        self._session_map[user_id] = session.session_id
        return session.session_id

    async def get_context_for_intent(
        self,
        user_id: str,
        intent: str,
    ) -> Dict[str, Any]:
        """Get relevant context for an intent using AgentCore memory."""
        session_id = await self.get_or_create_session(user_id)

        # Retrieve semantic memories related to intent
        semantic_memories = await self.client.retrieve_memories(
            session_id=session_id,
            memory_type=AgentCoreMemoryType.SEMANTIC,
            query=intent,
            max_results=5,
        )

        # Retrieve recent episodes
        episodic_memories = await self.client.retrieve_memories(
            session_id=session_id,
            memory_type=AgentCoreMemoryType.EPISODIC,
            max_results=3,
        )

        # Get conversation history
        history = await self.client.get_conversation_history(
            session_id=session_id,
            max_messages=10,
        )

        return {
            "facts": [m.content for m in semantic_memories],
            "episodes": [m.content for m in episodic_memories],
            "history": history,
            "session_id": session_id,
        }

    async def learn_fact(
        self,
        user_id: str,
        fact_type: str,
        subject: str,
        predicate: str,
        obj: str,
        confidence: float = 1.0,
    ) -> None:
        """Store a learned fact about the user."""
        session_id = await self.get_or_create_session(user_id)
        await self.client.store_user_fact(
            session_id=session_id,
            fact_type=fact_type,
            subject=subject,
            predicate=predicate,
            obj=obj,
            confidence=confidence,
        )

    async def record_interaction(
        self,
        user_id: str,
        summary: str,
        intent: str,
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an interaction summary."""
        session_id = await self.get_or_create_session(user_id)
        await self.client.store_interaction_summary(
            session_id=session_id,
            summary=summary,
            intent=intent,
            outcome=outcome,
            details=details,
        )


class AgentCoreGuardrailAdapter:
    """
    Adapter to use AgentCore guardrails with our existing guardrail interface.
    """

    def __init__(self, agentcore_client: AgentCoreClient):
        self.client = agentcore_client

    async def check_input(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Check input against guardrails."""
        result = await self.client.check_guardrails(
            content=text,
            content_type="INPUT",
        )

        return {
            "allowed": result.action in [
                AgentCoreGuardrailAction.ALLOW,
                AgentCoreGuardrailAction.WARN,
            ],
            "action": result.action.value,
            "matched_policies": result.matched_policies,
            "modified_content": result.modified_content,
            "explanation": result.explanation,
        }

    async def check_output(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Check output against guardrails."""
        result = await self.client.check_guardrails(
            content=text,
            content_type="OUTPUT",
        )

        return {
            "allowed": result.action in [
                AgentCoreGuardrailAction.ALLOW,
                AgentCoreGuardrailAction.WARN,
                AgentCoreGuardrailAction.ANONYMIZE,
            ],
            "action": result.action.value,
            "matched_policies": result.matched_policies,
            "modified_content": result.modified_content or text,
            "explanation": result.explanation,
        }
