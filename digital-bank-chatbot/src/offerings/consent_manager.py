"""
Consent Manager and Fulfillment Handler

Manages customer consent for offerings and handles fulfillment
through either banker notification (Phase 1) or direct intent execution (Phase 2).
"""

import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field

import boto3
from botocore.exceptions import ClientError

from .models import (
    OfferingConsent,
    CustomerMatch,
    ConsentStatus,
    FulfillmentMode,
    Offering,
)
from .repository import OfferingsRepository

logger = logging.getLogger(__name__)


@dataclass
class ConsentRequest:
    """Request to record customer consent."""
    match: CustomerMatch
    agreed_amount: Optional[Decimal] = None
    agreed_term_months: Optional[int] = None
    customer_notes: Optional[str] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None


@dataclass
class FulfillmentResult:
    """Result of fulfillment attempt."""
    success: bool
    fulfillment_mode: FulfillmentMode
    message: str = ""
    banker_email_sent: bool = False
    intent_executed: bool = False
    intent_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    next_steps_he: str = ""
    next_steps_en: str = ""


class ConsentManager:
    """
    Manages customer consent for offerings.

    Handles the full lifecycle:
    1. Recording interest
    2. Capturing consent
    3. Triggering fulfillment
    4. Tracking status
    """

    def __init__(
        self,
        table_name: str = "offering-consents",
        region: str = "us-east-1",
        use_dynamodb: bool = True,
    ):
        self.table_name = table_name
        self.use_dynamodb = use_dynamodb

        if use_dynamodb:
            self.dynamodb = boto3.resource("dynamodb", region_name=region)
            self.table = self.dynamodb.Table(table_name)
        else:
            self._memory_store: Dict[str, OfferingConsent] = {}

    async def record_interest(
        self,
        match: CustomerMatch,
        session_id: Optional[str] = None,
    ) -> OfferingConsent:
        """Record that customer showed interest in an offering."""
        consent = OfferingConsent(
            consent_id=str(uuid.uuid4()),
            offering_id=match.offering_id,
            customer_id=match.customer_id,
            match=match,
            status=ConsentStatus.INTERESTED,
            fulfillment_mode=match.offering.fulfillment_mode,
            session_id=session_id,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )

        consent.update_status(ConsentStatus.INTERESTED, "Customer showed interest")
        await self._save(consent)

        logger.info(
            f"Recorded interest for customer {match.customer_id} "
            f"in offering {match.offering_id}"
        )

        return consent

    async def record_consent(
        self,
        request: ConsentRequest,
    ) -> OfferingConsent:
        """Record customer consent to proceed with an offering."""
        # Check for existing interest record
        existing = await self.get_by_customer_and_offering(
            request.match.customer_id,
            request.match.offering_id,
        )

        if existing and existing.status == ConsentStatus.INTERESTED:
            consent = existing
        else:
            consent = OfferingConsent(
                consent_id=str(uuid.uuid4()),
                offering_id=request.match.offering_id,
                customer_id=request.match.customer_id,
                match=request.match,
                fulfillment_mode=request.match.offering.fulfillment_mode,
                expires_at=datetime.utcnow() + timedelta(days=30),
            )

        # Update with consent details
        consent.agreed_amount = request.agreed_amount
        consent.agreed_term_months = request.agreed_term_months
        consent.customer_notes = request.customer_notes
        consent.session_id = request.session_id
        consent.conversation_id = request.conversation_id

        consent.update_status(ConsentStatus.CONSENTED, "Customer gave consent")
        await self._save(consent)

        logger.info(
            f"Recorded consent for customer {request.match.customer_id} "
            f"in offering {request.match.offering_id}"
        )

        return consent

    async def record_decline(
        self,
        customer_id: str,
        offering_id: str,
        reason: Optional[str] = None,
    ) -> Optional[OfferingConsent]:
        """Record that customer declined an offering."""
        existing = await self.get_by_customer_and_offering(customer_id, offering_id)

        if existing:
            existing.update_status(
                ConsentStatus.DECLINED,
                reason or "Customer declined"
            )
            await self._save(existing)
            return existing

        return None

    async def mark_fulfilled(
        self,
        consent_id: str,
        intent_execution_id: Optional[str] = None,
        intent_result: Optional[Dict[str, Any]] = None,
    ) -> Optional[OfferingConsent]:
        """Mark a consent as fulfilled."""
        consent = await self.get(consent_id)
        if not consent:
            return None

        consent.intent_executed = bool(intent_execution_id)
        consent.intent_execution_id = intent_execution_id
        consent.intent_result = intent_result
        consent.update_status(ConsentStatus.FULFILLED, "Offering fulfilled")

        await self._save(consent)
        return consent

    async def get(self, consent_id: str) -> Optional[OfferingConsent]:
        """Get consent by ID."""
        if self.use_dynamodb:
            try:
                response = self.table.get_item(Key={"consent_id": consent_id})
                if "Item" in response:
                    return self._dict_to_consent(response["Item"])
                return None
            except ClientError as e:
                logger.error(f"Failed to get consent: {e}")
                return None
        else:
            return self._memory_store.get(consent_id)

    async def get_by_customer_and_offering(
        self,
        customer_id: str,
        offering_id: str,
    ) -> Optional[OfferingConsent]:
        """Get consent by customer and offering."""
        # In production, use GSI for this query
        consents = await self.get_by_customer(customer_id)
        for consent in consents:
            if consent.offering_id == offering_id:
                if consent.status not in [ConsentStatus.EXPIRED, ConsentStatus.FULFILLED]:
                    return consent
        return None

    async def get_by_customer(
        self,
        customer_id: str,
        status: Optional[ConsentStatus] = None,
    ) -> List[OfferingConsent]:
        """Get all consents for a customer."""
        if self.use_dynamodb:
            try:
                # Use GSI on customer_id in production
                response = self.table.scan(
                    FilterExpression="customer_id = :cid",
                    ExpressionAttributeValues={":cid": customer_id},
                )
                consents = [
                    self._dict_to_consent(item)
                    for item in response.get("Items", [])
                ]
                if status:
                    consents = [c for c in consents if c.status == status]
                return consents
            except ClientError as e:
                logger.error(f"Failed to get consents: {e}")
                return []
        else:
            consents = [
                c for c in self._memory_store.values()
                if c.customer_id == customer_id
            ]
            if status:
                consents = [c for c in consents if c.status == status]
            return consents

    async def get_pending_fulfillment(self) -> List[OfferingConsent]:
        """Get all consents pending fulfillment."""
        if self.use_dynamodb:
            try:
                response = self.table.scan(
                    FilterExpression="status = :status",
                    ExpressionAttributeValues={":status": ConsentStatus.CONSENTED.value},
                )
                return [
                    self._dict_to_consent(item)
                    for item in response.get("Items", [])
                ]
            except ClientError as e:
                logger.error(f"Failed to get pending consents: {e}")
                return []
        else:
            return [
                c for c in self._memory_store.values()
                if c.status == ConsentStatus.CONSENTED
            ]

    async def expire_old_consents(self, batch_size: int = 100) -> int:
        """Expire consents that have passed their expiry date."""
        expired_count = 0
        now = datetime.utcnow()

        if self.use_dynamodb:
            try:
                response = self.table.scan(
                    FilterExpression="expires_at < :now AND status <> :expired",
                    ExpressionAttributeValues={
                        ":now": now.isoformat(),
                        ":expired": ConsentStatus.EXPIRED.value,
                    },
                    Limit=batch_size,
                )

                for item in response.get("Items", []):
                    consent = self._dict_to_consent(item)
                    consent.update_status(ConsentStatus.EXPIRED, "Expired")
                    await self._save(consent)
                    expired_count += 1

            except ClientError as e:
                logger.error(f"Failed to expire consents: {e}")
        else:
            for consent in list(self._memory_store.values()):
                if consent.expires_at and consent.expires_at < now:
                    if consent.status != ConsentStatus.EXPIRED:
                        consent.update_status(ConsentStatus.EXPIRED, "Expired")
                        expired_count += 1

        logger.info(f"Expired {expired_count} consents")
        return expired_count

    async def _save(self, consent: OfferingConsent) -> bool:
        """Save consent to storage."""
        if self.use_dynamodb:
            try:
                self.table.put_item(Item=consent.to_dict())
                return True
            except ClientError as e:
                logger.error(f"Failed to save consent: {e}")
                return False
        else:
            self._memory_store[consent.consent_id] = consent
            return True

    def _dict_to_consent(self, data: Dict[str, Any]) -> OfferingConsent:
        """Convert dictionary to OfferingConsent object."""
        # Simplified conversion - in production would be more complete
        consent = OfferingConsent(
            consent_id=data["consent_id"],
            offering_id=data["offering_id"],
            customer_id=data["customer_id"],
            match=None,  # Would need to reconstruct from stored data
            status=ConsentStatus(data.get("status", "pending")),
            status_history=data.get("status_history", []),
            agreed_amount=Decimal(data["agreed_amount"]) if data.get("agreed_amount") else None,
            agreed_term_months=data.get("agreed_term_months"),
            customer_notes=data.get("customer_notes"),
            fulfillment_mode=FulfillmentMode(data.get("fulfillment_mode", "email_to_banker")),
            banker_email_sent=data.get("banker_email_sent", False),
            banker_email_sent_at=datetime.fromisoformat(data["banker_email_sent_at"]) if data.get("banker_email_sent_at") else None,
            assigned_banker_id=data.get("assigned_banker_id"),
            assigned_banker_name=data.get("assigned_banker_name"),
            intent_executed=data.get("intent_executed", False),
            intent_execution_id=data.get("intent_execution_id"),
            intent_result=data.get("intent_result"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            consented_at=datetime.fromisoformat(data["consented_at"]) if data.get("consented_at") else None,
            fulfilled_at=datetime.fromisoformat(data["fulfilled_at"]) if data.get("fulfilled_at") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            session_id=data.get("session_id"),
            conversation_id=data.get("conversation_id"),
        )
        return consent


class FulfillmentHandler:
    """
    Handles fulfillment of consented offerings.

    Supports two modes:
    1. Phase 1 (EMAIL_TO_BANKER): Send email notification to banker
    2. Phase 2 (DIRECT_INTENT): Execute intent directly
    """

    def __init__(
        self,
        consent_manager: ConsentManager,
        repository: OfferingsRepository,
        banker_notification_service: Optional[Any] = None,  # BankerNotificationService
        intent_executor: Optional[Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
    ):
        self.consent_manager = consent_manager
        self.repository = repository
        self.banker_notification = banker_notification_service
        self.intent_executor = intent_executor

    async def fulfill(
        self,
        consent: OfferingConsent,
    ) -> FulfillmentResult:
        """
        Fulfill a consented offering.

        Routes to appropriate handler based on fulfillment mode.
        """
        if consent.status != ConsentStatus.CONSENTED:
            return FulfillmentResult(
                success=False,
                fulfillment_mode=consent.fulfillment_mode,
                error=f"Cannot fulfill consent in status: {consent.status.value}",
            )

        offering = self.repository.get(consent.offering_id)
        if not offering:
            return FulfillmentResult(
                success=False,
                fulfillment_mode=consent.fulfillment_mode,
                error=f"Offering not found: {consent.offering_id}",
            )

        # Route based on fulfillment mode
        if consent.fulfillment_mode == FulfillmentMode.EMAIL_TO_BANKER:
            return await self._fulfill_via_email(consent, offering)

        elif consent.fulfillment_mode == FulfillmentMode.DIRECT_INTENT:
            return await self._fulfill_via_intent(consent, offering)

        elif consent.fulfillment_mode == FulfillmentMode.HYBRID:
            return await self._fulfill_hybrid(consent, offering)

        else:
            return FulfillmentResult(
                success=False,
                fulfillment_mode=consent.fulfillment_mode,
                error=f"Unsupported fulfillment mode: {consent.fulfillment_mode.value}",
            )

    async def _fulfill_via_email(
        self,
        consent: OfferingConsent,
        offering: Offering,
    ) -> FulfillmentResult:
        """Fulfill by sending email to banker (Phase 1)."""
        if not self.banker_notification:
            return FulfillmentResult(
                success=False,
                fulfillment_mode=FulfillmentMode.EMAIL_TO_BANKER,
                error="Banker notification service not configured",
            )

        try:
            # Send notification to banker
            notification_result = await self.banker_notification.send_offering_notification(
                consent=consent,
                offering=offering,
            )

            if notification_result.success:
                # Update consent
                consent.banker_email_sent = True
                consent.banker_email_sent_at = datetime.utcnow()
                consent.assigned_banker_id = notification_result.assigned_banker_id
                consent.assigned_banker_name = notification_result.assigned_banker_name
                await self.consent_manager._save(consent)

                # Update offering analytics
                self.repository.update_analytics(
                    offering.offering_id,
                    consents=1,
                )

                return FulfillmentResult(
                    success=True,
                    fulfillment_mode=FulfillmentMode.EMAIL_TO_BANKER,
                    message="Banker has been notified and will contact you shortly",
                    banker_email_sent=True,
                    next_steps_he="יועץ הבנק יצור איתך קשר תוך יום עסקים אחד להשלמת הבקשה.",
                    next_steps_en="A banker will contact you within one business day to complete the request.",
                )
            else:
                return FulfillmentResult(
                    success=False,
                    fulfillment_mode=FulfillmentMode.EMAIL_TO_BANKER,
                    error=notification_result.error,
                )

        except Exception as e:
            logger.error(f"Failed to fulfill via email: {e}")
            return FulfillmentResult(
                success=False,
                fulfillment_mode=FulfillmentMode.EMAIL_TO_BANKER,
                error=str(e),
            )

    async def _fulfill_via_intent(
        self,
        consent: OfferingConsent,
        offering: Offering,
    ) -> FulfillmentResult:
        """Fulfill by executing intent directly (Phase 2)."""
        if not self.intent_executor:
            # Fallback to email if intent executor not available
            logger.warning(
                f"Intent executor not available, falling back to email "
                f"for offering {offering.offering_id}"
            )
            consent.fulfillment_mode = FulfillmentMode.EMAIL_TO_BANKER
            return await self._fulfill_via_email(consent, offering)

        if not offering.fulfillment_intent_id:
            return FulfillmentResult(
                success=False,
                fulfillment_mode=FulfillmentMode.DIRECT_INTENT,
                error="No fulfillment intent configured for this offering",
            )

        try:
            # Prepare intent parameters
            intent_params = {
                "customer_id": consent.customer_id,
                "offering_id": consent.offering_id,
                "amount": str(consent.agreed_amount) if consent.agreed_amount else None,
                "term_months": consent.agreed_term_months,
                "session_id": consent.session_id,
                "consent_id": consent.consent_id,
            }

            # Execute the intent
            intent_result = await self.intent_executor(
                offering.fulfillment_intent_id,
                intent_params,
            )

            if intent_result.get("success"):
                # Mark as fulfilled
                await self.consent_manager.mark_fulfilled(
                    consent.consent_id,
                    intent_execution_id=intent_result.get("execution_id"),
                    intent_result=intent_result,
                )

                # Update offering analytics
                self.repository.update_analytics(
                    offering.offering_id,
                    consents=1,
                    fulfillments=1,
                )

                return FulfillmentResult(
                    success=True,
                    fulfillment_mode=FulfillmentMode.DIRECT_INTENT,
                    message="Your request has been processed successfully",
                    intent_executed=True,
                    intent_result=intent_result,
                    next_steps_he=intent_result.get("next_steps_he", "הבקשה בוצעה בהצלחה."),
                    next_steps_en=intent_result.get("next_steps_en", "Your request was completed successfully."),
                )
            else:
                # Intent failed, fallback to email
                logger.warning(f"Intent execution failed: {intent_result.get('error')}")
                consent.fulfillment_mode = FulfillmentMode.EMAIL_TO_BANKER
                return await self._fulfill_via_email(consent, offering)

        except Exception as e:
            logger.error(f"Failed to fulfill via intent: {e}")
            # Fallback to email on error
            consent.fulfillment_mode = FulfillmentMode.EMAIL_TO_BANKER
            return await self._fulfill_via_email(consent, offering)

    async def _fulfill_hybrid(
        self,
        consent: OfferingConsent,
        offering: Offering,
    ) -> FulfillmentResult:
        """Fulfill using both intent and email notification."""
        # First try intent
        intent_result = await self._fulfill_via_intent(consent, offering)

        # Always send email notification as well
        if self.banker_notification:
            await self.banker_notification.send_offering_notification(
                consent=consent,
                offering=offering,
                is_backup=not intent_result.success,
            )
            intent_result.banker_email_sent = True

        return intent_result

    async def process_pending_fulfillments(
        self,
        batch_size: int = 50,
    ) -> Dict[str, int]:
        """Process all pending fulfillments (for scheduled job)."""
        results = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
        }

        pending = await self.consent_manager.get_pending_fulfillment()

        for consent in pending[:batch_size]:
            results["processed"] += 1

            result = await self.fulfill(consent)
            if result.success:
                results["succeeded"] += 1
            else:
                results["failed"] += 1

        logger.info(f"Processed {results['processed']} pending fulfillments")
        return results
