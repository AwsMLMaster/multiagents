"""
Saved Searches & Alerts for USA Property Finder Assistant.

Lets a buyer save a set of search criteria and be notified when new
matching listings appear.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SavedSearch:
    """A buyer's saved search criteria with alert preferences."""
    search_id: str
    user_id: str
    name: str
    filters: Dict[str, Any]
    alerts_enabled: bool = True
    alert_frequency: str = "instant"  # instant, daily, weekly
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_notified_at: Optional[datetime] = None
    last_result_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "search_id": self.search_id,
            "user_id": self.user_id,
            "name": self.name,
            "filters": self.filters,
            "alerts_enabled": self.alerts_enabled,
            "alert_frequency": self.alert_frequency,
            "created_at": self.created_at.isoformat(),
            "last_notified_at": self.last_notified_at.isoformat() if self.last_notified_at else None,
            "last_result_count": self.last_result_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SavedSearch":
        return cls(
            search_id=data["search_id"],
            user_id=data["user_id"],
            name=data["name"],
            filters=data.get("filters", {}),
            alerts_enabled=data.get("alerts_enabled", True),
            alert_frequency=data.get("alert_frequency", "instant"),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_notified_at=datetime.fromisoformat(data["last_notified_at"]) if data.get("last_notified_at") else None,
            last_result_count=data.get("last_result_count", 0),
        )


class SavedSearchRepository:
    """
    Repository for saved searches, backed by DynamoDB.
    """

    def __init__(self, dynamodb_table: Optional[str] = None):
        self.dynamodb_table = dynamodb_table or "property-finder-saved-searches"
        self._client = None

    @property
    def dynamodb(self):
        if self._client is None:
            import boto3
            self._client = boto3.resource("dynamodb").Table(self.dynamodb_table)
        return self._client

    async def save(
        self,
        user_id: str,
        filters: Dict[str, Any],
        name: Optional[str] = None,
        alert_frequency: str = "instant",
    ) -> SavedSearch:
        """Save a new search."""
        import asyncio

        search = SavedSearch(
            search_id=f"search_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            name=name or self._default_name(filters),
            filters=filters,
            alert_frequency=alert_frequency,
        )

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.dynamodb.put_item(Item=search.to_dict()))
        except Exception as e:
            logger.error(f"Error saving search: {e}")

        return search

    async def list_for_user(self, user_id: str) -> List[SavedSearch]:
        """List all saved searches for a user."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.dynamodb.scan(
                    FilterExpression="user_id = :uid",
                    ExpressionAttributeValues={":uid": user_id},
                )
            )
            return [SavedSearch.from_dict(item) for item in response.get("Items", [])]
        except Exception as e:
            logger.error(f"Error listing saved searches for {user_id}: {e}")
            return []

    async def delete(self, search_id: str) -> bool:
        """Delete a saved search."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.dynamodb.delete_item(Key={"search_id": search_id})
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting saved search {search_id}: {e}")
            return False

    def _default_name(self, filters: Dict[str, Any]) -> str:
        """Generate a human-readable default name for a saved search."""
        parts = []
        location = filters.get("location")
        if location:
            parts.append(str(location))
        if filters.get("price_max"):
            parts.append(f"under ${filters['price_max']:,.0f}")
        if filters.get("bedrooms_min"):
            parts.append(f"{filters['bedrooms_min']}+ bed")
        return " • ".join(parts) if parts else "My saved search"


def get_saved_search_repository() -> SavedSearchRepository:
    """Factory for the saved search repository."""
    return SavedSearchRepository()
