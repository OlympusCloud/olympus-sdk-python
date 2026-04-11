"""Subscription billing, usage metering, invoices, and plan management.

Wraps the Olympus Billing service (Rust Platform + Stripe) via the Go API Gateway.
Routes: ``/billing/*``, ``/platform/subscription``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from olympus_sdk.models.billing import Invoice, Plan, UsageReport

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class BillingService:
    """Subscription billing, usage metering, invoices, and plan management."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def get_current_plan(self) -> Plan:
        """Get the current subscription plan for the tenant."""
        data = self._http.get("/billing/subscription")
        return Plan.from_dict(data)

    def get_usage(self, *, period: str | None = None) -> UsageReport:
        """Get resource usage for the current billing period."""
        data = self._http.get("/billing/stats", params={"period": period})
        return UsageReport.from_dict(data)

    def get_invoices(self) -> list[Invoice]:
        """List invoices for the tenant."""
        data = self._http.get("/billing/invoices")
        items_raw = data.get("invoices") or data.get("data") or []
        return [Invoice.from_dict(i) for i in items_raw]

    def get_invoice(self, invoice_id: str) -> Invoice:
        """Get a single invoice by ID."""
        data = self._http.get(f"/billing/invoices/{invoice_id}")
        return Invoice.from_dict(data)

    def get_invoice_pdf(self, invoice_id: str) -> str:
        """Download an invoice PDF. Returns the PDF URL."""
        data = self._http.get(f"/billing/invoices/{invoice_id}/pdf")
        return data.get("url") or data.get("pdf_url", "")

    def upgrade_plan(self, plan_id: str) -> Plan:
        """Upgrade (or downgrade) to a different plan."""
        data = self._http.put("/billing/subscription/plan", json={"plan_id": plan_id})
        return Plan.from_dict(data)

    def list_plans(self) -> list[Plan]:
        """List all available billing plans."""
        data = self._http.get("/platform/billing/plans")
        items_raw = data.get("plans") or data.get("data") or []
        return [Plan.from_dict(p) for p in items_raw]

    def add_payment_method(self, method: dict[str, Any]) -> dict[str, Any]:
        """Add a payment method."""
        return self._http.post("/billing/payment-methods", json=method)

    def remove_payment_method(self, method_id: str) -> None:
        """Remove a payment method."""
        self._http.delete(f"/billing/payment-methods/{method_id}")
