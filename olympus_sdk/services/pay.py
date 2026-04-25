"""Payment processing, refunds, balance, payouts, and terminal management.

Wraps the Olympus Payment Orchestration service via the Go API Gateway.
Routes: ``/payments/*``, ``/finance/*``, ``/stripe/terminal/*``,
``/platform/pay/routing*`` (#3312).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote

from olympus_sdk.models.pay import Balance, Payment, Payout, Refund, TerminalPayment, TerminalReader

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


PaymentProcessor = Literal["olympus_pay", "square", "adyen", "worldpay"]


@dataclass
class RoutingConfig:
    """Per-location processor routing config (#3312).

    ``preferred_processor`` and entries in ``fallback_processors`` are
    each one of :data:`PaymentProcessor` but exposed as plain ``str``
    so future server-side additions don't break parsing. ``created_at``
    and ``updated_at`` may be ``None`` on the POST response — the
    server sets them only after the row is committed.
    """

    tenant_id: str
    location_id: str
    preferred_processor: str
    is_active: bool
    fallback_processors: list[str] = field(default_factory=list)
    credentials_secret_ref: str | None = None
    merchant_id: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


def _opt_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _to_routing_config(row: dict[str, Any]) -> RoutingConfig:
    fallback_raw = row.get("fallback_processors") or []
    fallback = [p for p in fallback_raw if isinstance(p, str)]
    is_active_raw = row.get("is_active")
    is_active = is_active_raw if isinstance(is_active_raw, bool) else True
    return RoutingConfig(
        tenant_id=row.get("tenant_id", "") or "",
        location_id=row.get("location_id", "") or "",
        preferred_processor=row.get("preferred_processor", "") or "",
        is_active=is_active,
        fallback_processors=fallback,
        credentials_secret_ref=_opt_str(row.get("credentials_secret_ref")),
        merchant_id=_opt_str(row.get("merchant_id")),
        notes=_opt_str(row.get("notes")),
        created_at=_opt_str(row.get("created_at")),
        updated_at=_opt_str(row.get("updated_at")),
    )


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

    # ------------------------------------------------------------------
    # Payment routing config (#3312)
    # ------------------------------------------------------------------

    def configure_routing(
        self,
        *,
        location_id: str,
        preferred_processor: PaymentProcessor,
        fallback_processors: list[PaymentProcessor] | None = None,
        credentials_secret_ref: str | None = None,
        merchant_id: str | None = None,
        is_active: bool = True,
        notes: str | None = None,
    ) -> RoutingConfig:
        """Configure processor-agnostic routing for a location (#3312).

        ``preferred_processor`` and entries in ``fallback_processors``
        must each be one of: ``olympus_pay``, ``square``, ``adyen``,
        ``worldpay``. The fallback chain cannot include the preferred
        processor (server enforces).

        ``credentials_secret_ref`` must be a Secret Manager secret NAME
        (NOT the credential itself) starting with
        ``olympus-merchant-credentials-`` per the canonical secrets
        schema. Plaintext API keys are rejected at the server.
        """
        payload: dict[str, Any] = {
            "location_id": location_id,
            "preferred_processor": preferred_processor,
            "fallback_processors": list(fallback_processors or []),
            "is_active": is_active,
        }
        if credentials_secret_ref is not None:
            payload["credentials_secret_ref"] = credentials_secret_ref
        if merchant_id is not None:
            payload["merchant_id"] = merchant_id
        if notes is not None:
            payload["notes"] = notes
        data = self._http.post("/platform/pay/routing", json=payload)
        return _to_routing_config(data)

    def get_routing(self, *, location_id: str) -> RoutingConfig:
        """Read the current routing config for a location (#3312).

        Raises :class:`~olympus_sdk.errors.OlympusApiError` (404) when
        no routing config exists for the location.
        """
        data = self._http.get(
            f"/platform/pay/routing/{quote(location_id, safe='')}"
        )
        return _to_routing_config(data)
