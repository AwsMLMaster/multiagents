"""
Pattern Detection for Financial Insights

Analyzes transaction data to detect patterns, anomalies, and trends.
"""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .models import (
    PatternType,
    DetectedPattern,
    InsightConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class Transaction:
    """Transaction data for analysis."""
    transaction_id: str
    date: datetime
    amount: Decimal
    merchant_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_credit: bool = False  # True for incoming, False for outgoing
    account_id: Optional[str] = None
    counterparty_account: Optional[str] = None
    is_recurring: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Result of transaction analysis."""
    patterns: List[DetectedPattern] = field(default_factory=list)
    anomalies: List[Transaction] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class TransactionAnalyzer:
    """
    Analyzes transactions to compute statistics and identify patterns.
    """

    def __init__(self, config: Optional[InsightConfig] = None):
        self.config = config or InsightConfig()

    def analyze(
        self,
        transactions: List[Transaction],
        historical_transactions: Optional[List[Transaction]] = None,
    ) -> AnalysisResult:
        """Perform comprehensive analysis on transactions."""
        if not transactions:
            return AnalysisResult()

        result = AnalysisResult(
            period_start=min(t.date for t in transactions),
            period_end=max(t.date for t in transactions),
        )

        # Basic statistics
        result.statistics = self._compute_statistics(transactions)

        # Compare with historical if available
        if historical_transactions:
            result.statistics["comparison"] = self._compute_comparison(
                transactions, historical_transactions
            )

        return result

    def _compute_statistics(
        self,
        transactions: List[Transaction],
    ) -> Dict[str, Any]:
        """Compute basic statistics from transactions."""
        outgoing = [t for t in transactions if not t.is_credit]
        incoming = [t for t in transactions if t.is_credit]

        outgoing_amounts = [float(t.amount) for t in outgoing]
        incoming_amounts = [float(t.amount) for t in incoming]

        # Spending by category
        category_spending = defaultdict(Decimal)
        for t in outgoing:
            if t.category:
                category_spending[t.category] += t.amount

        # Spending by merchant
        merchant_spending = defaultdict(Decimal)
        for t in outgoing:
            if t.merchant_name:
                merchant_spending[t.merchant_name] += t.amount

        return {
            "total_outgoing": sum(t.amount for t in outgoing),
            "total_incoming": sum(t.amount for t in incoming),
            "net_cash_flow": sum(t.amount for t in incoming) - sum(t.amount for t in outgoing),
            "transaction_count": len(transactions),
            "outgoing_count": len(outgoing),
            "incoming_count": len(incoming),
            "avg_outgoing": mean(outgoing_amounts) if outgoing_amounts else 0,
            "max_outgoing": max(outgoing_amounts) if outgoing_amounts else 0,
            "stdev_outgoing": stdev(outgoing_amounts) if len(outgoing_amounts) > 1 else 0,
            "avg_incoming": mean(incoming_amounts) if incoming_amounts else 0,
            "by_category": dict(category_spending),
            "by_merchant": dict(merchant_spending),
            "top_categories": sorted(
                category_spending.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5],
            "top_merchants": sorted(
                merchant_spending.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5],
        }

    def _compute_comparison(
        self,
        current: List[Transaction],
        historical: List[Transaction],
    ) -> Dict[str, Any]:
        """Compare current period with historical period."""
        current_stats = self._compute_statistics(current)
        historical_stats = self._compute_statistics(historical)

        def safe_pct_change(current_val, historical_val):
            if historical_val == 0:
                return None
            return ((current_val - historical_val) / historical_val) * 100

        return {
            "spending_change_pct": safe_pct_change(
                float(current_stats["total_outgoing"]),
                float(historical_stats["total_outgoing"]),
            ),
            "income_change_pct": safe_pct_change(
                float(current_stats["total_incoming"]),
                float(historical_stats["total_incoming"]),
            ),
            "transaction_count_change": (
                current_stats["transaction_count"] - historical_stats["transaction_count"]
            ),
            "category_changes": self._compare_categories(
                current_stats["by_category"],
                historical_stats["by_category"],
            ),
        }

    def _compare_categories(
        self,
        current: Dict[str, Decimal],
        historical: Dict[str, Decimal],
    ) -> List[Dict[str, Any]]:
        """Compare spending by category."""
        changes = []
        all_categories = set(current.keys()) | set(historical.keys())

        for category in all_categories:
            curr = float(current.get(category, Decimal("0")))
            hist = float(historical.get(category, Decimal("0")))

            if hist > 0:
                pct_change = ((curr - hist) / hist) * 100
            elif curr > 0:
                pct_change = 100.0
            else:
                pct_change = 0.0

            if abs(pct_change) > 10:  # Only report significant changes
                changes.append({
                    "category": category,
                    "current": curr,
                    "historical": hist,
                    "change_pct": pct_change,
                })

        return sorted(changes, key=lambda x: abs(x["change_pct"]), reverse=True)


class PatternDetector:
    """
    Detects patterns in transaction data.

    Patterns include:
    - Recurring transactions
    - Anomalies/outliers
    - Trends (increasing/decreasing)
    - Seasonal patterns
    - New payees/merchants
    """

    def __init__(self, config: Optional[InsightConfig] = None):
        self.config = config or InsightConfig()

    def detect_all_patterns(
        self,
        transactions: List[Transaction],
        historical_transactions: Optional[List[Transaction]] = None,
    ) -> List[DetectedPattern]:
        """Detect all types of patterns."""
        patterns = []

        # Detect recurring transactions
        patterns.extend(self._detect_recurring(transactions))

        # Detect anomalies
        patterns.extend(self._detect_anomalies(transactions))

        # Detect new payees (compare with historical)
        if historical_transactions:
            patterns.extend(
                self._detect_new_payees(transactions, historical_transactions)
            )
            patterns.extend(
                self._detect_trends(transactions, historical_transactions)
            )

        return patterns

    def _detect_recurring(
        self,
        transactions: List[Transaction],
    ) -> List[DetectedPattern]:
        """Detect recurring transaction patterns."""
        patterns = []

        # Group by merchant
        by_merchant = defaultdict(list)
        for t in transactions:
            if t.merchant_name:
                by_merchant[t.merchant_name].append(t)

        for merchant, txns in by_merchant.items():
            if len(txns) < 2:
                continue

            # Sort by date
            txns_sorted = sorted(txns, key=lambda x: x.date)

            # Calculate intervals between transactions
            intervals = []
            for i in range(1, len(txns_sorted)):
                delta = (txns_sorted[i].date - txns_sorted[i - 1].date).days
                intervals.append(delta)

            if not intervals:
                continue

            avg_interval = mean(intervals)
            interval_variance = stdev(intervals) if len(intervals) > 1 else 0

            # Check if it's recurring (low variance relative to mean)
            is_recurring = (
                avg_interval > 0 and
                interval_variance < avg_interval * 0.3 and
                7 <= avg_interval <= 35  # Weekly to monthly
            )

            if is_recurring:
                avg_amount = mean([float(t.amount) for t in txns])

                # Predict next occurrence
                last_date = txns_sorted[-1].date
                next_expected = last_date + timedelta(days=int(avg_interval))

                patterns.append(DetectedPattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_type=PatternType.RECURRING,
                    description=f"Recurring payment to {merchant}",
                    confidence=1.0 - (interval_variance / avg_interval) if avg_interval > 0 else 0.5,
                    affected_transactions=[t.transaction_id for t in txns],
                    merchant_or_category=merchant,
                    average_amount=Decimal(str(round(avg_amount, 2))),
                    frequency_days=int(avg_interval),
                    first_seen=txns_sorted[0].date,
                    last_seen=txns_sorted[-1].date,
                    next_expected=next_expected,
                    metadata={
                        "transaction_count": len(txns),
                        "interval_variance": interval_variance,
                    },
                ))

        return patterns

    def _detect_anomalies(
        self,
        transactions: List[Transaction],
    ) -> List[DetectedPattern]:
        """Detect anomalous transactions."""
        patterns = []

        # Group by category for category-specific anomaly detection
        by_category = defaultdict(list)
        for t in transactions:
            category = t.category or "uncategorized"
            by_category[category].append(t)

        for category, txns in by_category.items():
            if len(txns) < 3:
                continue

            amounts = [float(t.amount) for t in txns]
            avg = mean(amounts)
            std = stdev(amounts) if len(amounts) > 1 else 0

            if std == 0:
                continue

            # Find outliers (more than 2 standard deviations)
            threshold = self.config.unusual_spending_threshold
            for t in txns:
                z_score = (float(t.amount) - avg) / std if std > 0 else 0
                if abs(z_score) > threshold:
                    patterns.append(DetectedPattern(
                        pattern_id=str(uuid.uuid4()),
                        pattern_type=PatternType.ANOMALY,
                        description=f"Unusual {'high' if z_score > 0 else 'low'} amount in {category}",
                        confidence=min(0.9, abs(z_score) / 3),
                        affected_transactions=[t.transaction_id],
                        merchant_or_category=category,
                        average_amount=Decimal(str(round(avg, 2))),
                        metadata={
                            "actual_amount": str(t.amount),
                            "z_score": z_score,
                            "category_average": avg,
                            "category_stdev": std,
                        },
                    ))

        return patterns

    def _detect_new_payees(
        self,
        current: List[Transaction],
        historical: List[Transaction],
    ) -> List[DetectedPattern]:
        """Detect new payees/merchants not seen in historical data."""
        patterns = []

        historical_merchants = {
            t.merchant_name for t in historical
            if t.merchant_name
        }

        historical_payees = {
            t.counterparty_account for t in historical
            if t.counterparty_account
        }

        for t in current:
            # New merchant
            if t.merchant_name and t.merchant_name not in historical_merchants:
                patterns.append(DetectedPattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_type=PatternType.ANOMALY,
                    description=f"First transaction with {t.merchant_name}",
                    confidence=0.9,
                    affected_transactions=[t.transaction_id],
                    merchant_or_category=t.merchant_name,
                    average_amount=t.amount,
                    first_seen=t.date,
                    last_seen=t.date,
                    metadata={
                        "is_new_merchant": True,
                        "amount": str(t.amount),
                    },
                ))

            # New payee (for transfers)
            if t.counterparty_account and t.counterparty_account not in historical_payees:
                patterns.append(DetectedPattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_type=PatternType.ANOMALY,
                    description=f"First transfer to new account",
                    confidence=0.85,
                    affected_transactions=[t.transaction_id],
                    average_amount=t.amount,
                    first_seen=t.date,
                    last_seen=t.date,
                    metadata={
                        "is_new_payee": True,
                        "amount": str(t.amount),
                        "counterparty": t.counterparty_account[-4:] if t.counterparty_account else None,
                    },
                ))

        return patterns

    def _detect_trends(
        self,
        current: List[Transaction],
        historical: List[Transaction],
    ) -> List[DetectedPattern]:
        """Detect trending patterns (increasing/decreasing spending)."""
        patterns = []

        # Compare category spending trends
        current_by_category = defaultdict(Decimal)
        historical_by_category = defaultdict(Decimal)

        for t in current:
            if t.category and not t.is_credit:
                current_by_category[t.category] += t.amount

        for t in historical:
            if t.category and not t.is_credit:
                historical_by_category[t.category] += t.amount

        for category in set(current_by_category.keys()) | set(historical_by_category.keys()):
            curr = float(current_by_category.get(category, Decimal("0")))
            hist = float(historical_by_category.get(category, Decimal("0")))

            if hist == 0:
                continue

            change_pct = ((curr - hist) / hist) * 100

            if change_pct > 30:  # 30% increase
                patterns.append(DetectedPattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_type=PatternType.TRENDING_UP,
                    description=f"Spending on {category} increased by {change_pct:.0f}%",
                    confidence=min(0.95, change_pct / 100),
                    merchant_or_category=category,
                    metadata={
                        "current_amount": curr,
                        "historical_amount": hist,
                        "change_percentage": change_pct,
                    },
                ))
            elif change_pct < -30:  # 30% decrease
                patterns.append(DetectedPattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_type=PatternType.TRENDING_DOWN,
                    description=f"Spending on {category} decreased by {abs(change_pct):.0f}%",
                    confidence=min(0.95, abs(change_pct) / 100),
                    merchant_or_category=category,
                    metadata={
                        "current_amount": curr,
                        "historical_amount": hist,
                        "change_percentage": change_pct,
                    },
                ))

        return patterns

    def detect_subscription_patterns(
        self,
        transactions: List[Transaction],
    ) -> List[DetectedPattern]:
        """Specifically detect subscription-like patterns."""
        patterns = []

        # Group by merchant
        by_merchant = defaultdict(list)
        for t in transactions:
            if t.merchant_name and not t.is_credit:
                by_merchant[t.merchant_name].append(t)

        for merchant, txns in by_merchant.items():
            if len(txns) < 2:
                continue

            # Check for consistent amounts and timing
            amounts = [float(t.amount) for t in txns]
            txns_sorted = sorted(txns, key=lambda x: x.date)

            # Calculate amount consistency
            amount_variance = stdev(amounts) if len(amounts) > 1 else 0
            avg_amount = mean(amounts)

            # Calculate timing consistency
            intervals = []
            for i in range(1, len(txns_sorted)):
                delta = (txns_sorted[i].date - txns_sorted[i - 1].date).days
                intervals.append(delta)

            if not intervals:
                continue

            avg_interval = mean(intervals)
            interval_variance = stdev(intervals) if len(intervals) > 1 else 0

            # Subscription indicators:
            # - Consistent amount (low variance)
            # - Regular timing (weekly, monthly)
            # - Common subscription intervals: 7, 14, 28, 30, 31 days
            is_subscription = (
                amount_variance < avg_amount * 0.1 and  # Amount varies less than 10%
                interval_variance < avg_interval * 0.2 and  # Timing varies less than 20%
                25 <= avg_interval <= 35  # Monthly-ish
            )

            if is_subscription:
                patterns.append(DetectedPattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_type=PatternType.RECURRING,
                    description=f"Likely subscription: {merchant}",
                    confidence=0.85,
                    affected_transactions=[t.transaction_id for t in txns],
                    merchant_or_category=merchant,
                    average_amount=Decimal(str(round(avg_amount, 2))),
                    frequency_days=int(avg_interval),
                    first_seen=txns_sorted[0].date,
                    last_seen=txns_sorted[-1].date,
                    next_expected=txns_sorted[-1].date + timedelta(days=int(avg_interval)),
                    metadata={
                        "is_subscription": True,
                        "monthly_cost": round(avg_amount * 30 / avg_interval, 2),
                        "annual_cost": round(avg_amount * 365 / avg_interval, 2),
                    },
                ))

        return patterns
