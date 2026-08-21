"""
Scheduling Agent for USA Property Finder Assistant.

Handles scheduling property tours (in-person or virtual) and connecting
buyers with listing agents.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .base_agent import BaseAgent, AgentConfig, AgentResponse, AGENT_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


class SchedulingAgent(BaseAgent):
    """
    Agent for scheduling property tours and agent contact requests.

    Note: this scaffold does not integrate with a live scheduling/CRM backend.
    It models the request/confirmation flow and returns a structured booking
    record that a real integration (e.g., a showing-management API or CRM
    webhook) would consume downstream.
    """

    def __init__(self, config: Optional[AgentConfig] = None, property_data_client=None):
        super().__init__(config)
        self._property_data_client = property_data_client

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="scheduling_agent",
            description="Property tour scheduling and agent contact agent",
            tools=["schedule_tour", "contact_listing_agent"],
            system_prompt=AGENT_SYSTEM_PROMPTS["scheduling"],
        )

    @property
    def property_data_client(self):
        if self._property_data_client is None:
            from ..integrations.property_data_api import create_property_data_client
            from config.settings import get_settings
            settings = get_settings()
            self._property_data_client = create_property_data_client(
                provider=settings.property_data.provider,
                base_url=settings.property_data.base_url,
                api_key=settings.property_data.api_key,
            )
        return self._property_data_client

    async def execute(
        self,
        query: str,
        intent: Dict[str, Any],
        history: Optional[List[BaseMessage]] = None,
        focused_property_id: Optional[str] = None,
        **kwargs,
    ) -> AgentResponse:
        """Route to tour scheduling or agent contact request."""
        try:
            intent_id = intent.get("intent_id", "")
            params = intent.get("parameters", {})
            property_id = params.get("property_id") or focused_property_id

            if not property_id:
                return AgentResponse(
                    content="Which property would you like to schedule?",
                    success=True,
                    needs_followup=True,
                )

            if intent_id == "scheduling.contact_agent":
                return await self._contact_agent(property_id)

            return await self._schedule_tour(property_id, params)

        except Exception as e:
            return self._build_error_response(
                str(e), "Sorry, I couldn't complete that scheduling request."
            )

    async def _schedule_tour(self, property_id: str, params: Dict[str, Any]) -> AgentResponse:
        prop = await self.property_data_client.get_details(property_id)
        if not prop:
            return AgentResponse(
                content="I couldn't find that property to schedule a tour.",
                tools_used=["schedule_tour"],
                success=True,
            )

        preferred_date = params.get("preferred_date")
        preferred_time = params.get("preferred_time")
        tour_type = params.get("tour_type", "in_person")

        if not preferred_date:
            return AgentResponse(
                content=(
                    f"What date works for touring {prop.address}? "
                    "(You can also ask for a virtual tour.)"
                ),
                success=True,
                needs_followup=True,
            )

        confirmation_id = f"tour_{uuid.uuid4().hex[:8]}"

        content = (
            f"Tour request submitted for {prop.address} on {preferred_date}"
            + (f" at {preferred_time}" if preferred_time else "")
            + f" ({tour_type.replace('_', ' ')}).\n\n"
            f"Confirmation ID: {confirmation_id}. The listing agent will confirm "
            "availability shortly."
        )

        return AgentResponse(
            content=content,
            tools_used=["schedule_tour"],
            data={
                "confirmation_id": confirmation_id,
                "property_id": property_id,
                "preferred_date": preferred_date,
                "preferred_time": preferred_time,
                "tour_type": tour_type,
                "status": "pending_confirmation",
                "requested_at": datetime.utcnow().isoformat(),
            },
            success=True,
        )

    async def _contact_agent(self, property_id: str) -> AgentResponse:
        prop = await self.property_data_client.get_details(property_id)
        if not prop:
            return AgentResponse(
                content="I couldn't find that property to connect you with an agent.",
                tools_used=["contact_listing_agent"],
                success=True,
            )

        agent_info = prop.listing_agent or {}
        agent_name = agent_info.get("name", "the listing agent")

        content = (
            f"I've forwarded your interest in {prop.address} to {agent_name}. "
            "They'll typically follow up within one business day."
        )

        return AgentResponse(
            content=content,
            tools_used=["contact_listing_agent"],
            data={
                "property_id": property_id,
                "listing_agent": agent_info,
                "status": "request_sent",
            },
            success=True,
        )
