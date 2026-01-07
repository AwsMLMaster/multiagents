"""
TCS Bancs Core Banking System Integration.

This module provides integration with TCS Bancs for:
- Account operations (balance, statements, details)
- Transaction operations (transfers, payments)
- Loan operations (status, payments, applications)
- Customer operations (profile, preferences)
"""

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class TransactionType(str, Enum):
    """Types of banking transactions."""
    INTERNAL_TRANSFER = "internal_transfer"
    EXTERNAL_TRANSFER = "external_transfer"
    BILL_PAYMENT = "bill_payment"
    LOAN_PAYMENT = "loan_payment"
    STANDING_ORDER = "standing_order"


class TransactionStatus(str, Enum):
    """Transaction status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    AWAITING_APPROVAL = "awaiting_approval"


@dataclass
class TCSBancsConfig:
    """Configuration for TCS Bancs client."""
    base_url: str
    api_key: str
    api_secret: str
    client_id: str
    timeout: int = 30
    max_retries: int = 3
    verify_ssl: bool = True


@dataclass
class AccountBalance:
    """Account balance information."""
    account_id: str
    account_number: str
    account_type: str
    currency: str
    available_balance: float
    current_balance: float
    overdraft_limit: float
    as_of: datetime


@dataclass
class Transaction:
    """Transaction record."""
    transaction_id: str
    account_id: str
    transaction_type: str
    amount: float
    currency: str
    description: str
    reference: str
    value_date: datetime
    booking_date: datetime
    balance_after: float
    counterparty: Optional[str] = None
    category: Optional[str] = None


@dataclass
class TransferRequest:
    """Fund transfer request."""
    from_account: str
    to_account: str
    amount: float
    currency: str
    description: Optional[str] = None
    reference: Optional[str] = None
    execution_date: Optional[datetime] = None


@dataclass
class TransferResponse:
    """Fund transfer response."""
    transfer_id: str
    status: TransactionStatus
    from_account: str
    to_account: str
    amount: float
    currency: str
    reference: str
    created_at: datetime
    message: Optional[str] = None


@dataclass
class LoanDetails:
    """Loan details information."""
    loan_id: str
    loan_type: str
    principal_amount: float
    outstanding_balance: float
    interest_rate: float
    monthly_payment: float
    next_payment_date: datetime
    remaining_payments: int
    status: str
    start_date: datetime
    end_date: datetime


class TCSBancsClient:
    """
    TCS Bancs Core Banking API Client.

    Provides secure integration with TCS Bancs core banking system
    for all banking operations.
    """

    def __init__(self, config: TCSBancsConfig):
        """
        Initialize the TCS Bancs client.

        Args:
            config: TCSBancsConfig with connection details.
        """
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _sign_request(
        self,
        method: str,
        path: str,
        timestamp: str,
        body: Optional[str] = None
    ) -> str:
        """
        Sign request using HMAC-SHA256.

        Args:
            method: HTTP method.
            path: Request path.
            timestamp: Request timestamp.
            body: Optional request body.

        Returns:
            Base64-encoded signature.
        """
        import base64

        message = f"{method}\n{path}\n{timestamp}\n"
        if body:
            message += hashlib.sha256(body.encode()).hexdigest()

        signature = hmac.new(
            self.config.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()

        return base64.b64encode(signature).decode()

    def _get_headers(
        self,
        method: str,
        path: str,
        body: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate request headers with authentication.

        Args:
            method: HTTP method.
            path: Request path.
            body: Optional request body.

        Returns:
            Headers dictionary.
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        signature = self._sign_request(method, path, timestamp, body)

        return {
            "Content-Type": "application/json",
            "X-API-Key": self.config.api_key,
            "X-Client-ID": self.config.client_id,
            "X-Timestamp": timestamp,
            "X-Signature": signature,
            "Accept-Language": "he-IL",  # Hebrew responses
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated request to TCS Bancs API.

        Args:
            method: HTTP method.
            path: API path.
            data: Optional request body.
            params: Optional query parameters.

        Returns:
            Response JSON data.
        """
        session = await self._get_session()
        url = urljoin(self.config.base_url, path)

        body = json.dumps(data) if data else None
        headers = self._get_headers(method, path, body)

        start_time = time.time()

        try:
            async with session.request(
                method,
                url,
                headers=headers,
                data=body,
                params=params,
                ssl=self.config.verify_ssl
            ) as response:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info(f"TCS Bancs {method} {path} - {response.status} ({latency_ms}ms)")

                if response.status >= 400:
                    error_body = await response.text()
                    raise TCSBancsError(
                        f"TCS Bancs API error: {response.status} - {error_body}"
                    )

                return await response.json()

        except aiohttp.ClientError as e:
            logger.error(f"TCS Bancs request error: {e}")
            raise TCSBancsError(f"Failed to connect to TCS Bancs: {e}") from e

    # =========================================================================
    # Account Operations
    # =========================================================================

    async def get_account_balance(
        self,
        account_id: str,
        customer_id: str
    ) -> AccountBalance:
        """
        Get account balance.

        Args:
            account_id: Account identifier.
            customer_id: Customer identifier for authorization.

        Returns:
            AccountBalance object.
        """
        response = await self._request(
            "GET",
            f"/accounts/{account_id}/balance",
            params={"customerId": customer_id}
        )

        return AccountBalance(
            account_id=response["accountId"],
            account_number=response["accountNumber"],
            account_type=response["accountType"],
            currency=response["currency"],
            available_balance=float(response["availableBalance"]),
            current_balance=float(response["currentBalance"]),
            overdraft_limit=float(response.get("overdraftLimit", 0)),
            as_of=datetime.fromisoformat(response["asOf"].replace("Z", "+00:00"))
        )

    async def get_account_transactions(
        self,
        account_id: str,
        customer_id: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Transaction]:
        """
        Get account transactions.

        Args:
            account_id: Account identifier.
            customer_id: Customer identifier.
            from_date: Optional start date.
            to_date: Optional end date.
            limit: Maximum number of transactions.

        Returns:
            List of Transaction objects.
        """
        params = {"customerId": customer_id, "limit": str(limit)}

        if from_date:
            params["fromDate"] = from_date.strftime("%Y-%m-%d")
        if to_date:
            params["toDate"] = to_date.strftime("%Y-%m-%d")

        response = await self._request(
            "GET",
            f"/accounts/{account_id}/transactions",
            params=params
        )

        transactions = []
        for txn in response.get("transactions", []):
            transactions.append(Transaction(
                transaction_id=txn["transactionId"],
                account_id=account_id,
                transaction_type=txn["type"],
                amount=float(txn["amount"]),
                currency=txn["currency"],
                description=txn["description"],
                reference=txn.get("reference", ""),
                value_date=datetime.fromisoformat(txn["valueDate"].replace("Z", "+00:00")),
                booking_date=datetime.fromisoformat(txn["bookingDate"].replace("Z", "+00:00")),
                balance_after=float(txn.get("balanceAfter", 0)),
                counterparty=txn.get("counterparty"),
                category=txn.get("category")
            ))

        return transactions

    async def get_accounts(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get all accounts for a customer.

        Args:
            customer_id: Customer identifier.

        Returns:
            List of account information dictionaries.
        """
        response = await self._request(
            "GET",
            f"/customers/{customer_id}/accounts"
        )
        return response.get("accounts", [])

    # =========================================================================
    # Transaction Operations
    # =========================================================================

    async def initiate_transfer(
        self,
        customer_id: str,
        transfer: TransferRequest,
        idempotency_key: str
    ) -> TransferResponse:
        """
        Initiate a fund transfer.

        Args:
            customer_id: Customer identifier.
            transfer: TransferRequest with transfer details.
            idempotency_key: Unique key for idempotent request.

        Returns:
            TransferResponse with transfer status.
        """
        data = {
            "fromAccount": transfer.from_account,
            "toAccount": transfer.to_account,
            "amount": str(transfer.amount),
            "currency": transfer.currency,
            "customerId": customer_id,
            "idempotencyKey": idempotency_key,
        }

        if transfer.description:
            data["description"] = transfer.description
        if transfer.reference:
            data["reference"] = transfer.reference
        if transfer.execution_date:
            data["executionDate"] = transfer.execution_date.strftime("%Y-%m-%d")

        response = await self._request("POST", "/payments/transfers", data=data)

        return TransferResponse(
            transfer_id=response["transferId"],
            status=TransactionStatus(response["status"]),
            from_account=response["fromAccount"],
            to_account=response["toAccount"],
            amount=float(response["amount"]),
            currency=response["currency"],
            reference=response.get("reference", ""),
            created_at=datetime.fromisoformat(response["createdAt"].replace("Z", "+00:00")),
            message=response.get("message")
        )

    async def confirm_transfer(
        self,
        transfer_id: str,
        customer_id: str,
        mfa_token: str
    ) -> TransferResponse:
        """
        Confirm a pending transfer with MFA.

        Args:
            transfer_id: Transfer identifier.
            customer_id: Customer identifier.
            mfa_token: MFA verification token.

        Returns:
            TransferResponse with updated status.
        """
        data = {
            "customerId": customer_id,
            "mfaToken": mfa_token,
        }

        response = await self._request(
            "POST",
            f"/payments/transfers/{transfer_id}/confirm",
            data=data
        )

        return TransferResponse(
            transfer_id=response["transferId"],
            status=TransactionStatus(response["status"]),
            from_account=response["fromAccount"],
            to_account=response["toAccount"],
            amount=float(response["amount"]),
            currency=response["currency"],
            reference=response.get("reference", ""),
            created_at=datetime.fromisoformat(response["createdAt"].replace("Z", "+00:00")),
            message=response.get("message")
        )

    async def get_transfer_status(
        self,
        transfer_id: str,
        customer_id: str
    ) -> TransferResponse:
        """
        Get transfer status.

        Args:
            transfer_id: Transfer identifier.
            customer_id: Customer identifier.

        Returns:
            TransferResponse with current status.
        """
        response = await self._request(
            "GET",
            f"/payments/transfers/{transfer_id}",
            params={"customerId": customer_id}
        )

        return TransferResponse(
            transfer_id=response["transferId"],
            status=TransactionStatus(response["status"]),
            from_account=response["fromAccount"],
            to_account=response["toAccount"],
            amount=float(response["amount"]),
            currency=response["currency"],
            reference=response.get("reference", ""),
            created_at=datetime.fromisoformat(response["createdAt"].replace("Z", "+00:00")),
            message=response.get("message")
        )

    async def pay_bill(
        self,
        customer_id: str,
        from_account: str,
        biller_id: str,
        amount: float,
        currency: str = "ILS",
        reference: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> TransferResponse:
        """
        Pay a bill.

        Args:
            customer_id: Customer identifier.
            from_account: Source account.
            biller_id: Biller identifier.
            amount: Payment amount.
            currency: Currency code.
            reference: Optional payment reference.
            idempotency_key: Unique key for idempotent request.

        Returns:
            TransferResponse with payment status.
        """
        import uuid

        data = {
            "customerId": customer_id,
            "fromAccount": from_account,
            "billerId": biller_id,
            "amount": str(amount),
            "currency": currency,
            "idempotencyKey": idempotency_key or str(uuid.uuid4()),
        }

        if reference:
            data["reference"] = reference

        response = await self._request("POST", "/payments/bills", data=data)

        return TransferResponse(
            transfer_id=response["paymentId"],
            status=TransactionStatus(response["status"]),
            from_account=from_account,
            to_account=biller_id,
            amount=amount,
            currency=currency,
            reference=response.get("reference", ""),
            created_at=datetime.fromisoformat(response["createdAt"].replace("Z", "+00:00")),
            message=response.get("message")
        )

    # =========================================================================
    # Loan Operations
    # =========================================================================

    async def get_loan_details(
        self,
        loan_id: str,
        customer_id: str
    ) -> LoanDetails:
        """
        Get loan details.

        Args:
            loan_id: Loan identifier.
            customer_id: Customer identifier.

        Returns:
            LoanDetails object.
        """
        response = await self._request(
            "GET",
            f"/loans/{loan_id}",
            params={"customerId": customer_id}
        )

        return LoanDetails(
            loan_id=response["loanId"],
            loan_type=response["loanType"],
            principal_amount=float(response["principalAmount"]),
            outstanding_balance=float(response["outstandingBalance"]),
            interest_rate=float(response["interestRate"]),
            monthly_payment=float(response["monthlyPayment"]),
            next_payment_date=datetime.fromisoformat(
                response["nextPaymentDate"].replace("Z", "+00:00")
            ),
            remaining_payments=int(response["remainingPayments"]),
            status=response["status"],
            start_date=datetime.fromisoformat(response["startDate"].replace("Z", "+00:00")),
            end_date=datetime.fromisoformat(response["endDate"].replace("Z", "+00:00"))
        )

    async def get_loans(self, customer_id: str) -> List[LoanDetails]:
        """
        Get all loans for a customer.

        Args:
            customer_id: Customer identifier.

        Returns:
            List of LoanDetails objects.
        """
        response = await self._request(
            "GET",
            f"/customers/{customer_id}/loans"
        )

        loans = []
        for loan in response.get("loans", []):
            loans.append(LoanDetails(
                loan_id=loan["loanId"],
                loan_type=loan["loanType"],
                principal_amount=float(loan["principalAmount"]),
                outstanding_balance=float(loan["outstandingBalance"]),
                interest_rate=float(loan["interestRate"]),
                monthly_payment=float(loan["monthlyPayment"]),
                next_payment_date=datetime.fromisoformat(
                    loan["nextPaymentDate"].replace("Z", "+00:00")
                ),
                remaining_payments=int(loan["remainingPayments"]),
                status=loan["status"],
                start_date=datetime.fromisoformat(loan["startDate"].replace("Z", "+00:00")),
                end_date=datetime.fromisoformat(loan["endDate"].replace("Z", "+00:00"))
            ))

        return loans

    async def calculate_loan_emi(
        self,
        principal: float,
        annual_rate: float,
        tenure_months: int
    ) -> Dict[str, Any]:
        """
        Calculate loan EMI (Equated Monthly Installment).

        This can be done locally without API call.

        Args:
            principal: Loan principal amount.
            annual_rate: Annual interest rate (percentage).
            tenure_months: Loan tenure in months.

        Returns:
            Dictionary with EMI details.
        """
        # Convert annual rate to monthly rate
        monthly_rate = annual_rate / 12 / 100

        if monthly_rate == 0:
            emi = principal / tenure_months
        else:
            # EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)
            emi = (
                principal
                * monthly_rate
                * ((1 + monthly_rate) ** tenure_months)
                / (((1 + monthly_rate) ** tenure_months) - 1)
            )

        total_payment = emi * tenure_months
        total_interest = total_payment - principal

        return {
            "principal": principal,
            "annual_rate": annual_rate,
            "tenure_months": tenure_months,
            "monthly_payment": round(emi, 2),
            "total_payment": round(total_payment, 2),
            "total_interest": round(total_interest, 2),
        }


class TCSBancsError(Exception):
    """Exception raised when TCS Bancs operations fail."""
    pass


def create_tcs_bancs_client(
    base_url: str,
    api_key: str,
    api_secret: str,
    client_id: str
) -> TCSBancsClient:
    """
    Factory function to create TCS Bancs client.

    Args:
        base_url: TCS Bancs API base URL.
        api_key: API key for authentication.
        api_secret: API secret for signing.
        client_id: Client identifier.

    Returns:
        Configured TCSBancsClient.
    """
    config = TCSBancsConfig(
        base_url=base_url,
        api_key=api_key,
        api_secret=api_secret,
        client_id=client_id,
    )
    return TCSBancsClient(config)
