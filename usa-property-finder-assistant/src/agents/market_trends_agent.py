"""
Market Trends Agent for USA Property Finder Assistant.

Provides local housing market analysis: price trends, days-on-market,
buyer's/seller's market classification, and forecasts.
"""

import logging
import random
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .base_agent import BaseAgent, AgentConfig, AgentResponse, AGENT_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


class MarketTrendsAgent(BaseAgent):
    """
    Agent for local housing market trend analysis and forecasts.
    """

    def __init__(self, config: Optional[AgentConfig] = None, geocoding_client=None):
        super().__init__(config)
        self._geocoding_client = geocoding_client

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="market_trends_agent",
            description="Housing market trends and forecast agent",
            tools=["get_price_trends", "get_market_temperature", "get_days_on_market", "get_market_forecast"],
            system_prompt=AGENT_SYSTEM_PROMPTS["market_trends"],
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
        """Route to market trends or market forecast."""
        try:
            intent_id = intent.get("intent_id", "")
            params = intent.get("parameters", {})
            location = params.get("location")

            if not location:
                return AgentResponse(
                    content="Which city or area would you like market data for?",
                    success=True,
                    needs_followup=True,
                )

            if intent_id == "market.forecast":
                return self._forecast(location)
            return self._trends(location)

        except Exception as e:
            return self._build_error_response(
                str(e), "Sorry, I couldn't retrieve market data right now."
            )

    def _trends(self, location: str) -> AgentResponse:
        # NOTE: not wired to a live market-data API in this scaffold; a
        # deterministic placeholder demonstrates the agent's response contract.
        # Replace with a real provider (e.g., ATTOM market stats, Redfin Data
        # Center, or an MLS-derived market stats feed).
        data = self._placeholder_market_data(location)

        market_label = (
            "a seller's market" if data["months_of_inventory"] < 3 else
            "a buyer's market" if data["months_of_inventory"] > 6 else
            "a balanced market"
        )

        content = (
            f"Housing market snapshot for {location}:\n\n"
            f"Median list price: ${data['median_price']:,.0f} "
            f"({'+' if data['yoy_change_pct'] >= 0 else ''}{data['yoy_change_pct']}% YoY)\n"
            f"Median days on market: {data['median_dom']} days\n"
            f"Months of inventory: {data['months_of_inventory']}\n\n"
            f"This currently looks like **{market_label}**."
        )

        return AgentResponse(
            content=content,
            tools_used=["get_price_trends", "get_market_temperature", "get_days_on_market"],
            data={"location": location, "market_classification": market_label, **data},
            success=True,
        )

    def _forecast(self, location: str) -> AgentResponse:
        data = self._placeholder_market_data(location)
        forecast_pct = round(data["yoy_change_pct"] * 0.6, 1)  # damped continuation

        content = (
            f"Based on recent trends in {location}, prices have moved "
            f"{'+' if data['yoy_change_pct'] >= 0 else ''}{data['yoy_change_pct']}% "
            f"over the past year. If current trends continue, a rough forecast "
            f"suggests {'+' if forecast_pct >= 0 else ''}{forecast_pct}% over the "
            f"next 12 months.\n\n"
            "This is a trend-based estimate, not a guarantee - local market "
            "conditions can shift due to interest rates, inventory, and the "
            "broader economy."
        )

        return AgentResponse(
            content=content,
            tools_used=["get_market_forecast"],
            data={"location": location, "forecast_12mo_pct": forecast_pct},
            success=True,
        )

    def _placeholder_market_data(self, location: str) -> Dict[str, Any]:
        """Deterministic placeholder market metrics keyed by location string."""
        rng = random.Random(location.lower())
        return {
            "median_price": rng.randint(250_000, 950_000),
            "yoy_change_pct": round(rng.uniform(-4.0, 12.0), 1),
            "median_dom": rng.randint(8, 75),
            "months_of_inventory": round(rng.uniform(1.0, 9.0), 1),
        }
