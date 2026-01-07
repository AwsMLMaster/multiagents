"""
Offerings Repository

Storage and retrieval of bank product offerings.
Includes pre-configured offerings for common banking products.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
import json

import boto3
from botocore.exceptions import ClientError

from .models import (
    Offering,
    OfferingCategory,
    OfferingType,
    EligibilityCriteria,
    OfferingTerms,
    OfferingPresentation,
    FulfillmentMode,
)

logger = logging.getLogger(__name__)


class OfferingsRepository:
    """
    Repository for managing bank offerings.

    Supports both in-memory storage (for development) and DynamoDB (for production).
    """

    def __init__(
        self,
        table_name: str = "bank-offerings",
        region: str = "us-east-1",
        use_dynamodb: bool = True,
    ):
        self.table_name = table_name
        self.use_dynamodb = use_dynamodb

        if use_dynamodb:
            self.dynamodb = boto3.resource("dynamodb", region_name=region)
            self.table = self.dynamodb.Table(table_name)
        else:
            self._memory_store: Dict[str, Offering] = {}

        # Initialize with default offerings
        self._initialize_default_offerings()

    def _initialize_default_offerings(self) -> None:
        """Initialize repository with default bank offerings."""
        default_offerings = self._create_default_offerings()

        for offering in default_offerings:
            try:
                self.save(offering)
            except Exception as e:
                logger.warning(f"Failed to save default offering {offering.offering_id}: {e}")

    def _create_default_offerings(self) -> List[Offering]:
        """Create default bank offerings."""
        offerings = []

        # ========== SAVINGS OFFERINGS ==========

        # High-Yield Savings (the example from user: 12k balance -> 3% savings)
        offerings.append(Offering(
            offering_id="savings-high-yield-001",
            name="חיסכון בתשואה גבוהה",
            category=OfferingCategory.SAVINGS,
            offering_type=OfferingType.HIGH_YIELD_SAVINGS,
            eligibility=EligibilityCriteria(
                min_balance=Decimal("5000"),
                min_account_age_months=3,
                target_segments=["standard", "premium", "young_professional"],
            ),
            terms=OfferingTerms(
                interest_rate=Decimal("3.0"),
                interest_rate_type="fixed",
                min_amount=Decimal("5000"),
                max_amount=Decimal("500000"),
                min_term_months=6,
                lock_in_period_months=3,
            ),
            presentation=OfferingPresentation(
                title_he="חיסכון בתשואה גבוהה 3%",
                subtitle_he="הכסף שלך יעבוד בשבילך",
                description_he="העבר את היתרה הפנויה שלך לחשבון חיסכון בתשואה של 3% שנתי. ללא עמלות, עם גישה גמישה לכספים.",
                benefits_he=[
                    "ריבית שנתית של 3%",
                    "ללא עמלות ניהול",
                    "משיכה גמישה לאחר 3 חודשים",
                    "צבירת ריבית חודשית",
                ],
                call_to_action_he="אני מעוניין לפתוח חיסכון",
                title_en="High-Yield Savings 3%",
                subtitle_en="Make your money work for you",
                description_en="Transfer your available balance to a savings account earning 3% annual interest. No fees, flexible access.",
                benefits_en=[
                    "3% annual interest rate",
                    "No management fees",
                    "Flexible withdrawal after 3 months",
                    "Monthly interest accrual",
                ],
                call_to_action_en="I'm interested in opening savings",
                icon="piggy-bank",
                color_scheme="green",
                priority_badge="recommended",
                personalized_message_template="שמנו לב שיש לך {idle_balance} ₪ ביתרה פנויה. תוכל להרוויח כ-{projected_earnings} ₪ בשנה בריבית!",
            ),
            fulfillment_mode=FulfillmentMode.EMAIL_TO_BANKER,  # Phase 1
            fulfillment_intent_id="open_savings_account",  # For Phase 2
            banker_action_required=True,
            priority=90,
            trigger_conditions=[
                {"type": "balance_threshold", "min_idle_balance": 10000, "idle_days": 30},
                {"type": "intent_completion", "intent": "check_balance"},
            ],
        ))

        # Goal-Based Savings
        offerings.append(Offering(
            offering_id="savings-goal-001",
            name="חיסכון למטרה",
            category=OfferingCategory.SAVINGS,
            offering_type=OfferingType.GOAL_SAVINGS,
            eligibility=EligibilityCriteria(
                min_age=18,
                max_age=45,
                target_segments=["young_professional", "standard"],
            ),
            terms=OfferingTerms(
                interest_rate=Decimal("2.5"),
                bonus_rate=Decimal("0.5"),
                bonus_rate_duration_months=12,
                min_amount=Decimal("100"),
                max_amount=Decimal("100000"),
            ),
            presentation=OfferingPresentation(
                title_he="חיסכון למטרה",
                subtitle_he="חסכו לחופשה, לרכב, או לכל מטרה",
                description_he="הגדירו יעד חיסכון ותקבלו בונוס ריבית כשתגיעו אליו!",
                benefits_he=[
                    "בונוס 0.5% בהגעה ליעד",
                    "מעקב התקדמות באפליקציה",
                    "הפקדות אוטומטיות",
                ],
                call_to_action_he="להתחיל לחסוך למטרה",
                title_en="Goal Savings",
                subtitle_en="Save for vacation, car, or any goal",
                description_en="Set a savings goal and get a bonus interest rate when you reach it!",
                benefits_en=[
                    "0.5% bonus on goal achievement",
                    "Progress tracking in app",
                    "Automatic deposits",
                ],
                call_to_action_en="Start saving for a goal",
                icon="target",
                color_scheme="blue",
            ),
            fulfillment_mode=FulfillmentMode.EMAIL_TO_BANKER,
            fulfillment_intent_id="open_goal_savings",
            priority=70,
            trigger_conditions=[
                {"type": "behavior", "pattern": "regular_deposits"},
                {"type": "segment", "segments": ["young_professional"]},
            ],
        ))

        # ========== DEPOSIT OFFERINGS ==========

        # Fixed Deposit
        offerings.append(Offering(
            offering_id="deposit-fixed-001",
            name="פיקדון בריבית קבועה",
            category=OfferingCategory.DEPOSITS,
            offering_type=OfferingType.FIXED_DEPOSIT,
            eligibility=EligibilityCriteria(
                min_balance=Decimal("10000"),
                target_segments=["premium", "senior"],
            ),
            terms=OfferingTerms(
                interest_rate=Decimal("4.5"),
                interest_rate_type="fixed",
                min_amount=Decimal("10000"),
                max_amount=Decimal("1000000"),
                min_term_months=12,
                max_term_months=60,
                early_withdrawal_penalty_percent=Decimal("1.0"),
            ),
            presentation=OfferingPresentation(
                title_he="פיקדון 4.5% לשנה",
                subtitle_he="ריבית מובטחת, שקט נפשי",
                description_he="נעלו את הכסף שלכם בפיקדון בטוח עם ריבית מובטחת של 4.5%.",
                benefits_he=[
                    "ריבית מובטחת 4.5%",
                    "בטחון מלא על הקרן",
                    "תכנון פיננסי ברור",
                ],
                call_to_action_he="לפתוח פיקדון",
                title_en="4.5% Fixed Deposit",
                subtitle_en="Guaranteed interest, peace of mind",
                description_en="Lock your money in a secure deposit with guaranteed 4.5% interest.",
                benefits_en=[
                    "Guaranteed 4.5% interest",
                    "Full principal protection",
                    "Clear financial planning",
                ],
                call_to_action_en="Open fixed deposit",
                icon="lock",
                color_scheme="gold",
                priority_badge="hot",
            ),
            fulfillment_mode=FulfillmentMode.EMAIL_TO_BANKER,
            fulfillment_intent_id="open_fixed_deposit",
            priority=85,
            is_promotional=True,
            promotion_end=datetime.utcnow() + timedelta(days=90),
            trigger_conditions=[
                {"type": "balance_threshold", "min_idle_balance": 20000, "idle_days": 60},
                {"type": "segment", "segments": ["premium", "senior"]},
            ],
        ))

        # ========== LOAN OFFERINGS ==========

        # Personal Loan - Pre-approved
        offerings.append(Offering(
            offering_id="loan-personal-preapproved-001",
            name="הלוואה אישית מאושרת מראש",
            category=OfferingCategory.LOANS,
            offering_type=OfferingType.PERSONAL_LOAN,
            eligibility=EligibilityCriteria(
                min_age=21,
                max_age=67,
                min_account_age_months=6,
                min_credit_score=650,
                max_debt_ratio=0.4,
                target_segments=["standard", "premium", "young_professional"],
            ),
            terms=OfferingTerms(
                interest_rate=Decimal("5.9"),
                interest_rate_type="fixed",
                min_amount=Decimal("5000"),
                max_amount=Decimal("100000"),
                min_term_months=12,
                max_term_months=60,
                setup_fee=Decimal("0"),
            ),
            presentation=OfferingPresentation(
                title_he="הלוואה מאושרת מראש עד 100,000 ₪",
                subtitle_he="ריבית מועדפת של 5.9% בלבד",
                description_he="בהתבסס על הפרופיל שלך, אושרה לך הלוואה בתנאים מועדפים. ללא עמלת פתיחה!",
                benefits_he=[
                    "אישור מיידי",
                    "ריבית מועדפת 5.9%",
                    "ללא עמלת פתיחה",
                    "החזר גמיש עד 60 חודשים",
                ],
                call_to_action_he="לקבל את ההלוואה",
                title_en="Pre-Approved Loan up to ₪100,000",
                subtitle_en="Preferred rate of just 5.9%",
                description_en="Based on your profile, you're pre-approved for a loan with preferred terms. No setup fee!",
                benefits_en=[
                    "Instant approval",
                    "5.9% preferred rate",
                    "No setup fee",
                    "Flexible repayment up to 60 months",
                ],
                call_to_action_en="Get the loan",
                icon="money",
                color_scheme="purple",
                priority_badge="limited",
            ),
            fulfillment_mode=FulfillmentMode.EMAIL_TO_BANKER,
            fulfillment_intent_id="apply_personal_loan",
            priority=80,
            trigger_conditions=[
                {"type": "credit_event", "event": "credit_check_passed"},
                {"type": "time_based", "days_since_last_loan_offer": 90},
            ],
        ))

        # Overdraft Facility
        offerings.append(Offering(
            offering_id="loan-overdraft-001",
            name="מסגרת אשראי",
            category=OfferingCategory.LOANS,
            offering_type=OfferingType.OVERDRAFT,
            eligibility=EligibilityCriteria(
                min_age=21,
                min_account_age_months=3,
                min_monthly_income=Decimal("8000"),
            ),
            terms=OfferingTerms(
                interest_rate=Decimal("8.9"),
                credit_limit=Decimal("20000"),
            ),
            presentation=OfferingPresentation(
                title_he="מסגרת אשראי גמישה",
                subtitle_he="כרית ביטחון לכל מצב",
                description_he="קבלו מסגרת אשראי של עד 20,000 ₪ לשימוש בעת הצורך.",
                benefits_he=[
                    "זמין בכל עת",
                    "משלמים רק על השימוש",
                    "אין עמלת התחייבות",
                ],
                call_to_action_he="להגדיל את המסגרת",
                title_en="Flexible Overdraft",
                subtitle_en="Safety cushion for any situation",
                description_en="Get an overdraft facility of up to ₪20,000 available when you need it.",
                benefits_en=[
                    "Available anytime",
                    "Pay only for usage",
                    "No commitment fee",
                ],
                call_to_action_en="Increase my limit",
                icon="shield",
                color_scheme="orange",
            ),
            fulfillment_mode=FulfillmentMode.EMAIL_TO_BANKER,
            fulfillment_intent_id="apply_overdraft",
            priority=60,
            trigger_conditions=[
                {"type": "balance_event", "event": "low_balance_alert"},
                {"type": "behavior", "pattern": "end_of_month_stress"},
            ],
        ))

        # ========== CREDIT CARD OFFERINGS ==========

        # Cashback Card
        offerings.append(Offering(
            offering_id="card-cashback-001",
            name="כרטיס קאשבק",
            category=OfferingCategory.CREDIT_CARDS,
            offering_type=OfferingType.CASHBACK_CARD,
            eligibility=EligibilityCriteria(
                min_age=21,
                min_monthly_income=Decimal("6000"),
                excluded_product_holdings=["cashback_card"],
            ),
            terms=OfferingTerms(
                annual_fee=Decimal("0"),
                cashback_rate=Decimal("1.5"),
                credit_limit=Decimal("15000"),
            ),
            presentation=OfferingPresentation(
                title_he="כרטיס קאשבק 1.5%",
                subtitle_he="קבלו כסף חזרה על כל קנייה",
                description_he="קבלו 1.5% חזרה על כל הקניות שלכם. ללא דמי כרטיס לשנה הראשונה!",
                benefits_he=[
                    "1.5% קאשבק על הכל",
                    "ללא דמי כרטיס בשנה הראשונה",
                    "העברת קאשבק אוטומטית לחשבון",
                ],
                call_to_action_he="להנפיק כרטיס קאשבק",
                title_en="1.5% Cashback Card",
                subtitle_en="Get money back on every purchase",
                description_en="Get 1.5% back on all your purchases. No annual fee for the first year!",
                benefits_en=[
                    "1.5% cashback on everything",
                    "No annual fee first year",
                    "Automatic cashback transfer to account",
                ],
                call_to_action_en="Get cashback card",
                icon="credit-card",
                color_scheme="teal",
            ),
            fulfillment_mode=FulfillmentMode.EMAIL_TO_BANKER,
            fulfillment_intent_id="apply_credit_card",
            priority=75,
            trigger_conditions=[
                {"type": "behavior", "pattern": "high_spending"},
                {"type": "product_gap", "missing_product": "cashback_card"},
            ],
        ))

        # ========== INVESTMENT OFFERINGS ==========

        # Pension Fund Enhancement
        offerings.append(Offering(
            offering_id="invest-pension-001",
            name="שדרוג קרן פנסיה",
            category=OfferingCategory.INVESTMENTS,
            offering_type=OfferingType.PENSION_FUND,
            eligibility=EligibilityCriteria(
                min_age=25,
                max_age=55,
                min_monthly_income=Decimal("10000"),
                target_segments=["young_professional", "standard", "premium"],
            ),
            terms=OfferingTerms(
                monthly_fee=Decimal("0"),
            ),
            presentation=OfferingPresentation(
                title_he="בדיקת קרן פנסיה חינם",
                subtitle_he="האם אתם מפסידים כסף?",
                description_he="בדיקה חינם של קרן הפנסיה שלכם מול הקרנות המובילות בשוק.",
                benefits_he=[
                    "בדיקה חינם וללא התחייבות",
                    "השוואה מול קרנות מובילות",
                    "ייעוץ אישי",
                ],
                call_to_action_he="לבדוק את הפנסיה שלי",
                title_en="Free Pension Check",
                subtitle_en="Are you losing money?",
                description_en="Free comparison of your pension fund against market leaders.",
                benefits_en=[
                    "Free, no obligation check",
                    "Comparison with leading funds",
                    "Personal advisory",
                ],
                call_to_action_en="Check my pension",
                icon="trending-up",
                color_scheme="indigo",
            ),
            fulfillment_mode=FulfillmentMode.EMAIL_TO_BANKER,
            fulfillment_intent_id="pension_review",
            priority=65,
            trigger_conditions=[
                {"type": "time_based", "months_since_pension_review": 24},
                {"type": "life_event", "event": "salary_increase"},
            ],
        ))

        return offerings

    # ========== CRUD Operations ==========

    def save(self, offering: Offering) -> bool:
        """Save an offering to the repository."""
        offering.updated_at = datetime.utcnow()

        if self.use_dynamodb:
            try:
                self.table.put_item(Item=offering.to_dict())
                return True
            except ClientError as e:
                logger.error(f"Failed to save offering: {e}")
                return False
        else:
            self._memory_store[offering.offering_id] = offering
            return True

    def get(self, offering_id: str) -> Optional[Offering]:
        """Get an offering by ID."""
        if self.use_dynamodb:
            try:
                response = self.table.get_item(Key={"offering_id": offering_id})
                if "Item" in response:
                    return self._dict_to_offering(response["Item"])
                return None
            except ClientError as e:
                logger.error(f"Failed to get offering: {e}")
                return None
        else:
            return self._memory_store.get(offering_id)

    def get_all(self, active_only: bool = True) -> List[Offering]:
        """Get all offerings."""
        if self.use_dynamodb:
            try:
                if active_only:
                    response = self.table.scan(
                        FilterExpression="is_active = :active",
                        ExpressionAttributeValues={":active": True},
                    )
                else:
                    response = self.table.scan()

                return [
                    self._dict_to_offering(item)
                    for item in response.get("Items", [])
                ]
            except ClientError as e:
                logger.error(f"Failed to get offerings: {e}")
                return []
        else:
            offerings = list(self._memory_store.values())
            if active_only:
                offerings = [o for o in offerings if o.is_active]
            return offerings

    def get_by_category(
        self,
        category: OfferingCategory,
        active_only: bool = True,
    ) -> List[Offering]:
        """Get offerings by category."""
        all_offerings = self.get_all(active_only=active_only)
        return [o for o in all_offerings if o.category == category]

    def get_by_type(
        self,
        offering_type: OfferingType,
        active_only: bool = True,
    ) -> List[Offering]:
        """Get offerings by type."""
        all_offerings = self.get_all(active_only=active_only)
        return [o for o in all_offerings if o.offering_type == offering_type]

    def get_promotional(self) -> List[Offering]:
        """Get active promotional offerings."""
        all_offerings = self.get_all(active_only=True)
        return [
            o for o in all_offerings
            if o.is_promotional and o.is_promotion_active()
        ]

    def delete(self, offering_id: str) -> bool:
        """Delete an offering."""
        if self.use_dynamodb:
            try:
                self.table.delete_item(Key={"offering_id": offering_id})
                return True
            except ClientError as e:
                logger.error(f"Failed to delete offering: {e}")
                return False
        else:
            if offering_id in self._memory_store:
                del self._memory_store[offering_id]
                return True
            return False

    def update_analytics(
        self,
        offering_id: str,
        impressions: int = 0,
        consents: int = 0,
        fulfillments: int = 0,
    ) -> bool:
        """Update offering analytics."""
        offering = self.get(offering_id)
        if not offering:
            return False

        offering.total_impressions += impressions
        offering.total_consents += consents
        offering.total_fulfillments += fulfillments

        return self.save(offering)

    def _dict_to_offering(self, data: Dict[str, Any]) -> Offering:
        """Convert dictionary to Offering object."""
        # Parse eligibility
        eligibility_data = data.get("eligibility", {})
        eligibility = EligibilityCriteria(
            min_age=eligibility_data.get("min_age"),
            max_age=eligibility_data.get("max_age"),
            min_account_age_months=eligibility_data.get("min_account_age_months"),
            required_account_types=eligibility_data.get("required_account_types", []),
            excluded_account_types=eligibility_data.get("excluded_account_types", []),
            min_balance=Decimal(eligibility_data["min_balance"]) if eligibility_data.get("min_balance") else None,
            max_balance=Decimal(eligibility_data["max_balance"]) if eligibility_data.get("max_balance") else None,
            min_monthly_income=Decimal(eligibility_data["min_monthly_income"]) if eligibility_data.get("min_monthly_income") else None,
            min_credit_score=eligibility_data.get("min_credit_score"),
            max_debt_ratio=eligibility_data.get("max_debt_ratio"),
            min_monthly_transactions=eligibility_data.get("min_monthly_transactions"),
            required_product_holdings=eligibility_data.get("required_product_holdings", []),
            excluded_product_holdings=eligibility_data.get("excluded_product_holdings", []),
            target_segments=eligibility_data.get("target_segments", []),
            excluded_segments=eligibility_data.get("excluded_segments", []),
            custom_conditions=eligibility_data.get("custom_conditions", []),
        )

        # Parse terms
        terms_data = data.get("terms", {})
        terms = OfferingTerms(
            interest_rate=Decimal(terms_data["interest_rate"]) if terms_data.get("interest_rate") else None,
            interest_rate_type=terms_data.get("interest_rate_type", "fixed"),
            bonus_rate=Decimal(terms_data["bonus_rate"]) if terms_data.get("bonus_rate") else None,
            bonus_rate_duration_months=terms_data.get("bonus_rate_duration_months"),
            min_term_months=terms_data.get("min_term_months"),
            max_term_months=terms_data.get("max_term_months"),
            lock_in_period_months=terms_data.get("lock_in_period_months"),
            min_amount=Decimal(terms_data["min_amount"]) if terms_data.get("min_amount") else None,
            max_amount=Decimal(terms_data["max_amount"]) if terms_data.get("max_amount") else None,
            setup_fee=Decimal(terms_data["setup_fee"]) if terms_data.get("setup_fee") else None,
            monthly_fee=Decimal(terms_data["monthly_fee"]) if terms_data.get("monthly_fee") else None,
            annual_fee=Decimal(terms_data["annual_fee"]) if terms_data.get("annual_fee") else None,
            credit_limit=Decimal(terms_data["credit_limit"]) if terms_data.get("credit_limit") else None,
            cashback_rate=Decimal(terms_data["cashback_rate"]) if terms_data.get("cashback_rate") else None,
        )

        # Parse presentation
        pres_data = data.get("presentation", {})
        presentation = OfferingPresentation(
            title_he=pres_data.get("title_he", ""),
            subtitle_he=pres_data.get("subtitle_he", ""),
            description_he=pres_data.get("description_he", ""),
            benefits_he=pres_data.get("benefits_he", []),
            call_to_action_he=pres_data.get("call_to_action_he", ""),
            title_en=pres_data.get("title_en", ""),
            subtitle_en=pres_data.get("subtitle_en", ""),
            description_en=pres_data.get("description_en", ""),
            benefits_en=pres_data.get("benefits_en", []),
            call_to_action_en=pres_data.get("call_to_action_en", ""),
            icon=pres_data.get("icon", ""),
            color_scheme=pres_data.get("color_scheme", "default"),
            priority_badge=pres_data.get("priority_badge"),
            personalized_message_template=pres_data.get("personalized_message_template", ""),
        )

        return Offering(
            offering_id=data["offering_id"],
            name=data["name"],
            category=OfferingCategory(data["category"]),
            offering_type=OfferingType(data["offering_type"]),
            eligibility=eligibility,
            terms=terms,
            presentation=presentation,
            fulfillment_mode=FulfillmentMode(data.get("fulfillment_mode", "email_to_banker")),
            fulfillment_intent_id=data.get("fulfillment_intent_id"),
            banker_action_required=data.get("banker_action_required", True),
            priority=data.get("priority", 0),
            is_promotional=data.get("is_promotional", False),
            promotion_start=datetime.fromisoformat(data["promotion_start"]) if data.get("promotion_start") else None,
            promotion_end=datetime.fromisoformat(data["promotion_end"]) if data.get("promotion_end") else None,
            trigger_conditions=data.get("trigger_conditions", []),
            is_active=data.get("is_active", True),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            total_impressions=data.get("total_impressions", 0),
            total_consents=data.get("total_consents", 0),
            total_fulfillments=data.get("total_fulfillments", 0),
        )
