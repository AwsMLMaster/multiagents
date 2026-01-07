"""
Financial Insights Generator

Main orchestrator that generates financial insights by:
1. Analyzing transaction data
2. Detecting patterns
3. Generating insights
4. Creating recommendations
"""

import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .models import (
    Insight,
    InsightType,
    InsightCategory,
    InsightSeverity,
    InsightConfig,
    CustomerInsightProfile,
    DetectedPattern,
    PatternType,
)
from .patterns import PatternDetector, TransactionAnalyzer, Transaction
from .recommendations import RecommendationEngine, RecommendationContext

logger = logging.getLogger(__name__)


@dataclass
class InsightGenerationRequest:
    """Request for generating insights."""
    customer_id: str
    transactions: List[Transaction]
    historical_transactions: Optional[List[Transaction]] = None
    current_balance: Decimal = Decimal("0")
    account_id: Optional[str] = None
    config: Optional[InsightConfig] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class InsightGenerationResult:
    """Result of insight generation."""
    insights: List[Insight]
    patterns_detected: int
    generation_time_ms: float
    filtered_count: int  # Insights filtered due to config/dedup
    errors: List[str]


class FinancialInsightsGenerator:
    """
    Generates personalized financial insights for customers.

    The generator:
    1. Analyzes recent transactions
    2. Compares with historical data
    3. Detects patterns and anomalies
    4. Generates relevant insights
    5. Attaches actionable recommendations
    """

    def __init__(
        self,
        default_config: Optional[InsightConfig] = None,
    ):
        self.default_config = default_config or InsightConfig()
        self.pattern_detector = PatternDetector(self.default_config)
        self.transaction_analyzer = TransactionAnalyzer(self.default_config)
        self.recommendation_engine = RecommendationEngine()

        # Customer profiles cache
        self._profiles: Dict[str, CustomerInsightProfile] = {}

    async def generate_insights(
        self,
        request: InsightGenerationRequest,
    ) -> InsightGenerationResult:
        """Generate insights for a customer."""
        start_time = datetime.utcnow()
        errors = []
        insights = []
        filtered_count = 0

        config = request.config or self.default_config
        profile = self._get_or_create_profile(request.customer_id, config)

        try:
            # Analyze transactions
            analysis = self.transaction_analyzer.analyze(
                request.transactions,
                request.historical_transactions,
            )

            # Detect patterns
            patterns = self.pattern_detector.detect_all_patterns(
                request.transactions,
                request.historical_transactions,
            )

            # Detect subscriptions specifically
            subscription_patterns = self.pattern_detector.detect_subscription_patterns(
                request.transactions
            )
            patterns.extend(subscription_patterns)

            # Generate insights from analysis
            analysis_insights = self._generate_analysis_insights(
                analysis, request, config
            )
            insights.extend(analysis_insights)

            # Generate insights from patterns
            pattern_insights = self._generate_pattern_insights(
                patterns, request, config
            )
            insights.extend(pattern_insights)

            # Generate balance-based insights
            balance_insights = self._generate_balance_insights(
                request, config
            )
            insights.extend(balance_insights)

            # Filter and deduplicate
            original_count = len(insights)
            insights = self._filter_insights(insights, profile, config)
            filtered_count = original_count - len(insights)

            # Add recommendations to each insight
            rec_context = RecommendationContext(
                customer_id=request.customer_id,
                current_balance=request.current_balance,
            )

            for insight in insights:
                recommendations = self.recommendation_engine.generate_recommendations(
                    insight, rec_context
                )
                insight.recommendations = recommendations

            # Sort by severity and relevance
            insights = self._sort_insights(insights)

            # Limit to max per session
            insights = insights[:config.max_insights_per_session]

            # Update profile
            profile.total_insights_generated += len(insights)
            for insight in insights:
                profile.recent_insight_types[insight.insight_type.value] = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            errors.append(str(e))

        generation_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return InsightGenerationResult(
            insights=insights,
            patterns_detected=len(patterns) if 'patterns' in dir() else 0,
            generation_time_ms=generation_time,
            filtered_count=filtered_count,
            errors=errors,
        )

    def _generate_analysis_insights(
        self,
        analysis: Any,
        request: InsightGenerationRequest,
        config: InsightConfig,
    ) -> List[Insight]:
        """Generate insights from transaction analysis."""
        insights = []
        stats = analysis.statistics

        if not stats:
            return insights

        # Check for category overspending
        if "comparison" in stats and config.enable_spending_insights:
            category_changes = stats["comparison"].get("category_changes", [])
            for change in category_changes:
                if change["change_pct"] > 50:  # 50% increase
                    insights.append(Insight(
                        insight_id=str(uuid.uuid4()),
                        insight_type=InsightType.CATEGORY_OVERSPEND,
                        category=InsightCategory.SPENDING,
                        severity=InsightSeverity.IMPORTANT if change["change_pct"] > 100 else InsightSeverity.SUGGESTION,
                        title_he=f"עלייה בהוצאות על {change['category']}",
                        title_en=f"Spending increase on {change['category']}",
                        summary_he=f"ההוצאות על {change['category']} עלו ב-{change['change_pct']:.0f}% לעומת החודש הקודם",
                        summary_en=f"Spending on {change['category']} increased {change['change_pct']:.0f}% vs last month",
                        amount=Decimal(str(change["current"])),
                        comparison_amount=Decimal(str(change["historical"])),
                        percentage_change=change["change_pct"],
                        category_name=change["category"],
                        confidence=0.9,
                    ))

        # Overall spending change
        if "comparison" in stats:
            spending_change = stats["comparison"].get("spending_change_pct")
            if spending_change and abs(spending_change) > 20:
                is_increase = spending_change > 0
                insights.append(Insight(
                    insight_id=str(uuid.uuid4()),
                    insight_type=InsightType.SPENDING_SPIKE if is_increase else InsightType.POSITIVE_TREND,
                    category=InsightCategory.SPENDING if is_increase else InsightCategory.SAVINGS,
                    severity=InsightSeverity.IMPORTANT if is_increase else InsightSeverity.INFO,
                    title_he="עלייה בהוצאות הכלליות" if is_increase else "ירידה בהוצאות",
                    title_en="Overall spending increase" if is_increase else "Spending decrease",
                    summary_he=f"ההוצאות הכלליות {'עלו' if is_increase else 'ירדו'} ב-{abs(spending_change):.0f}%",
                    summary_en=f"Overall spending {'increased' if is_increase else 'decreased'} by {abs(spending_change):.0f}%",
                    percentage_change=spending_change,
                    confidence=0.85,
                ))

        # Top spending categories insight
        if stats.get("top_categories") and config.enable_spending_insights:
            top_cat = stats["top_categories"][0]
            total_spending = float(stats.get("total_outgoing", 0))
            if total_spending > 0:
                cat_pct = (float(top_cat[1]) / total_spending) * 100
                if cat_pct > 30:  # More than 30% in one category
                    insights.append(Insight(
                        insight_id=str(uuid.uuid4()),
                        insight_type=InsightType.CATEGORY_OVERSPEND,
                        category=InsightCategory.SPENDING,
                        severity=InsightSeverity.INFO,
                        title_he=f"רוב ההוצאות שלך על {top_cat[0]}",
                        title_en=f"Most spending on {top_cat[0]}",
                        summary_he=f"{cat_pct:.0f}% מההוצאות שלך החודש הלכו ל{top_cat[0]}",
                        summary_en=f"{cat_pct:.0f}% of your spending this month went to {top_cat[0]}",
                        amount=top_cat[1],
                        percentage_change=cat_pct,
                        category_name=top_cat[0],
                        confidence=0.95,
                    ))

        return insights

    def _generate_pattern_insights(
        self,
        patterns: List[DetectedPattern],
        request: InsightGenerationRequest,
        config: InsightConfig,
    ) -> List[Insight]:
        """Generate insights from detected patterns."""
        insights = []

        for pattern in patterns:
            if pattern.confidence < config.min_confidence_threshold:
                continue

            if pattern.pattern_type == PatternType.RECURRING:
                if pattern.metadata.get("is_subscription"):
                    insights.append(Insight(
                        insight_id=str(uuid.uuid4()),
                        insight_type=InsightType.NEW_SUBSCRIPTION,
                        category=InsightCategory.SUBSCRIPTIONS,
                        severity=InsightSeverity.INFO,
                        title_he=f"מנוי זוהה: {pattern.merchant_or_category}",
                        title_en=f"Subscription detected: {pattern.merchant_or_category}",
                        summary_he=f"זיהינו תשלום חוזר ל-{pattern.merchant_or_category} בסך {pattern.average_amount} ₪",
                        summary_en=f"Detected recurring payment to {pattern.merchant_or_category} of ₪{pattern.average_amount}",
                        amount=pattern.average_amount,
                        merchant_name=pattern.merchant_or_category,
                        detected_pattern=pattern,
                        confidence=pattern.confidence,
                    ))

            elif pattern.pattern_type == PatternType.ANOMALY:
                if pattern.metadata.get("is_new_payee"):
                    insights.append(Insight(
                        insight_id=str(uuid.uuid4()),
                        insight_type=InsightType.NEW_PAYEE,
                        category=InsightCategory.TRANSFERS,
                        severity=InsightSeverity.IMPORTANT,
                        title_he="העברה למוטב חדש",
                        title_en="Transfer to new payee",
                        summary_he=f"זיהינו העברה ראשונה לחשבון חדש בסך {pattern.average_amount} ₪",
                        summary_en=f"First transfer to new account of ₪{pattern.average_amount}",
                        amount=pattern.average_amount,
                        detected_pattern=pattern,
                        confidence=pattern.confidence,
                    ))
                elif pattern.metadata.get("is_new_merchant"):
                    insights.append(Insight(
                        insight_id=str(uuid.uuid4()),
                        insight_type=InsightType.FIRST_TIME_MERCHANT,
                        category=InsightCategory.SPENDING,
                        severity=InsightSeverity.INFO,
                        title_he=f"קנייה ראשונה ב-{pattern.merchant_or_category}",
                        title_en=f"First purchase at {pattern.merchant_or_category}",
                        summary_he=f"זו הפעם הראשונה שקנית ב-{pattern.merchant_or_category}",
                        summary_en=f"This is your first purchase at {pattern.merchant_or_category}",
                        amount=pattern.average_amount,
                        merchant_name=pattern.merchant_or_category,
                        detected_pattern=pattern,
                        confidence=pattern.confidence,
                    ))
                else:
                    # General anomaly (unusual amount)
                    z_score = pattern.metadata.get("z_score", 0)
                    if abs(z_score) > 2:
                        insights.append(Insight(
                            insight_id=str(uuid.uuid4()),
                            insight_type=InsightType.UNUSUAL_SPENDING,
                            category=InsightCategory.SPENDING,
                            severity=InsightSeverity.IMPORTANT,
                            title_he=f"הוצאה חריגה ב{pattern.merchant_or_category}",
                            title_en=f"Unusual spending in {pattern.merchant_or_category}",
                            summary_he=f"הסכום גבוה באופן חריג מהממוצע שלך בקטגוריה זו",
                            summary_en=f"Amount is unusually high compared to your average in this category",
                            amount=Decimal(str(pattern.metadata.get("actual_amount", 0))),
                            comparison_amount=Decimal(str(pattern.metadata.get("category_average", 0))),
                            category_name=pattern.merchant_or_category,
                            detected_pattern=pattern,
                            confidence=pattern.confidence,
                        ))

            elif pattern.pattern_type == PatternType.TRENDING_UP:
                insights.append(Insight(
                    insight_id=str(uuid.uuid4()),
                    insight_type=InsightType.SPENDING_SPIKE,
                    category=InsightCategory.SPENDING,
                    severity=InsightSeverity.SUGGESTION,
                    title_he=f"מגמת עלייה ב{pattern.merchant_or_category}",
                    title_en=f"Upward trend in {pattern.merchant_or_category}",
                    summary_he=pattern.description,
                    summary_en=pattern.description,
                    percentage_change=pattern.metadata.get("change_percentage"),
                    category_name=pattern.merchant_or_category,
                    detected_pattern=pattern,
                    confidence=pattern.confidence,
                ))

        return insights

    def _generate_balance_insights(
        self,
        request: InsightGenerationRequest,
        config: InsightConfig,
    ) -> List[Insight]:
        """Generate balance-based insights."""
        insights = []

        if not config.enable_savings_insights:
            return insights

        # Idle balance insight
        if request.current_balance >= config.idle_balance_threshold:
            # Check if balance has been stable (would need historical balance data)
            insights.append(Insight(
                insight_id=str(uuid.uuid4()),
                insight_type=InsightType.IDLE_BALANCE,
                category=InsightCategory.SAVINGS,
                severity=InsightSeverity.SUGGESTION,
                title_he="יש לך יתרה פנויה בחשבון",
                title_en="You have idle balance",
                summary_he=f"יש לך {request.current_balance:,.0f} ₪ ביתרה. שקול להעביר לחיסכון ולהרוויח ריבית",
                summary_en=f"You have ₪{request.current_balance:,.0f} available. Consider saving to earn interest",
                amount=request.current_balance,
                account_id=request.account_id,
                confidence=0.85,
                relevance_score=0.9,
            ))

        # Low balance prediction (simplified)
        if request.current_balance < config.low_balance_threshold:
            insights.append(Insight(
                insight_id=str(uuid.uuid4()),
                insight_type=InsightType.LOW_BALANCE_PREDICTION,
                category=InsightCategory.CASH_FLOW,
                severity=InsightSeverity.IMPORTANT,
                title_he="יתרה נמוכה",
                title_en="Low balance",
                summary_he=f"היתרה הנוכחית שלך היא {request.current_balance:,.0f} ₪ בלבד",
                summary_en=f"Your current balance is only ₪{request.current_balance:,.0f}",
                amount=request.current_balance,
                account_id=request.account_id,
                confidence=0.95,
                relevance_score=1.0,
            ))

        return insights

    def _filter_insights(
        self,
        insights: List[Insight],
        profile: CustomerInsightProfile,
        config: InsightConfig,
    ) -> List[Insight]:
        """Filter insights based on config and deduplication."""
        filtered = []

        for insight in insights:
            # Check category enabled
            if insight.category not in config.enabled_categories:
                continue

            # Check severity
            severity_order = [s for s in InsightSeverity]
            if severity_order.index(insight.severity) < severity_order.index(config.min_severity):
                continue

            # Check confidence
            if insight.confidence < config.min_confidence_threshold:
                continue

            # Check cooldown (don't repeat same type within window)
            last_shown = profile.recent_insight_types.get(insight.insight_type.value)
            if last_shown:
                hours_since = (datetime.utcnow() - last_shown).total_seconds() / 3600
                if hours_since < config.insight_cooldown_hours:
                    continue

            # Check if dismissed
            if insight.insight_type.value in profile.dismissed_insight_types:
                continue

            filtered.append(insight)

        return filtered

    def _sort_insights(self, insights: List[Insight]) -> List[Insight]:
        """Sort insights by severity and relevance."""
        severity_order = {
            InsightSeverity.ALERT: 5,
            InsightSeverity.URGENT: 4,
            InsightSeverity.IMPORTANT: 3,
            InsightSeverity.SUGGESTION: 2,
            InsightSeverity.INFO: 1,
        }

        return sorted(
            insights,
            key=lambda i: (
                severity_order.get(i.severity, 0),
                i.relevance_score,
                i.confidence,
            ),
            reverse=True,
        )

    def _get_or_create_profile(
        self,
        customer_id: str,
        config: InsightConfig,
    ) -> CustomerInsightProfile:
        """Get or create customer insight profile."""
        if customer_id not in self._profiles:
            self._profiles[customer_id] = CustomerInsightProfile(
                customer_id=customer_id,
                config=config,
            )
        return self._profiles[customer_id]

    async def dismiss_insight(
        self,
        customer_id: str,
        insight_id: str,
        insight_type: InsightType,
        permanently: bool = False,
    ) -> None:
        """Mark an insight as dismissed."""
        profile = self._profiles.get(customer_id)
        if profile and permanently:
            if insight_type.value not in profile.dismissed_insight_types:
                profile.dismissed_insight_types.append(insight_type.value)

    async def mark_insight_read(
        self,
        customer_id: str,
        insight_id: str,
    ) -> None:
        """Mark an insight as read."""
        profile = self._profiles.get(customer_id)
        if profile:
            profile.total_insights_read += 1

    async def mark_recommendation_followed(
        self,
        customer_id: str,
        insight_id: str,
        recommendation_id: str,
    ) -> None:
        """Mark a recommendation as followed."""
        profile = self._profiles.get(customer_id)
        if profile:
            profile.total_recommendations_followed += 1
            profile.last_recommendation_followed_at = datetime.utcnow()
