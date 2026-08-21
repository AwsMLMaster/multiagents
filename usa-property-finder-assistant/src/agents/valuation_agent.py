"""
Valuation Agent for USA Property Finder Assistant.

Provides automated valuation model (AVM) estimates and comparable recent
sales data for a property.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .base_agent import BaseAgent, AgentConfig, AgentResponse, AGENT_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


class ValuationAgent(BaseAgent):
    """
    Agent for property value estimates and comparable sales.
    """

    def __init__(self, config: Optional[AgentConfig] = None, property_data_client=None):
        super().__init__(config)
        self._property_data_client = property_data_client

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="valuation_agent",
            description="Property valuation (AVM) and comps agent",
            tools=["get_avm_estimate", "get_comparable_sales"],
            system_prompt=AGENT_SYSTEM_PROMPTS["valuation"],
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
        Get an AVM estimate or comparable sales for a property.
        """
        try:
            intent_id = intent.get("intent_id", "")
            params = intent.get("parameters", {})
            property_id = (
                params.get("property_id_or_address")
                or params.get("property_id")
                or focused_property_id
            )

            if not property_id:
                return AgentResponse(
                    content="Which property would you like a valuation for?",
                    success=True,
                    needs_followup=True,
                )

            if intent_id == "valuation.comps":
                return await self._get_comps(property_id)

            return await self._get_estimate(property_id)

        except Exception as e:
            return self._build_error_response(
                str(e), "Sorry, I couldn't retrieve a valuation for that property."
            )

    async def _get_estimate(self, property_id: str) -> AgentResponse:
        estimate = await self.property_data_client.get_avm_estimate(property_id)

        if not estimate:
            return AgentResponse(
                content=(
                    "I don't have a value estimate available for that property "
                    "right now. This can happen for new construction or unlisted "
                    "properties."
                ),
                tools_used=["get_avm_estimate"],
                success=True,
            )

        content = (
            f"Estimated value: ${estimate.estimated_value:,.0f} "
            f"(range: ${estimate.value_range_low:,.0f} - ${estimate.value_range_high:,.0f})\n"
            f"Confidence: {estimate.confidence_score:.0%}, based on "
            f"{estimate.comparable_count} comparable sale(s)."
        )

        return AgentResponse(
            content=content,
            tools_used=["get_avm_estimate"],
            data={
                "property_id": property_id,
                "estimated_value": estimate.estimated_value,
                "value_range_low": estimate.value_range_low,
                "value_range_high": estimate.value_range_high,
                "confidence_score": estimate.confidence_score,
            },
            success=True,
        )

    async def _get_comps(self, property_id: str) -> AgentResponse:
        comps = await self.property_data_client.get_comparable_sales(property_id)

        if not comps:
            return AgentResponse(
                content="I couldn't find comparable recent sales near that property.",
                tools_used=["get_comparable_sales"],
                success=True,
            )

        lines = ["Comparable recent sales nearby:\n"]
        for i, comp in enumerate(comps, 1):
            specs = []
            if comp.bedrooms is not None:
                specs.append(f"{comp.bedrooms} bd")
            if comp.bathrooms is not None:
                specs.append(f"{comp.bathrooms} ba")
            if comp.sqft:
                specs.append(f"{comp.sqft:,} sqft")
            specs_str = f" ({', '.join(specs)})" if specs else ""

            lines.append(
                f"{i}. {comp.address} - sold ${comp.sale_price:,.0f} on "
                f"{comp.sale_date.strftime('%b %Y')}{specs_str}, "
                f"{comp.distance_miles} mi away"
            )

        return AgentResponse(
            content="\n".join(lines),
            tools_used=["get_comparable_sales"],
            data={
                "property_id": property_id,
                "comparables": [
                    {
                        "address": c.address,
                        "sale_price": c.sale_price,
                        "sale_date": c.sale_date.isoformat(),
                        "distance_miles": c.distance_miles,
                    }
                    for c in comps
                ],
            },
            success=True,
        )
