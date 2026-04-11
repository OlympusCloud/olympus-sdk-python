"""Payment processing, refunds, balance, payouts, and terminal management.

Wraps the Olympus Payment Orchestration service via the Go API Gateway.
Routes: ``/payments/*``, ``/finance/*``, ``/stripe/terminal/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from olympus_sdk.models.pay import Balance, Payment, Payout, Refund, TerminalPayment, TerminalReader

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class PayService:
    """Payment processing, refunds, balance, payouts, and terminal management."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Payment intents
    # ------------------------------------------------------------------

    def charge(self, order_id: str, amount: int, method: str) -> Payment:
        """Charge an order using the given payment method.

        ``amount`` is in cents. ``method`` is a payment method token or ID
        (e.g. a Stripe payment method ID or "cash").
        """
        data = self._http.post("/payments/intents", json={
            "order_id": order_id,
            "amount": amount,
            "payment_method": method,
        })
        return Payment.from_dict(data)

    def capture(self, payment_id: str) -> Payment:
        """Capture a previously authorized payment."""
        data = self._http.post(f"/payments/{payment_id}/capture")
        return Payment.from_dict(data)

    # ------------------------------------------------------------------
    # Refunds
    # ------------------------------------------------------------------

    def refund(
        self,
        payment_id: str,
        *,
        amount: int | None = None,
        reason: str | None = None,
    ) -> Refund:
        """Refund a payment, optionally partially.

        If ``amount`` is None the full payment is refunded.
        """
        payload: dict[str, Any] = {}
        if amount is not None:
            payload["amount"] = amount
        if reason is not None:
            payload["reason"] = reason
        data = self._http.post(f"/payments/{payment_id}/refund", json=payload)
        return Refund.from_dict(data)

    # ------------------------------------------------------------------
    # Balance & payouts
    # ------------------------------------------------------------------

    def get_balance(self) -> Balance:
        """Get the current account balance."""
        data = self._http.get("/finance/balance")
        return Balance.from_dict(data)

    def create_payout(
        self,
        amount: int,
        destination: str,
        *,
        currency: str | None = None,
        method: str | None = None,
        description: str | None = None,
    ) -> Payout:
        """Initiate a payout to an external destination.

        ``method`` is either "standard" (1-2 business days) or "instant".
        """
        payload: dict[str, Any] = {"amount": amount, "destination": destination}
        if currency is not None:
            payload["currency"] = currency
        if method is not None:
            payload["method"] = method
        if description is not None:
            payload["description"] = description
        data = self._http.post("/finance/payouts", json=payload)
        return Payout.from_dict(data)

    # ------------------------------------------------------------------
    # Payment listing
    # ------------------------------------------------------------------

    def list_payments(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        status: str | None = None,
    ) -> list[Payment]:
        """List recent payments for the tenant."""
        data = self._http.get(
            "/payments",
            params={"page": page, "limit": limit, "status": status},
        )
        items_raw = data.get("payments") or data.get("data") or []
        return [Payment.from_dict(p) for p in items_raw]

    # ------------------------------------------------------------------
    # Terminal -- card reader management
    # ------------------------------------------------------------------

    def create_terminal_reader(
        self,
        *,
        location_id: str,
        registration_code: str,
        label: str | None = None,
    ) -> TerminalReader:
        """Register a physical card reader (e.g. Stripe BBPOS WisePOS E)."""
        payload: dict[str, str] = {
            "location_id": location_id,
            "registration_code": registration_code,
        }
        if label is not None:
            payload["label"] = label
        data = self._http.post("/stripe/terminal/readers", json=payload)
        return TerminalReader.from_dict(data)

    def capture_terminal_payment(
        self,
        reader_id: str,
        amount: int,
        *,
        currency: str | None = None,
        description: str | None = None,
    ) -> TerminalPayment:
        """Present a payment to a terminal reader for collection."""
        payload: dict[str, Any] = {"amount": amount}
        if currency is not None:
            payload["currency"] = currency
        if description is not None:
            payload["description"] = description
        data = self._http.post(
            f"/stripe/terminal/readers/{reader_id}/process",
            json=payload,
        )
        return TerminalPayment.from_dict(data)
