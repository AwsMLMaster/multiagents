"""
Recommendation Engine

Generates actionable recommendations based on detected insights and patterns.
"""

import logging
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .models import (
    Insight,
    InsightType,
    InsightCategory,
    InsightRecommendation,
    DetectedPattern,
    PatternType,
)

logger = logging.getLogger(__name__)


@dataclass
class RecommendationContext:
    """Context for generating recommendations."""
    customer_id: str
    current_balance: Decimal = Decimal("0")
    monthly_income: Optional[Decimal] = None
    has_savings_account: bool = False
    has_investment_account: bool = False
    existing_products: List[str] = None
    risk_tolerance: str = "moderate"  # conservative, moderate, aggressive
    preferred_language: str = "he"


class RecommendationEngine:
    """
    Generates actionable recommendations based on insights.

    Recommendations are tied to:
    - Bank offerings (for upsell/cross-sell)
    - User actions (alerts, budgets, transfers)
    - Educational content
    """

    def __init__(self):
        # Recommendation templates by insight type
        self.templates = self._build_templates()

    def generate_recommendations(
        self,
        insight: Insight,
        context: RecommendationContext,
    ) -> List[InsightRecommendation]:
        """Generate recommendations for an insight."""
        recommendations = []

        # Get base recommendations from templates
        template_recs = self.templates.get(insight.insight_type, [])
        for template in template_recs:
            rec = self._apply_template(template, insight, context)
            if rec and self._is_applicable(rec, context):
                recommendations.append(rec)

        # Add pattern-based recommendations
        if insight.detected_pattern:
            pattern_recs = self._generate_pattern_recommendations(
                insight.detected_pattern, context
            )
            recommendations.extend(pattern_recs)

        # Sort by priority and limit
        recommendations.sort(key=lambda r: r.priority, reverse=True)
        return recommendations[:3]  # Max 3 recommendations per insight

    def _build_templates(self) -> Dict[InsightType, List[Dict[str, Any]]]:
        """Build recommendation templates for each insight type."""
        return {
            # Idle balance recommendations
            InsightType.IDLE_BALANCE: [
                {
                    "title_he": "העבר לחיסכון בריבית גבוהה",
                    "title_en": "Transfer to high-yield savings",
                    "description_he": "העבר את היתרה הפנויה לחשבון חיסכון והרוויח ריבית",
                    "description_en": "Transfer idle funds to savings account and earn interest",
                    "action_type": "transfer_to_savings",
                    "related_offering_id": "savings-high-yield-001",
                    "priority": 90,
                },
                {
                    "title_he": "פתח פיקדון לטווח קצר",
                    "title_en": "Open short-term deposit",
                    "description_he": "נעל את הכסף בפיקדון לתקופה קצרה עם ריבית מובטחת",
                    "description_en": "Lock money in deposit for guaranteed interest",
                    "action_type": "open_deposit",
                    "related_offering_id": "deposit-fixed-001",
                    "priority": 80,
                },
            ],

            # Unusual spending recommendations
            InsightType.UNUSUAL_SPENDING: [
                {
                    "title_he": "הגדר התראת תקציב",
                    "title_en": "Set budget alert",
                    "description_he": "הגדר התראה כשההוצאות בקטגוריה זו חורגות מהרגיל",
                    "description_en": "Set alert when spending in this category exceeds normal",
                    "action_type": "set_budget_alert",
                    "priority": 70,
                },
                {
                    "title_he": "בדוק את הפעולה",
                    "title_en": "Review transaction",
                    "description_he": "ודא שהפעולה נראית לך מוכרת ותקינה",
                    "description_en": "Verify the transaction looks familiar and correct",
                    "action_type": "review_transaction",
                    "priority": 85,
                },
            ],

            # New payee recommendations
            InsightType.NEW_PAYEE: [
                {
                    "title_he": "הוסף לרשימת המוטבים",
                    "title_en": "Add to beneficiaries",
                    "description_he": "שמור את המוטב להעברות עתידיות",
                    "description_en": "Save beneficiary for future transfers",
                    "action_type": "save_beneficiary",
                    "priority": 60,
                },
                {
                    "title_he": "הגדר העברה קבועה",
                    "title_en": "Set up recurring transfer",
                    "description_he": "אם זו העברה קבועה, הגדר הוראת קבע",
                    "description_en": "If this is regular, set up standing order",
                    "action_type": "create_standing_order",
                    "priority": 50,
                },
            ],

            # Large transfer recommendations
            InsightType.LARGE_TRANSFER: [
                {
                    "title_he": "בדוק את הפרטים",
                    "title_en": "Verify details",
                    "description_he": "ודא שפרטי ההעברה נכונים לפני האישור",
                    "description_en": "Verify transfer details before confirming",
                    "action_type": "verify_transfer",
                    "priority": 95,
                },
            ],

            # Subscription insights
            InsightType.NEW_SUBSCRIPTION: [
                {
                    "title_he": "עקוב אחרי המנוי",
                    "title_en": "Track subscription",
                    "description_he": "הוסף את המנוי למעקב כדי לקבל התראות על חידושים",
                    "description_en": "Add subscription to tracking for renewal alerts",
                    "action_type": "track_subscription",
                    "priority": 65,
                },
            ],

            InsightType.UNUSED_SUBSCRIPTION: [
                {
                    "title_he": "שקול לבטל את המנוי",
                    "title_en": "Consider cancelling",
                    "description_he": "נראה שלא השתמשת במנוי זה. שקול לבטל ולחסוך כסף",
                    "description_en": "Looks like you haven't used this. Consider cancelling to save",
                    "action_type": "review_subscription",
                    "priority": 75,
                },
            ],

            # Avoidable fee recommendations
            InsightType.AVOIDABLE_FEE: [
                {
                    "title_he": "הימנע מעמלה בפעם הבאה",
                    "title_en": "Avoid fee next time",
                    "description_he": "למד איך להימנע מעמלה זו בעתיד",
                    "description_en": "Learn how to avoid this fee in the future",
                    "action_type": "learn_fee_avoidance",
                    "priority": 70,
                },
                {
                    "title_he": "שדרג את החשבון",
                    "title_en": "Upgrade account",
                    "description_he": "שדרג לחשבון פרימיום וקבל פטור מעמלות",
                    "description_en": "Upgrade to premium account for fee waivers",
                    "action_type": "upgrade_account",
                    "related_offering_id": "account-premium-001",
                    "priority": 60,
                },
            ],

            # Overdraft risk
            InsightType.OVERDRAFT_RISK: [
                {
                    "title_he": "הגדל מסגרת אשראי",
                    "title_en": "Increase credit limit",
                    "description_he": "הגדל את המסגרת כדי להימנע מחריגה",
                    "description_en": "Increase limit to avoid overdraft",
                    "action_type": "request_overdraft",
                    "related_offering_id": "loan-overdraft-001",
                    "priority": 85,
                },
                {
                    "title_he": "העבר כסף מחשבון אחר",
                    "title_en": "Transfer from another account",
                    "description_he": "העבר יתרה מחשבון אחר כדי לכסות את החריגה",
                    "description_en": "Transfer balance from another account to cover",
                    "action_type": "internal_transfer",
                    "priority": 90,
                },
            ],

            # Salary received
            InsightType.SALARY_RECEIVED: [
                {
                    "title_he": "הפרש לחיסכון אוטומטי",
                    "title_en": "Set up auto-save",
                    "description_he": "הגדר הפרשה אוטומטית לחיסכון בכל משכורת",
                    "description_en": "Set up automatic savings transfer each payday",
                    "action_type": "setup_auto_save",
                    "related_offering_id": "savings-goal-001",
                    "priority": 75,
                },
            ],

            # Low balance prediction
            InsightType.LOW_BALANCE_PREDICTION: [
                {
                    "title_he": "תכנן מראש",
                    "title_en": "Plan ahead",
                    "description_he": "צפויה יתרה נמוכה. שקול לדחות הוצאות או להעביר כסף",
                    "description_en": "Low balance expected. Consider postponing expenses or transferring",
                    "action_type": "cash_flow_planning",
                    "priority": 80,
                },
            ],

            # Savings opportunity
            InsightType.SAVINGS_OPPORTUNITY: [
                {
                    "title_he": "נצל את ההזדמנות לחסוך",
                    "title_en": "Take savings opportunity",
                    "description_he": "זה הזמן המושלם להתחיל לחסוך",
                    "description_en": "This is the perfect time to start saving",
                    "action_type": "open_savings",
                    "related_offering_id": "savings-high-yield-001",
                    "priority": 85,
                },
            ],

            # Duplicate charge
            InsightType.DUPLICATE_CHARGE: [
                {
                    "title_he": "בדוק חיוב כפול",
                    "title_en": "Check duplicate charge",
                    "description_he": "זיהינו חיוב שעשוי להיות כפול. בדוק ופנה לבית העסק",
                    "description_en": "We detected a possible duplicate. Check and contact merchant",
                    "action_type": "dispute_charge",
                    "priority": 95,
                },
            ],
        }

    def _apply_template(
        self,
        template: Dict[str, Any],
        insight: Insight,
        context: RecommendationContext,
    ) -> Optional[InsightRecommendation]:
        """Apply template to create recommendation."""
        # Calculate estimated benefit if applicable
        estimated_benefit = None
        estimated_amount = None

        if template.get("action_type") == "transfer_to_savings" and insight.amount:
            # Assume 3% annual interest
            annual_benefit = insight.amount * Decimal("0.03")
            estimated_benefit = f"הרוויח כ-{annual_benefit:,.0f} ₪ בשנה"
            estimated_amount = annual_benefit

        return InsightRecommendation(
            recommendation_id=str(uuid.uuid4()),
            title_he=template["title_he"],
            title_en=template["title_en"],
            description_he=template["description_he"],
            description_en=template["description_en"],
            action_type=template["action_type"],
            action_params={
                "insight_id": insight.insight_id,
                "amount": str(insight.amount) if insight.amount else None,
            },
            related_offering_id=template.get("related_offering_id"),
            estimated_benefit=estimated_benefit,
            estimated_benefit_amount=estimated_amount,
            priority=template.get("priority", 50),
        )

    def _is_applicable(
        self,
        recommendation: InsightRecommendation,
        context: RecommendationContext,
    ) -> bool:
        """Check if recommendation is applicable to customer."""
        # Skip savings recommendations if customer already has savings
        if recommendation.action_type == "transfer_to_savings" and context.has_savings_account:
            # Still applicable, but lower priority
            recommendation.priority -= 20

        # Skip upgrade recommendations if already premium
        if recommendation.action_type == "upgrade_account":
            if context.existing_products and "premium_account" in context.existing_products:
                return False

        return True

    def _generate_pattern_recommendations(
        self,
        pattern: DetectedPattern,
        context: RecommendationContext,
    ) -> List[InsightRecommendation]:
        """Generate recommendations based on detected patterns."""
        recommendations = []

        if pattern.pattern_type == PatternType.RECURRING:
            # Subscription management recommendations
            if pattern.metadata.get("is_subscription"):
                annual_cost = pattern.metadata.get("annual_cost", 0)
                if annual_cost > 500:  # Significant subscription
                    recommendations.append(InsightRecommendation(
                        recommendation_id=str(uuid.uuid4()),
                        title_he="בדוק את שווי המנוי",
                        title_en="Review subscription value",
                        description_he=f"המנוי ל-{pattern.merchant_or_category} עולה כ-{annual_cost:,.0f} ₪ בשנה. האם הוא שווה את זה?",
                        description_en=f"Subscription to {pattern.merchant_or_category} costs ~₪{annual_cost:,.0f}/year. Worth it?",
                        action_type="review_subscription",
                        action_params={
                            "merchant": pattern.merchant_or_category,
                            "annual_cost": annual_cost,
                        },
                        priority=65,
                    ))

        elif pattern.pattern_type == PatternType.TRENDING_UP:
            change_pct = pattern.metadata.get("change_percentage", 0)
            recommendations.append(InsightRecommendation(
                recommendation_id=str(uuid.uuid4()),
                title_he=f"שים לב לעלייה בהוצאות",
                title_en="Note spending increase",
                description_he=f"ההוצאות על {pattern.merchant_or_category} עלו ב-{change_pct:.0f}%. שקול להגדיר תקציב",
                description_en=f"Spending on {pattern.merchant_or_category} increased {change_pct:.0f}%. Consider setting a budget",
                action_type="set_budget",
                action_params={
                    "category": pattern.merchant_or_category,
                },
                priority=70,
            ))

        elif pattern.pattern_type == PatternType.ANOMALY:
            if pattern.metadata.get("is_new_payee"):
                recommendations.append(InsightRecommendation(
                    recommendation_id=str(uuid.uuid4()),
                    title_he="וודא שההעברה מוכרת לך",
                    title_en="Verify transfer is known",
                    description_he="זוהי העברה ראשונה לחשבון זה. ודא שהפרטים נכונים",
                    description_en="First transfer to this account. Verify details are correct",
                    action_type="verify_transfer",
                    priority=85,
                ))

        return recommendations
