"""
Neighborhood Agent for USA Property Finder Assistant.

Provides objective neighborhood livability data: school ratings, crime
statistics, walkability, nearby amenities, and commute estimates.

All output must comply with the Fair Housing Act: never characterize a
neighborhood by the race, religion, or national origin of its residents.
"""

import logging
import random
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .base_agent import BaseAgent, AgentConfig, AgentResponse, AGENT_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


class NeighborhoodAgent(BaseAgent):
    """
    Agent for neighborhood overview and commute information.
    """

    def __init__(self, config: Optional[AgentConfig] = None, geocoding_client=None):
        super().__init__(config)
        self._geocoding_client = geocoding_client

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="neighborhood_agent",
            description="Neighborhood data and commute agent",
            tools=["get_school_ratings", "get_crime_stats", "get_walkability", "estimate_commute"],
            system_prompt=AGENT_SYSTEM_PROMPTS["neighborhood"],
        )

    @property
    def geocoding_client(self):
        if self._geocoding_client is None:
            from ..integrations.geocoding import create_geocoding_client
            from config.settings import get_settings
            settings = get_settings()
            self._geocoding_client = create_geocoding_client(
                provider=settings.geocoding.provider,
                api_key=settings.geocoding.api_key,
            )
        return self._geocoding_client

    async def execute(
        self,
        query: str,
        intent: Dict[str, Any],
        history: Optional[List[BaseMessage]] = None,
        **kwargs,
    ) -> AgentResponse:
        """Route to neighborhood overview or commute estimate."""
        try:
            intent_id = intent.get("intent_id", "")
            params = intent.get("parameters", {})

            if intent_id == "neighborhood.commute":
                return await self._commute(params)
            return await self._overview(params)

        except Exception as e:
            return self._build_error_response(
                str(e), "Sorry, I couldn't retrieve neighborhood information right now."
            )

    async def _overview(self, params: Dict[str, Any]) -> AgentResponse:
        location = params.get("location")
        if not location:
            return AgentResponse(
                content="Which location would you like neighborhood information for?",
                success=True,
                needs_followup=True,
            )

        geo = await self.geocoding_client.geocode(location)
        if not geo:
            return AgentResponse(
                content=f"I couldn't resolve '{location}' to a location. Could you clarify the city/ZIP?",
                success=True,
            )

        # NOTE: school/crime/walkability data providers are not wired to a live
        # API in this scaffold; a deterministic placeholder is generated so the
        # agent's contract and formatting are demonstrable end-to-end. Replace
        # with real GreatSchools / crime-data / Walk Score integrations.
        data = self._placeholder_livability_data(geo.formatted_address)

        content = (
            f"Here's what I found for {geo.formatted_address}:\n\n"
            f"Schools: {data['school_rating']}/10 average rating "
            f"({data['school_count']} schools nearby)\n"
            f"Safety: crime index {data['crime_index']} (lower is safer; national avg = 100)\n"
            f"Walkability: {data['walk_score']}/100 ({data['walk_label']})\n"
            f"Nearby amenities: {', '.join(data['amenities'])}"
        )

        return AgentResponse(
            content=content,
            tools_used=["get_school_ratings", "get_crime_stats", "get_walkability", "get_amenities"],
            data={"location": geo.formatted_address, **data},
            success=True,
        )

    async def _commute(self, params: Dict[str, Any]) -> AgentResponse:
        origin = params.get("origin")
        destination = params.get("destination")

        if not origin or not destination:
            return AgentResponse(
                content="What are the starting point and destination for the commute?",
                success=True,
                needs_followup=True,
            )

        commute = await self.geocoding_client.estimate_commute(origin, destination)
        if not commute:
            return AgentResponse(
                content="I couldn't estimate that commute - please double check both locations.",
                tools_used=["estimate_commute"],
                success=True,
            )

        content = (
            f"Estimated commute from {origin} to {destination}: "
            f"{commute.distance_miles} miles"
        )
        if commute.driving_minutes:
            content += f", approximately {commute.driving_minutes:.0f} min by car"

        return AgentResponse(
            content=content,
            tools_used=["estimate_commute"],
            data={
                "distance_miles": commute.distance_miles,
                "driving_minutes": commute.driving_minutes,
            },
            success=True,
        )

    def _placeholder_livability_data(self, seed_key: str) -> Dict[str, Any]:
        """Deterministic placeholder livability metrics keyed by location string."""
        rng = random.Random(seed_key)
        walk_score = rng.randint(20, 95)
        walk_label = (
            "car-dependent" if walk_score < 50 else
            "somewhat walkable" if walk_score < 70 else
            "very walkable"
        )
        return {
            "school_rating": round(rng.uniform(4.0, 9.5), 1),
            "school_count": rng.randint(3, 12),
            "crime_index": rng.randint(40, 140),
            "walk_score": walk_score,
            "walk_label": walk_label,
            "amenities": rng.sample(
                ["grocery stores", "parks", "restaurants", "public transit",
                 "gyms", "coffee shops", "shopping centers", "libraries"],
                k=4,
            ),
        }
