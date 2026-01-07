"""
Banker Notification Service

Sends email notifications to bankers when customers consent to offerings.
Uses AWS SES for email delivery.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import boto3
from botocore.exceptions import ClientError

from .models import OfferingConsent, Offering

logger = logging.getLogger(__name__)


@dataclass
class BankerAssignment:
    """Banker assignment for handling offering."""
    banker_id: str
    banker_name: str
    banker_email: str
    branch_id: Optional[str] = None
    branch_name: Optional[str] = None
    specialization: Optional[str] = None


@dataclass
class NotificationResult:
    """Result of notification attempt."""
    success: bool
    message_id: Optional[str] = None
    assigned_banker_id: Optional[str] = None
    assigned_banker_name: Optional[str] = None
    error: Optional[str] = None


class BankerNotificationService:
    """
    Service for notifying bankers about customer offering consents.

    Features:
    - Email notification via AWS SES
    - Banker assignment/routing
    - Email templates (Hebrew + English)
    - Tracking and auditing
    """

    def __init__(
        self,
        sender_email: str = "chatbot@digitalbank.co.il",
        region: str = "us-east-1",
        banker_assignment_service: Optional[Any] = None,
    ):
        self.sender_email = sender_email
        self.ses_client = boto3.client("ses", region_name=region)
        self.banker_assignment = banker_assignment_service

        # Default banker pool for routing
        self._default_bankers: Dict[str, List[BankerAssignment]] = {
            "savings": [],
            "deposits": [],
            "loans": [],
            "credit_cards": [],
            "investments": [],
            "insurance": [],
            "default": [],
        }

    def register_banker(
        self,
        banker: BankerAssignment,
        categories: List[str],
    ) -> None:
        """Register a banker for handling specific offering categories."""
        for category in categories:
            if category in self._default_bankers:
                self._default_bankers[category].append(banker)
            else:
                self._default_bankers["default"].append(banker)

    async def send_offering_notification(
        self,
        consent: OfferingConsent,
        offering: Offering,
        is_backup: bool = False,
    ) -> NotificationResult:
        """
        Send notification to banker about customer offering consent.

        Args:
            consent: The customer consent record
            offering: The offering details
            is_backup: True if this is a backup notification (intent already executed)
        """
        # Assign banker
        banker = await self._assign_banker(consent, offering)
        if not banker:
            return NotificationResult(
                success=False,
                error="No banker available for this offering type",
            )

        # Build email
        subject = self._build_subject(consent, offering, is_backup)
        html_body = self._build_html_body(consent, offering, banker, is_backup)
        text_body = self._build_text_body(consent, offering, banker, is_backup)

        # Send email
        try:
            response = self.ses_client.send_email(
                Source=self.sender_email,
                Destination={
                    "ToAddresses": [banker.banker_email],
                    "CcAddresses": [],  # Could CC manager or audit
                },
                Message={
                    "Subject": {
                        "Data": subject,
                        "Charset": "UTF-8",
                    },
                    "Body": {
                        "Text": {
                            "Data": text_body,
                            "Charset": "UTF-8",
                        },
                        "Html": {
                            "Data": html_body,
                            "Charset": "UTF-8",
                        },
                    },
                },
                Tags=[
                    {"Name": "offering_id", "Value": consent.offering_id},
                    {"Name": "customer_id", "Value": consent.customer_id},
                    {"Name": "consent_id", "Value": consent.consent_id},
                ],
            )

            logger.info(
                f"Sent notification to banker {banker.banker_id} "
                f"for consent {consent.consent_id}"
            )

            return NotificationResult(
                success=True,
                message_id=response["MessageId"],
                assigned_banker_id=banker.banker_id,
                assigned_banker_name=banker.banker_name,
            )

        except ClientError as e:
            logger.error(f"Failed to send email: {e}")
            return NotificationResult(
                success=False,
                error=str(e),
            )

    async def _assign_banker(
        self,
        consent: OfferingConsent,
        offering: Offering,
    ) -> Optional[BankerAssignment]:
        """Assign a banker to handle this consent."""
        # If external assignment service is available, use it
        if self.banker_assignment:
            try:
                return await self.banker_assignment.assign(
                    customer_id=consent.customer_id,
                    offering_category=offering.category.value,
                    offering_type=offering.offering_type.value,
                )
            except Exception as e:
                logger.warning(f"External banker assignment failed: {e}")

        # Fallback to local routing
        category = offering.category.value
        bankers = self._default_bankers.get(category, [])

        if not bankers:
            bankers = self._default_bankers.get("default", [])

        if bankers:
            # Simple round-robin or random selection
            # In production, would consider workload, specialization, etc.
            import random
            return random.choice(bankers)

        return None

    def _build_subject(
        self,
        consent: OfferingConsent,
        offering: Offering,
        is_backup: bool,
    ) -> str:
        """Build email subject line."""
        prefix = "[גיבוי] " if is_backup else ""
        return (
            f"{prefix}לקוח מעוניין: {offering.name} | "
            f"מזהה לקוח: {consent.customer_id}"
        )

    def _build_html_body(
        self,
        consent: OfferingConsent,
        offering: Offering,
        banker: BankerAssignment,
        is_backup: bool,
    ) -> str:
        """Build HTML email body."""
        amount_str = f"₪{consent.agreed_amount:,.0f}" if consent.agreed_amount else "לא צוין"
        term_str = f"{consent.agreed_term_months} חודשים" if consent.agreed_term_months else "לא צוין"

        backup_notice = ""
        if is_backup:
            backup_notice = """
            <div style="background-color: #fff3cd; padding: 10px; border-radius: 5px; margin-bottom: 20px;">
                <strong>הערה:</strong> זוהי הודעת גיבוי. הבקשה כבר בוצעה באופן אוטומטי,
                אך נשלחה אליך לצורך מעקב ובקרת איכות.
            </div>
            """

        return f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #1a365d; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
        .content {{ background-color: #f7fafc; padding: 20px; border: 1px solid #e2e8f0; }}
        .highlight {{ background-color: #ebf8ff; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .details {{ background-color: white; padding: 15px; border-radius: 5px; border: 1px solid #e2e8f0; }}
        .details table {{ width: 100%; border-collapse: collapse; }}
        .details td {{ padding: 8px; border-bottom: 1px solid #e2e8f0; }}
        .details td:first-child {{ font-weight: bold; width: 40%; }}
        .cta {{ background-color: #3182ce; color: white; padding: 12px 24px; border-radius: 5px; text-decoration: none; display: inline-block; margin-top: 15px; }}
        .footer {{ background-color: #edf2f7; padding: 15px; border-radius: 0 0 5px 5px; font-size: 12px; color: #718096; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">בקשת לקוח חדשה</h1>
            <p style="margin: 5px 0 0 0;">מערכת הצ'אטבוט הדיגיטלי</p>
        </div>

        <div class="content">
            {backup_notice}

            <p>שלום {banker.banker_name},</p>

            <p>לקוח הביע עניין והסכמה למוצר הבא:</p>

            <div class="highlight">
                <h2 style="margin: 0 0 10px 0; color: #2c5282;">{offering.name}</h2>
                <p style="margin: 0;">{offering.presentation.description_he}</p>
            </div>

            <div class="details">
                <h3>פרטי הבקשה</h3>
                <table>
                    <tr>
                        <td>מזהה לקוח</td>
                        <td>{consent.customer_id}</td>
                    </tr>
                    <tr>
                        <td>סכום מבוקש</td>
                        <td>{amount_str}</td>
                    </tr>
                    <tr>
                        <td>תקופה מבוקשת</td>
                        <td>{term_str}</td>
                    </tr>
                    <tr>
                        <td>תאריך הסכמה</td>
                        <td>{consent.consented_at.strftime('%d/%m/%Y %H:%M') if consent.consented_at else datetime.utcnow().strftime('%d/%m/%Y %H:%M')}</td>
                    </tr>
                    <tr>
                        <td>מזהה הסכמה</td>
                        <td><code>{consent.consent_id}</code></td>
                    </tr>
                </table>

                {f'''
                <h4>הערות הלקוח</h4>
                <p style="background-color: #f0fff4; padding: 10px; border-radius: 5px;">{consent.customer_notes}</p>
                ''' if consent.customer_notes else ''}
            </div>

            <div class="details" style="margin-top: 15px;">
                <h3>פרטי המוצר</h3>
                <table>
                    <tr>
                        <td>קטגוריה</td>
                        <td>{offering.category.value}</td>
                    </tr>
                    <tr>
                        <td>סוג מוצר</td>
                        <td>{offering.offering_type.value}</td>
                    </tr>
                    {f'''
                    <tr>
                        <td>ריבית</td>
                        <td>{offering.terms.interest_rate}%</td>
                    </tr>
                    ''' if offering.terms.interest_rate else ''}
                </table>
            </div>

            <p style="margin-top: 20px;">
                <strong>פעולה נדרשת:</strong> יש ליצור קשר עם הלקוח תוך יום עסקים אחד
                להשלמת התהליך.
            </p>

            <a href="https://crm.bank.internal/customer/{consent.customer_id}" class="cta">
                צפייה בפרטי לקוח במערכת CRM
            </a>
        </div>

        <div class="footer">
            <p>הודעה זו נשלחה אוטומטית ממערכת הצ'אטבוט הבנקאי.</p>
            <p>מזהה שיחה: {consent.conversation_id or 'N/A'} | מזהה סשן: {consent.session_id or 'N/A'}</p>
        </div>
    </div>
</body>
</html>
"""

    def _build_text_body(
        self,
        consent: OfferingConsent,
        offering: Offering,
        banker: BankerAssignment,
        is_backup: bool,
    ) -> str:
        """Build plain text email body."""
        amount_str = f"₪{consent.agreed_amount:,.0f}" if consent.agreed_amount else "לא צוין"
        term_str = f"{consent.agreed_term_months} חודשים" if consent.agreed_term_months else "לא צוין"

        backup_notice = ""
        if is_backup:
            backup_notice = "\n[גיבוי] הבקשה כבר בוצעה אוטומטית. הודעה זו לצורך מעקב.\n"

        return f"""
בקשת לקוח חדשה - מערכת הצ'אטבוט הדיגיטלי
{'=' * 50}
{backup_notice}
שלום {banker.banker_name},

לקוח הביע עניין והסכמה למוצר הבא:

מוצר: {offering.name}
תיאור: {offering.presentation.description_he}

פרטי הבקשה:
- מזהה לקוח: {consent.customer_id}
- סכום מבוקש: {amount_str}
- תקופה מבוקשת: {term_str}
- תאריך הסכמה: {consent.consented_at.strftime('%d/%m/%Y %H:%M') if consent.consented_at else datetime.utcnow().strftime('%d/%m/%Y %H:%M')}
- מזהה הסכמה: {consent.consent_id}

{f'הערות הלקוח: {consent.customer_notes}' if consent.customer_notes else ''}

פרטי המוצר:
- קטגוריה: {offering.category.value}
- סוג: {offering.offering_type.value}
{f'- ריבית: {offering.terms.interest_rate}%' if offering.terms.interest_rate else ''}

פעולה נדרשת: יש ליצור קשר עם הלקוח תוך יום עסקים אחד.

קישור ל-CRM: https://crm.bank.internal/customer/{consent.customer_id}

{'=' * 50}
הודעה אוטומטית ממערכת הצ'אטבוט הבנקאי
מזהה שיחה: {consent.conversation_id or 'N/A'}
מזהה סשן: {consent.session_id or 'N/A'}
"""

    async def send_daily_summary(
        self,
        banker: BankerAssignment,
        consents: List[OfferingConsent],
        date: datetime,
    ) -> NotificationResult:
        """Send daily summary of all consents to a banker."""
        if not consents:
            return NotificationResult(success=True, message_id="no_consents")

        subject = f"סיכום יומי: {len(consents)} בקשות לקוחות | {date.strftime('%d/%m/%Y')}"

        # Build summary HTML
        consent_rows = ""
        for consent in consents:
            consent_rows += f"""
            <tr>
                <td>{consent.customer_id}</td>
                <td>{consent.offering_id}</td>
                <td>{f'₪{consent.agreed_amount:,.0f}' if consent.agreed_amount else '-'}</td>
                <td>{consent.status.value}</td>
                <td>{consent.consented_at.strftime('%H:%M') if consent.consented_at else '-'}</td>
            </tr>
            """

        html_body = f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; border: 1px solid #ddd; text-align: right; }}
        th {{ background-color: #1a365d; color: white; }}
    </style>
</head>
<body>
    <h1>סיכום יומי - בקשות לקוחות</h1>
    <p>תאריך: {date.strftime('%d/%m/%Y')}</p>
    <p>שלום {banker.banker_name}, להלן סיכום הבקשות שהתקבלו היום:</p>

    <table>
        <tr>
            <th>מזהה לקוח</th>
            <th>מוצר</th>
            <th>סכום</th>
            <th>סטטוס</th>
            <th>שעה</th>
        </tr>
        {consent_rows}
    </table>

    <p>סה"כ: {len(consents)} בקשות</p>
</body>
</html>
"""

        try:
            response = self.ses_client.send_email(
                Source=self.sender_email,
                Destination={"ToAddresses": [banker.banker_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
                },
            )

            return NotificationResult(
                success=True,
                message_id=response["MessageId"],
            )

        except ClientError as e:
            logger.error(f"Failed to send summary email: {e}")
            return NotificationResult(success=False, error=str(e))
