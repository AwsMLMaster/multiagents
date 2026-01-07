"""
Offerings Matching Agent

Intelligent agent that matches customers to the most suitable bank offerings
based on their profile, behavior, and current context.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .models import (
    Offering,
    OfferingCategory,
    CustomerMatch,
    EligibilityCriteria,
)
from .repository import OfferingsRepository

logger = logging.getLogger(__name__)


@dataclass
class CustomerProfile:
    """Customer profile for matching."""
    customer_id: str

    # Demographics
    age: Optional[int] = None
    account_type: str = "standard"  # standard, premium, business

    # Financial profile
    current_balance: Decimal = Decimal("0")
    average_balance: Decimal = Decimal("0")
    monthly_income: Optional[Decimal] = None
    credit_score: Optional[int] = None
    debt_ratio: Optional[float] = None

    # Account info
    account_age_months: int = 0
    products_held: List[str] = field(default_factory=list)

    # Behavioral
    monthly_transactions: int = 0
    spending_pattern: str = "average"  # low, average, high
    savings_pattern: str = "irregular"  # none, irregular, regular

    # Segments (computed or assigned)
    segments: List[str] = field(default_factory=list)

    # Recent activity
    last_offering_shown_at: Optional[datetime] = None
    last_offering_consented_at: Optional[datetime] = None
    declined_offering_ids: List[str] = field(default_factory=list)

    # Preferences
    preferred_language: str = "he"
    prefers_digital: bool = True


@dataclass
class MatchContext:
    """Context for the current matching session."""
    session_id: str
    trigger_type: str = "proactive"  # proactive, reactive, scheduled
    trigger_intent: Optional[str] = None
    current_balance_snapshot: Optional[Decimal] = None
    idle_balance: Optional[Decimal] = None
    idle_balance_days: Optional[int] = None
    conversation_topics: List[str] = field(default_factory=list)
    user_expressed_needs: List[str] = field(default_factory=list)
    # e.g., ["want to save", "looking for loan", "need credit card"]


class OfferingsMatchingAgent:
    """
    Agent for matching customers to suitable offerings.

    Uses a scoring algorithm that considers:
    1. Eligibility - Must pass all criteria
    2. Relevance - How well the offering matches customer needs
    3. Timing - Is this the right time to present?
    4. Priority - Offering priority and promotional status
    5. History - Past interactions with similar offerings
    """

    def __init__(
        self,
        repository: OfferingsRepository,
        max_matches: int = 3,
        min_score_threshold: float = 0.3,
    ):
        self.repository = repository
        self.max_matches = max_matches
        self.min_score_threshold = min_score_threshold

        # Scoring weights
        self.weights = {
            "eligibility": 0.25,  # Base eligibility score
            "relevance": 0.30,   # Match to customer needs
            "timing": 0.20,      # Right time to present
            "priority": 0.15,    # Offering priority
            "history": 0.10,     # Past interaction history
        }

    async def find_matches(
        self,
        customer: CustomerProfile,
        context: MatchContext,
        categories: Optional[List[OfferingCategory]] = None,
    ) -> List[CustomerMatch]:
        """
        Find the best offering matches for a customer.

        Args:
            customer: Customer profile
            context: Current matching context
            categories: Optional filter by categories

        Returns:
            List of CustomerMatch objects, sorted by score
        """
        # Get all active offerings
        offerings = self.repository.get_all(active_only=True)

        # Filter by category if specified
        if categories:
            offerings = [o for o in offerings if o.category in categories]

        # Score each offering
        scored_matches: List[Tuple[float, CustomerMatch]] = []

        for offering in offerings:
            # Check basic eligibility
            if not self._check_eligibility(offering, customer):
                continue

            # Skip recently declined offerings
            if offering.offering_id in customer.declined_offering_ids:
                continue

            # Calculate match score
            score, reasons = self._calculate_match_score(
                offering, customer, context
            )

            if score >= self.min_score_threshold:
                match = self._create_match(
                    offering, customer, context, score, reasons
                )
                scored_matches.append((score, match))

        # Sort by score and return top matches
        scored_matches.sort(key=lambda x: x[0], reverse=True)
        return [match for _, match in scored_matches[:self.max_matches]]

    async def find_best_match(
        self,
        customer: CustomerProfile,
        context: MatchContext,
    ) -> Optional[CustomerMatch]:
        """Find the single best match for a customer."""
        matches = await self.find_matches(customer, context)
        return matches[0] if matches else None

    async def find_matches_for_trigger(
        self,
        customer: CustomerProfile,
        trigger_type: str,
        trigger_data: Dict[str, Any],
    ) -> List[CustomerMatch]:
        """
        Find matches based on a specific trigger event.

        Trigger types:
        - balance_threshold: Customer has idle balance
        - intent_completion: Customer completed an intent
        - time_based: Scheduled/periodic check
        - life_event: Detected life event
        """
        context = MatchContext(
            session_id=trigger_data.get("session_id", ""),
            trigger_type=trigger_type,
        )

        if trigger_type == "balance_threshold":
            context.idle_balance = Decimal(str(trigger_data.get("idle_balance", 0)))
            context.idle_balance_days = trigger_data.get("idle_days", 0)
            context.current_balance_snapshot = Decimal(str(trigger_data.get("current_balance", 0)))

        elif trigger_type == "intent_completion":
            context.trigger_intent = trigger_data.get("intent")
            context.conversation_topics = trigger_data.get("topics", [])

        elif trigger_type == "user_request":
            context.user_expressed_needs = trigger_data.get("needs", [])

        # Get offerings with matching triggers
        offerings = self.repository.get_all(active_only=True)
        triggered_offerings = []

        for offering in offerings:
            if self._matches_trigger(offering, trigger_type, trigger_data):
                triggered_offerings.append(offering)

        # Score and return matches
        scored_matches: List[Tuple[float, CustomerMatch]] = []

        for offering in triggered_offerings:
            if not self._check_eligibility(offering, customer):
                continue

            score, reasons = self._calculate_match_score(
                offering, customer, context
            )

            if score >= self.min_score_threshold:
                match = self._create_match(
                    offering, customer, context, score, reasons
                )
                scored_matches.append((score, match))

        scored_matches.sort(key=lambda x: x[0], reverse=True)
        return [match for _, match in scored_matches[:self.max_matches]]

    def _check_eligibility(
        self,
        offering: Offering,
        customer: CustomerProfile,
    ) -> bool:
        """Check if customer meets all eligibility criteria."""
        criteria = offering.eligibility

        # Age check
        if criteria.min_age and customer.age:
            if customer.age < criteria.min_age:
                return False
        if criteria.max_age and customer.age:
            if customer.age > criteria.max_age:
                return False

        # Account age check
        if criteria.min_account_age_months:
            if customer.account_age_months < criteria.min_account_age_months:
                return False

        # Balance check
        if criteria.min_balance:
            if customer.current_balance < criteria.min_balance:
                return False
        if criteria.max_balance:
            if customer.current_balance > criteria.max_balance:
                return False

        # Income check
        if criteria.min_monthly_income and customer.monthly_income:
            if customer.monthly_income < criteria.min_monthly_income:
                return False

        # Credit score check
        if criteria.min_credit_score and customer.credit_score:
            if customer.credit_score < criteria.min_credit_score:
                return False

        # Debt ratio check
        if criteria.max_debt_ratio and customer.debt_ratio:
            if customer.debt_ratio > criteria.max_debt_ratio:
                return False

        # Product holdings check
        if criteria.required_product_holdings:
            if not all(p in customer.products_held for p in criteria.required_product_holdings):
                return False

        if criteria.excluded_product_holdings:
            if any(p in customer.products_held for p in criteria.excluded_product_holdings):
                return False

        # Account type check
        if criteria.required_account_types:
            if customer.account_type not in criteria.required_account_types:
                return False

        if criteria.excluded_account_types:
            if customer.account_type in criteria.excluded_account_types:
                return False

        # Segment check
        if criteria.target_segments:
            if not any(s in customer.segments for s in criteria.target_segments):
                return False

        if criteria.excluded_segments:
            if any(s in customer.segments for s in criteria.excluded_segments):
                return False

        return True

    def _calculate_match_score(
        self,
        offering: Offering,
        customer: CustomerProfile,
        context: MatchContext,
    ) -> Tuple[float, List[str]]:
        """Calculate match score and reasons."""
        scores = {}
        reasons = []

        # 1. Eligibility score (how well they match, not just pass/fail)
        eligibility_score, elig_reasons = self._score_eligibility(
            offering, customer
        )
        scores["eligibility"] = eligibility_score
        reasons.extend(elig_reasons)

        # 2. Relevance score (match to current context/needs)
        relevance_score, rel_reasons = self._score_relevance(
            offering, customer, context
        )
        scores["relevance"] = relevance_score
        reasons.extend(rel_reasons)

        # 3. Timing score (is this the right time?)
        timing_score, tim_reasons = self._score_timing(
            offering, customer, context
        )
        scores["timing"] = timing_score
        reasons.extend(tim_reasons)

        # 4. Priority score (offering priority + promotional status)
        priority_score = self._score_priority(offering)
        scores["priority"] = priority_score

        # 5. History score (past interactions)
        history_score = self._score_history(offering, customer)
        scores["history"] = history_score

        # Calculate weighted total
        total_score = sum(
            scores[k] * self.weights[k]
            for k in scores
        )

        return total_score, reasons

    def _score_eligibility(
        self,
        offering: Offering,
        customer: CustomerProfile,
    ) -> Tuple[float, List[str]]:
        """Score how well customer matches eligibility criteria."""
        score = 0.5  # Base score for passing eligibility
        reasons = []
        criteria = offering.eligibility

        # Bonus for being in target segment
        if criteria.target_segments:
            matching_segments = [
                s for s in customer.segments
                if s in criteria.target_segments
            ]
            if matching_segments:
                score += 0.2
                reasons.append(f"matches_segment:{matching_segments[0]}")

        # Bonus for exceeding minimum balance significantly
        if criteria.min_balance and customer.current_balance:
            ratio = float(customer.current_balance / criteria.min_balance)
            if ratio >= 2:
                score += 0.15
                reasons.append("high_balance_fit")
            elif ratio >= 1.5:
                score += 0.1

        # Bonus for good credit score
        if criteria.min_credit_score and customer.credit_score:
            if customer.credit_score >= criteria.min_credit_score + 100:
                score += 0.15
                reasons.append("excellent_credit")

        return min(1.0, score), reasons

    def _score_relevance(
        self,
        offering: Offering,
        customer: CustomerProfile,
        context: MatchContext,
    ) -> Tuple[float, List[str]]:
        """Score relevance to customer's current context."""
        score = 0.3  # Base relevance
        reasons = []

        # High score if triggered by matching intent
        if context.trigger_intent:
            for trigger in offering.trigger_conditions:
                if trigger.get("type") == "intent_completion":
                    if trigger.get("intent") == context.trigger_intent:
                        score += 0.4
                        reasons.append(f"triggered_by_intent:{context.trigger_intent}")

        # High score for idle balance match
        if context.idle_balance and context.idle_balance > Decimal("0"):
            for trigger in offering.trigger_conditions:
                if trigger.get("type") == "balance_threshold":
                    min_idle = Decimal(str(trigger.get("min_idle_balance", 0)))
                    if context.idle_balance >= min_idle:
                        score += 0.4
                        reasons.append("high_idle_balance")

        # Match to expressed needs
        if context.user_expressed_needs:
            need_keywords = {
                "save": [OfferingCategory.SAVINGS, OfferingCategory.DEPOSITS],
                "loan": [OfferingCategory.LOANS],
                "credit": [OfferingCategory.CREDIT_CARDS, OfferingCategory.LOANS],
                "invest": [OfferingCategory.INVESTMENTS],
            }

            for need in context.user_expressed_needs:
                for keyword, categories in need_keywords.items():
                    if keyword in need.lower():
                        if offering.category in categories:
                            score += 0.3
                            reasons.append(f"matches_need:{keyword}")

        # Savings offering with idle balance
        if offering.category == OfferingCategory.SAVINGS:
            if context.idle_balance and context.idle_balance >= Decimal("5000"):
                score += 0.2
                reasons.append("idle_funds_available")

        return min(1.0, score), reasons

    def _score_timing(
        self,
        offering: Offering,
        customer: CustomerProfile,
        context: MatchContext,
    ) -> Tuple[float, List[str]]:
        """Score timing appropriateness."""
        score = 0.5  # Base timing score
        reasons = []

        # Check if promotional period is active
        if offering.is_promotional and offering.is_promotion_active():
            score += 0.3
            reasons.append("active_promotion")

        # Penalize if recently shown an offering
        if customer.last_offering_shown_at:
            days_since_shown = (datetime.utcnow() - customer.last_offering_shown_at).days
            if days_since_shown < 7:
                score -= 0.3
            elif days_since_shown < 14:
                score -= 0.1

        # Bonus for proactive triggers at good moments
        if context.trigger_type == "intent_completion":
            if context.trigger_intent in ["check_balance", "transaction_history"]:
                score += 0.2
                reasons.append("good_conversation_moment")

        return max(0.0, min(1.0, score)), reasons

    def _score_priority(self, offering: Offering) -> float:
        """Score based on offering priority."""
        # Normalize priority (0-100) to (0-1)
        base_score = offering.priority / 100.0

        # Bonus for promotional offerings
        if offering.is_promotional and offering.is_promotion_active():
            base_score += 0.2

        return min(1.0, base_score)

    def _score_history(
        self,
        offering: Offering,
        customer: CustomerProfile,
    ) -> float:
        """Score based on customer's history with similar offerings."""
        score = 0.5  # Neutral

        # Penalize if customer declined similar offerings
        if offering.offering_id in customer.declined_offering_ids:
            return 0.0

        # Bonus if customer previously consented to offerings
        if customer.last_offering_consented_at:
            # Customer is receptive to offerings
            score += 0.2

        return min(1.0, score)

    def _matches_trigger(
        self,
        offering: Offering,
        trigger_type: str,
        trigger_data: Dict[str, Any],
    ) -> bool:
        """Check if offering matches the trigger event."""
        for trigger in offering.trigger_conditions:
            if trigger.get("type") == trigger_type:
                if trigger_type == "balance_threshold":
                    min_idle = trigger.get("min_idle_balance", 0)
                    idle_balance = trigger_data.get("idle_balance", 0)
                    if idle_balance >= min_idle:
                        return True

                elif trigger_type == "intent_completion":
                    if trigger.get("intent") == trigger_data.get("intent"):
                        return True

                elif trigger_type == "segment":
                    target_segments = trigger.get("segments", [])
                    customer_segments = trigger_data.get("customer_segments", [])
                    if any(s in customer_segments for s in target_segments):
                        return True

                elif trigger_type == "time_based":
                    # Always match time-based if we're doing a scheduled check
                    return True

        return False

    def _create_match(
        self,
        offering: Offering,
        customer: CustomerProfile,
        context: MatchContext,
        score: float,
        reasons: List[str],
    ) -> CustomerMatch:
        """Create a CustomerMatch object."""
        # Calculate personalized amount
        personalized_amount = self._calculate_personalized_amount(
            offering, customer, context
        )

        # Generate personalized message
        personalized_message = self._generate_personalized_message(
            offering, customer, context, personalized_amount
        )

        # Calculate projected benefit
        projected_benefit = self._calculate_projected_benefit(
            offering, personalized_amount
        )

        return CustomerMatch(
            offering_id=offering.offering_id,
            offering=offering,
            customer_id=customer.customer_id,
            match_score=score,
            match_reasons=reasons,
            personalized_amount=personalized_amount,
            personalized_message=personalized_message,
            projected_benefit=projected_benefit,
            trigger_type=context.trigger_type,
            trigger_context={
                "intent": context.trigger_intent,
                "idle_balance": str(context.idle_balance) if context.idle_balance else None,
            },
            matched_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=7),
        )

    def _calculate_personalized_amount(
        self,
        offering: Offering,
        customer: CustomerProfile,
        context: MatchContext,
    ) -> Optional[Decimal]:
        """Calculate suggested amount based on customer profile."""
        if offering.category in [OfferingCategory.SAVINGS, OfferingCategory.DEPOSITS]:
            # Suggest based on idle balance
            if context.idle_balance:
                # Round to nice number
                amount = context.idle_balance
                if amount >= 10000:
                    amount = (amount // 1000) * 1000  # Round to nearest 1000
                return amount

            # Otherwise suggest based on current balance
            suggested = customer.current_balance * Decimal("0.3")  # 30% of balance
            if suggested >= 1000:
                return (suggested // 1000) * 1000

        elif offering.category == OfferingCategory.LOANS:
            # Use pre-approved limit or calculate based on income
            if customer.monthly_income:
                max_loan = customer.monthly_income * 12  # 12 months income
                if offering.terms.max_amount:
                    return min(max_loan, offering.terms.max_amount)
                return max_loan

        return offering.terms.recommended_amount

    def _generate_personalized_message(
        self,
        offering: Offering,
        customer: CustomerProfile,
        context: MatchContext,
        personalized_amount: Optional[Decimal],
    ) -> str:
        """Generate personalized message for the customer."""
        template = offering.presentation.personalized_message_template

        if not template:
            # Use default message
            if customer.preferred_language == "he":
                return offering.presentation.description_he
            return offering.presentation.description_en

        # Fill in template variables
        projected = self._calculate_projected_benefit(offering, personalized_amount)

        replacements = {
            "{idle_balance}": f"{context.idle_balance:,.0f}" if context.idle_balance else "",
            "{personalized_amount}": f"{personalized_amount:,.0f}" if personalized_amount else "",
            "{projected_earnings}": projected or "",
            "{interest_rate}": str(offering.terms.interest_rate) if offering.terms.interest_rate else "",
            "{customer_name}": "",  # Would be filled from customer record
        }

        message = template
        for key, value in replacements.items():
            message = message.replace(key, value)

        return message

    def _calculate_projected_benefit(
        self,
        offering: Offering,
        amount: Optional[Decimal],
    ) -> Optional[str]:
        """Calculate projected benefit string."""
        if not amount or not offering.terms.interest_rate:
            return None

        # Calculate annual earnings
        annual_rate = offering.terms.interest_rate / 100
        annual_earnings = amount * annual_rate

        return f"{annual_earnings:,.0f}"
