# Offerings Bank Module
# Manages bank product offerings, customer matching, and fulfillment

from .models import (
    Offering,
    OfferingCategory,
    OfferingType,
    EligibilityCriteria,
    OfferingTerms,
    CustomerMatch,
    OfferingConsent,
    ConsentStatus,
    FulfillmentMode,
    OfferingPresentation,
)
from .repository import OfferingsRepository
from .matching_agent import OfferingsMatchingAgent
from .consent_manager import ConsentManager, FulfillmentHandler
from .banker_notification import BankerNotificationService

__all__ = [
    "Offering",
    "OfferingCategory",
    "OfferingType",
    "EligibilityCriteria",
    "OfferingTerms",
    "CustomerMatch",
    "OfferingConsent",
    "ConsentStatus",
    "FulfillmentMode",
    "OfferingPresentation",
    "OfferingsRepository",
    "OfferingsMatchingAgent",
    "ConsentManager",
    "FulfillmentHandler",
    "BankerNotificationService",
]
