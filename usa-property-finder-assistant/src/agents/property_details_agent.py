"""
Property Details Agent for USA Property Finder Assistant.

Handles requests for detailed information about a specific property: full
description, photos, price/tax history, comparisons, and favorites.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .base_agent import BaseAgent, AgentConfig, AgentResponse, AGENT_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


class PropertyDetailsAgent(BaseAgent):
    """
    Agent for retrieving and presenting detailed property information.
    """

    def __init__(self, config: Optional[AgentConfig] = None, property_data_client=None):
        super().__init__(config)
        self._property_data_client = property_data_client

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="property_details_agent",
            description="Property details, comparison, and favorites agent",
            tools=["get_property_details", "compare_properties", "save_favorite"],
            system_prompt=AGENT_SYSTEM_PROMPTS["property_details"],
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
        """
        Get details for a specific property, or resolve "that one" / "the second
        listing" references using focused_property_id from short-term memory.
        """
        try:
            intent_id = intent.get("intent_id", "")
            params = intent.get("parameters", {})
            property_id = params.get("property_id") or focused_property_id

            if intent_id == "property.compare":
                property_ids = params.get("property_ids") or []
                return await self._compare(property_ids)

            if intent_id == "property.favorite":
                if not property_id:
                    return AgentResponse(
                        content="Which property would you like me to save?",
                        success=True,
                        needs_followup=True,
                    )
                return AgentResponse(
                    content="Saved to your favorites!",
                    tools_used=["save_favorite"],
                    data={"property_id": property_id, "favorited": True},
                    success=True,
                )

            if not property_id:
                return AgentResponse(
                    content=(
                        "Which property would you like details on? You can reference "
                        "it by address or by its position in the last search results."
                    ),
                    success=True,
                    needs_followup=True,
                )

            prop = await self.property_data_client.get_details(property_id)
            if not prop:
                return AgentResponse(
                    content="I couldn't find details for that property. It may no longer be listed.",
                    tools_used=["get_property_details"],
                    success=True,
                )

            content = self._format_details(prop)

            return AgentResponse(
                content=content,
                tools_used=["get_property_details"],
                data={"property": prop.to_summary(), "focused_property_id": property_id},
                success=True,
            )

        except Exception as e:
            return self._build_error_response(
                str(e), "Sorry, I couldn't pull up those property details."
            )

    def _format_details(self, prop) -> str:
        """Format full property details for display."""
        price = f"${prop.list_price:,.0f}" if prop.list_price else "Price not listed"
        lines = [
            f"**{prop.address}, {prop.city}, {prop.state} {prop.zip_code}**",
            f"{price} • {prop.property_type.replace('_', ' ').title()}",
        ]

        specs = []
        if prop.bedrooms is not None:
            specs.append(f"{prop.bedrooms} bed")
        if prop.bathrooms is not None:
            specs.append(f"{prop.bathrooms} bath")
        if prop.sqft:
            specs.append(f"{prop.sqft:,} sqft")
        if prop.year_built:
            specs.append(f"built {prop.year_built}")
        if specs:
            lines.append(" • ".join(specs))

        if prop.hoa_fee:
            lines.append(f"HOA: ${prop.hoa_fee:,.0f}/mo")

        if prop.days_on_market is not None:
            lines.append(f"Days on market: {prop.days_on_market}")

        if prop.features:
            lines.append(f"Features: {', '.join(prop.features)}")

        if prop.description:
            lines.append(f"\n{prop.description}")

        if prop.price_history:
            lines.append("\nPrice history:")
            for entry in prop.price_history[:5]:
                lines.append(f"  {entry.get('date', '')}: ${entry.get('price', 0):,.0f} ({entry.get('event', '')})")

        return "\n".join(lines)

    async def _compare(self, property_ids: List[str]) -> AgentResponse:
        """Compare two or more properties side by side."""
        if len(property_ids) < 2:
            return AgentResponse(
                content="I need at least two properties to compare. Which ones would you like?",
                success=True,
                needs_followup=True,
            )

        properties = []
        for pid in property_ids:
            prop = await self.property_data_client.get_details(pid)
            if prop:
                properties.append(prop)

        if len(properties) < 2:
            return AgentResponse(
                content="I couldn't find enough of those properties to compare.",
                tools_used=["compare_properties"],
                success=True,
            )

        lines = ["Here's a comparison:\n"]
        header = " | ".join(["Attribute"] + [p.address for p in properties])
        lines.append(header)

        rows = [
            ("Price", [f"${p.list_price:,.0f}" if p.list_price else "N/A" for p in properties]),
            ("Bedrooms", [str(p.bedrooms or "N/A") for p in properties]),
            ("Bathrooms", [str(p.bathrooms or "N/A") for p in properties]),
            ("Sqft", [f"{p.sqft:,}" if p.sqft else "N/A" for p in properties]),
            ("Year built", [str(p.year_built or "N/A") for p in properties]),
            ("Days on market", [str(p.days_on_market if p.days_on_market is not None else "N/A") for p in properties]),
        ]
        for label, values in rows:
            lines.append(f"{label}: " + " | ".join(values))

        return AgentResponse(
            content="\n".join(lines),
            tools_used=["compare_properties"],
            data={"properties": [p.to_summary() for p in properties]},
            success=True,
        )
