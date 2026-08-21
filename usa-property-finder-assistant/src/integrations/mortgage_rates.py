"""
Mortgage Rates & Calculation Integration.

Provides current average mortgage rates (e.g., from a Freddie Mac PMMS-style
feed) plus deterministic payment/affordability math that does not require an
external API.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# Conservative fallback rates used when the live rates provider is
# unavailable or not configured. These should be refreshed periodically.
FALLBACK_RATES = {
    "30_year_fixed": 6.75,
    "15_year_fixed": 6.00,
    "5_1_arm": 6.25,
}


@dataclass
class MortgageRatesConfig:
    """Configuration for the mortgage rates client."""
    base_url: str = ""
    api_key: str = ""
    timeout: int = 10


@dataclass
class CurrentRates:
    """Current average mortgage interest rates."""
    rate_30yr_fixed: float
    rate_15yr_fixed: float
    rate_5_1_arm: float
    as_of_date: datetime
    source: str = "fallback"


@dataclass
class PaymentBreakdown:
    """Monthly mortgage payment breakdown."""
    principal_and_interest: float
    property_tax_monthly: float
    home_insurance_monthly: float
    pmi_monthly: float
    hoa_monthly: float
    total_monthly_payment: float
    loan_amount: float
    interest_rate: float
    loan_term_years: int


@dataclass
class AffordabilityEstimate:
    """Home affordability estimate based on income and debts."""
    max_home_price: float
    max_monthly_payment: float
    estimated_loan_amount: float
    debt_to_income_ratio: float
    notes: str = ""


class MortgageRatesClient:
    """
    Client for current mortgage rates and deterministic mortgage math.
    """

    def __init__(self, config: MortgageRatesConfig):
        self.config = config

    async def get_current_rates(self) -> CurrentRates:
        """Get current average mortgage interest rates."""
        if self.config.base_url and self.config.api_key:
            try:
                return await self._fetch_live_rates()
            except Exception as e:
                logger.warning(f"Live mortgage rates fetch failed, using fallback: {e}")

        return CurrentRates(
            rate_30yr_fixed=FALLBACK_RATES["30_year_fixed"],
            rate_15yr_fixed=FALLBACK_RATES["15_year_fixed"],
            rate_5_1_arm=FALLBACK_RATES["5_1_arm"],
            as_of_date=datetime.utcnow(),
            source="fallback",
        )

    async def _fetch_live_rates(self) -> CurrentRates:
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{self.config.base_url.rstrip('/')}/rates", headers=headers
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Rates provider returned status {resp.status}")
                data = await resp.json()

        return CurrentRates(
            rate_30yr_fixed=data["rate_30yr_fixed"],
            rate_15yr_fixed=data["rate_15yr_fixed"],
            rate_5_1_arm=data.get("rate_5_1_arm", data["rate_30yr_fixed"] - 0.5),
            as_of_date=datetime.utcnow(),
            source="live",
        )

    def calculate_payment(
        self,
        home_price: float,
        down_payment: float,
        interest_rate: float,
        loan_term_years: int = 30,
        property_tax_rate: float = 0.011,  # ~1.1% national average annual
        annual_insurance: float = 1500.0,
        hoa_monthly: float = 0.0,
    ) -> PaymentBreakdown:
        """
        Calculate the estimated monthly mortgage payment.

        Args:
            home_price: Purchase price of the home.
            down_payment: Down payment amount (dollars, not percent).
            interest_rate: Annual interest rate as a percent (e.g. 6.75).
            loan_term_years: Loan term in years.
            property_tax_rate: Annual property tax rate as a fraction of home value.
            annual_insurance: Estimated annual homeowners insurance.
            hoa_monthly: Monthly HOA fee, if any.

        Returns:
            PaymentBreakdown with principal/interest, taxes, insurance, PMI, HOA.
        """
        loan_amount = max(0.0, home_price - down_payment)
        monthly_rate = (interest_rate / 100) / 12
        num_payments = loan_term_years * 12

        if monthly_rate == 0:
            principal_and_interest = loan_amount / num_payments if num_payments else 0.0
        else:
            principal_and_interest = (
                loan_amount
                * (monthly_rate * (1 + monthly_rate) ** num_payments)
                / ((1 + monthly_rate) ** num_payments - 1)
            )

        property_tax_monthly = (home_price * property_tax_rate) / 12
        home_insurance_monthly = annual_insurance / 12

        # PMI typically required when down payment < 20% of home price
        down_payment_pct = (down_payment / home_price) if home_price else 0.0
        pmi_monthly = (loan_amount * 0.006) / 12 if down_payment_pct < 0.20 else 0.0

        total = (
            principal_and_interest
            + property_tax_monthly
            + home_insurance_monthly
            + pmi_monthly
            + hoa_monthly
        )

        return PaymentBreakdown(
            principal_and_interest=round(principal_and_interest, 2),
            property_tax_monthly=round(property_tax_monthly, 2),
            home_insurance_monthly=round(home_insurance_monthly, 2),
            pmi_monthly=round(pmi_monthly, 2),
            hoa_monthly=round(hoa_monthly, 2),
            total_monthly_payment=round(total, 2),
            loan_amount=round(loan_amount, 2),
            interest_rate=interest_rate,
            loan_term_years=loan_term_years,
        )

    def calculate_affordability(
        self,
        annual_income: float,
        monthly_debts: float = 0.0,
        down_payment_available: float = 0.0,
        interest_rate: float = 6.75,
        loan_term_years: int = 30,
        max_dti: float = 0.36,  # conservative 36% debt-to-income ceiling
    ) -> AffordabilityEstimate:
        """
        Estimate maximum affordable home price based on income and debts.

        Uses a standard debt-to-income (DTI) approach: total housing + debt
        payments should not exceed max_dti of gross monthly income.
        """
        monthly_income = annual_income / 12
        max_total_debt_payment = monthly_income * max_dti
        max_housing_payment = max(0.0, max_total_debt_payment - monthly_debts)

        monthly_rate = (interest_rate / 100) / 12
        num_payments = loan_term_years * 12

        # Reserve ~25% of the housing payment budget for taxes/insurance/PMI
        max_principal_interest = max_housing_payment * 0.75

        if monthly_rate == 0:
            max_loan_amount = max_principal_interest * num_payments
        else:
            max_loan_amount = (
                max_principal_interest
                * ((1 + monthly_rate) ** num_payments - 1)
                / (monthly_rate * (1 + monthly_rate) ** num_payments)
            )

        max_home_price = max_loan_amount + down_payment_available
        dti = (monthly_debts + max_housing_payment) / monthly_income if monthly_income else 0.0

        return AffordabilityEstimate(
            max_home_price=round(max_home_price, 2),
            max_monthly_payment=round(max_housing_payment, 2),
            estimated_loan_amount=round(max_loan_amount, 2),
            debt_to_income_ratio=round(dti, 3),
            notes=(
                "Estimate assumes a 36% debt-to-income ceiling and reserves "
                "~25% of the housing budget for taxes, insurance, and PMI. "
                "Actual qualification depends on your lender and credit profile."
            ),
        )


def create_mortgage_rates_client(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> MortgageRatesClient:
    """Factory function to create a configured mortgage rates client."""
    config = MortgageRatesConfig(base_url=base_url or "", api_key=api_key or "")
    return MortgageRatesClient(config)
