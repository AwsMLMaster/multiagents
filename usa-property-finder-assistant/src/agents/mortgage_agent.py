"""
Mortgage Agent for USA Property Finder Assistant.

Handles mortgage payment calculations, affordability estimates, and current
rate lookups.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .base_agent import BaseAgent, AgentConfig, AgentResponse, AGENT_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


class MortgageAgent(BaseAgent):
    """
    Agent for mortgage payment calculations and affordability estimates.
    """

    def __init__(self, config: Optional[AgentConfig] = None, mortgage_rates_client=None):
        super().__init__(config)
        self._mortgage_rates_client = mortgage_rates_client

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="mortgage_agent",
            description="Mortgage payment calculator and affordability agent",
            tools=["calculate_payment", "calculate_affordability", "get_current_rates"],
            system_prompt=AGENT_SYSTEM_PROMPTS["mortgage"],
        )

    @property
    def mortgage_rates_client(self):
        if self._mortgage_rates_client is None:
            from ..integrations.mortgage_rates import create_mortgage_rates_client
            from config.settings import get_settings
            settings = get_settings()
            self._mortgage_rates_client = create_mortgage_rates_client(
                base_url=settings.mortgage_rates.base_url,
                api_key=settings.mortgage_rates.api_key,
            )
        return self._mortgage_rates_client

    async def execute(
        self,
        query: str,
        intent: Dict[str, Any],
        history: Optional[List[BaseMessage]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AgentResponse:
        """Route to the appropriate mortgage calculation based on intent."""
        try:
            intent_id = intent.get("intent_id", "")
            params = intent.get("parameters", {})

            if intent_id == "mortgage.affordability":
                return await self._affordability(params, user_context)
            if intent_id == "mortgage.rates":
                return await self._current_rates()
            return await self._payment(params, user_context)

        except Exception as e:
            return self._build_error_response(
                str(e), "Sorry, I couldn't complete that mortgage calculation."
            )

    async def _payment(
        self, params: Dict[str, Any], user_context: Optional[Dict[str, Any]]
    ) -> AgentResponse:
        price = params.get("price")
        if price is None:
            return AgentResponse(
                content="What's the home price you'd like to calculate a payment for?",
                success=True,
                needs_followup=True,
            )

        down_payment = params.get("down_payment")
        down_payment_percent = params.get("down_payment_percent")
        if down_payment is None:
            if down_payment_percent is not None:
                down_payment = price * (down_payment_percent / 100)
            elif user_context and user_context.get("pre_approval_amount"):
                down_payment = max(0.0, price * 0.20)
            else:
                down_payment = price * 0.20  # default assumption: 20% down

        rates = await self.mortgage_rates_client.get_current_rates()
        interest_rate = params.get("interest_rate") or rates.rate_30yr_fixed
        loan_term_years = params.get("loan_term_years", 30)
        hoa_fees = params.get("hoa_fees", 0.0)

        breakdown = self.mortgage_rates_client.calculate_payment(
            home_price=price,
            down_payment=down_payment,
            interest_rate=interest_rate,
            loan_term_years=loan_term_years,
            hoa_monthly=hoa_fees,
        )

        content = (
            f"Estimated monthly payment on a ${price:,.0f} home with "
            f"${down_payment:,.0f} down ({loan_term_years}-yr @ {interest_rate}%):\n\n"
            f"Principal & interest: ${breakdown.principal_and_interest:,.2f}\n"
            f"Property tax (est.): ${breakdown.property_tax_monthly:,.2f}\n"
            f"Home insurance (est.): ${breakdown.home_insurance_monthly:,.2f}\n"
        )
        if breakdown.pmi_monthly:
            content += f"PMI (down payment < 20%): ${breakdown.pmi_monthly:,.2f}\n"
        if breakdown.hoa_monthly:
            content += f"HOA: ${breakdown.hoa_monthly:,.2f}\n"
        content += f"\n**Total estimated monthly payment: ${breakdown.total_monthly_payment:,.2f}**"

        return AgentResponse(
            content=content,
            tools_used=["calculate_payment", "get_current_rates"],
            data={
                "home_price": price,
                "down_payment": down_payment,
                "interest_rate": interest_rate,
                "loan_term_years": loan_term_years,
                "total_monthly_payment": breakdown.total_monthly_payment,
                "breakdown": {
                    "principal_and_interest": breakdown.principal_and_interest,
                    "property_tax_monthly": breakdown.property_tax_monthly,
                    "home_insurance_monthly": breakdown.home_insurance_monthly,
                    "pmi_monthly": breakdown.pmi_monthly,
                    "hoa_monthly": breakdown.hoa_monthly,
                },
            },
            success=True,
        )

    async def _affordability(
        self, params: Dict[str, Any], user_context: Optional[Dict[str, Any]]
    ) -> AgentResponse:
        annual_income = params.get("annual_income")
        if annual_income is None:
            return AgentResponse(
                content="What's your approximate annual household income?",
                success=True,
                needs_followup=True,
            )

        monthly_debts = params.get("monthly_debts", 0.0)
        down_payment_available = params.get("down_payment_available", 0.0)
        if not down_payment_available and user_context:
            down_payment_available = user_context.get("pre_approval_amount") or 0.0

        rates = await self.mortgage_rates_client.get_current_rates()

        estimate = self.mortgage_rates_client.calculate_affordability(
            annual_income=annual_income,
            monthly_debts=monthly_debts,
            down_payment_available=down_payment_available,
            interest_rate=rates.rate_30yr_fixed,
        )

        content = (
            f"Based on ${annual_income:,.0f}/year income"
            + (f" and ${monthly_debts:,.0f}/mo in existing debts" if monthly_debts else "")
            + f":\n\nEstimated affordable home price: **${estimate.max_home_price:,.0f}**\n"
            f"Estimated max monthly housing payment: ${estimate.max_monthly_payment:,.0f}\n"
            f"Estimated debt-to-income ratio: {estimate.debt_to_income_ratio:.0%}\n\n"
            f"{estimate.notes}"
        )

        return AgentResponse(
            content=content,
            tools_used=["calculate_affordability", "get_current_rates"],
            data={
                "max_home_price": estimate.max_home_price,
                "max_monthly_payment": estimate.max_monthly_payment,
                "debt_to_income_ratio": estimate.debt_to_income_ratio,
            },
            success=True,
        )

    async def _current_rates(self) -> AgentResponse:
        rates = await self.mortgage_rates_client.get_current_rates()

        content = (
            f"Current average mortgage rates (as of {rates.as_of_date.strftime('%b %d, %Y')}):\n\n"
            f"30-year fixed: {rates.rate_30yr_fixed}%\n"
            f"15-year fixed: {rates.rate_15yr_fixed}%\n"
            f"5/1 ARM: {rates.rate_5_1_arm}%\n\n"
            "Your actual rate depends on your credit profile, loan amount, and lender."
        )

        return AgentResponse(
            content=content,
            tools_used=["get_current_rates"],
            data={
                "rate_30yr_fixed": rates.rate_30yr_fixed,
                "rate_15yr_fixed": rates.rate_15yr_fixed,
                "rate_5_1_arm": rates.rate_5_1_arm,
                "source": rates.source,
            },
            success=True,
        )
