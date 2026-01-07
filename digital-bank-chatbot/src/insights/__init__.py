# Financial Insights Module
# Analyzes account activity and generates personalized financial insights

from .models import (
    Insight,
    InsightCategory,
    InsightSeverity,
    InsightType,
    InsightRecommendation,
    PatternType,
    DetectedPattern,
    InsightConfig,
)
from .generator import FinancialInsightsGenerator
from .patterns import PatternDetector, TransactionAnalyzer
from .recommendations import RecommendationEngine

__all__ = [
    "Insight",
    "InsightCategory",
    "InsightSeverity",
    "InsightType",
    "InsightRecommendation",
    "PatternType",
    "DetectedPattern",
    "InsightConfig",
    "FinancialInsightsGenerator",
    "PatternDetector",
    "TransactionAnalyzer",
    "RecommendationEngine",
]
