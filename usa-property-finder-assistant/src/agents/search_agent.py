"""
Search Agent for USA Property Finder Assistant.

Handles property search requests: resolves the location, applies filters,
queries the property data provider, and summarizes results.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .base_agent import BaseAgent, AgentConfig, AgentResponse, AGENT_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


class SearchAgent(BaseAgent):
    """
    Search Agent for finding properties matching buyer criteria.
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        property_data_client=None,
        geocoding_client=None,
    ):
        super().__init__(config)
        self._property_data_client = property_data_client
        self._geocoding_client = geocoding_client

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="search_agent",
            description="Property search agent",
            tools=["search_listings", "geocode_location"],
            system_prompt=AGENT_SYSTEM_PROMPTS["search"],
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
        user_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AgentResponse:
        """
        Execute a property search based on extracted intent parameters.

        Args:
            query: User's search query text.
            intent: Intent classification result with extracted parameters.
            history: Conversation history.
            user_context: Optional buyer profile for personalization.

        Returns:
            AgentResponse with search results summary and structured data.
        """
        try:
            params = intent.get("parameters", {})
            location = params.get("location")

            # Fall back to buyer's preferred locations if no location given
            if not location and user_context:
                preferred = user_context.get("preferred_locations") or []
                if preferred:
                    location = preferred[0]

            if not location:
                return AgentResponse(
                    content=(
                        "I'd be happy to search for properties - what city, ZIP "
                        "code, or neighborhood are you interested in?"
                    ),
                    success=True,
                    needs_followup=True,
                )

            price_min = params.get("price_min")
            price_max = params.get("price_max")
            bedrooms_min = params.get("bedrooms_min")
            bathrooms_min = params.get("bathrooms_min")
            property_types = params.get("property_types") or []
            min_sqft = params.get("min_sqft")

            # Apply buyer profile defaults for anything not specified this turn
            if user_context:
                price_max = price_max or user_context.get("budget_max")
                price_min = price_min or user_context.get("budget_min")
                bedrooms_min = bedrooms_min or user_context.get("min_bedrooms")

            results = await self.property_data_client.search(
                location=location,
                price_min=price_min,
                price_max=price_max,
                bedrooms_min=bedrooms_min,
                bathrooms_min=bathrooms_min,
                property_types=property_types,
                min_sqft=min_sqft,
                max_results=20,
            )

            filters_used = {
                "location": location,
                "price_min": price_min,
                "price_max": price_max,
                "bedrooms_min": bedrooms_min,
                "bathrooms_min": bathrooms_min,
                "property_types": property_types,
                "min_sqft": min_sqft,
            }

            if not results:
                return AgentResponse(
                    content=(
                        f"I couldn't find any active listings in {location} matching "
                        "those criteria. Want me to broaden the price range or search "
                        "a wider area?"
                    ),
                    tools_used=["search_listings"],
                    data={"filters": filters_used, "results": []},
                    success=True,
                )

            content = self._summarize_results(location, results)

            return AgentResponse(
                content=content,
                tools_used=["search_listings"],
                data={
                    "filters": filters_used,
                    "results": [r.to_summary() for r in results],
                    "result_count": len(results),
                },
                success=True,
            )

        except Exception as e:
            return self._build_error_response(
                str(e),
                "Sorry, I ran into a problem searching for properties. Please try again.",
            )

    def _summarize_results(self, location: str, results: List) -> str:
        """Build a human-readable summary of search results."""
        lines = [f"I found {len(results)} listing(s) in {location}:\n"]

        for i, prop in enumerate(results[:10], 1):
            price = f"${prop.list_price:,.0f}" if prop.list_price else "Price N/A"
            beds = f"{prop.bedrooms} bd" if prop.bedrooms is not None else ""
            baths = f"{prop.bathrooms} ba" if prop.bathrooms is not None else ""
            sqft = f"{prop.sqft:,} sqft" if prop.sqft else ""
            specs = " • ".join(filter(None, [beds, baths, sqft]))

            lines.append(
                f"{i}. {prop.address}, {prop.city}, {prop.state} {prop.zip_code} - "
                f"{price}" + (f" ({specs})" if specs else "")
            )

        if len(results) > 10:
            lines.append(f"\n...and {len(results) - 10} more. Want me to narrow it down?")

        return "\n".join(lines)

    async def refine(
        self,
        active_filters: Dict[str, Any],
        refinements: Dict[str, Any],
    ) -> AgentResponse:
        """Refine an existing search with additional filter criteria."""
        try:
            merged = {**active_filters, **{k: v for k, v in refinements.items() if v is not None}}

            results = await self.property_data_client.search(
                location=merged.get("location"),
                price_min=merged.get("price_min"),
                price_max=merged.get("price_max"),
                bedrooms_min=merged.get("bedrooms_min"),
                bathrooms_min=merged.get("bathrooms_min"),
                property_types=merged.get("property_types") or [],
                min_sqft=merged.get("min_sqft"),
                sort_by=merged.get("sort_by", "relevance"),
                max_results=20,
            )

            content = self._summarize_results(merged.get("location", "your area"), results)

            return AgentResponse(
                content=content,
                tools_used=["refine_search"],
                data={
                    "filters": merged,
                    "results": [r.to_summary() for r in results],
                    "result_count": len(results),
                },
                success=True,
            )
        except Exception as e:
            return self._build_error_response(str(e), "Sorry, I couldn't refine that search.")
