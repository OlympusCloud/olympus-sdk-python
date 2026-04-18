"""Admin API for billing plan management, add-ons, minute packs, and usage metering.

Distinct from :class:`BillingService` which is the tenant-facing billing API.
This service manages the global plan catalog and usage recording.
Routes: ``/admin/billing/*``.

Requires: admin role (super_admin, platform_admin).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class AdminBillingService:
    """Admin API for billing plan management, add-ons, minute packs, and usage."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Plan CRUD
    # ------------------------------------------------------------------

    def create_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Create a new billing plan in the catalog."""
        return self._http.post("/admin/billing/plans", json=plan)

    def update_plan(
        self, plan_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing billing plan."""
        return self._http.put(
            f"/admin/billing/plans/{plan_id}", json=updates
        )

    def delete_plan(self, plan_id: str) -> None:
        """Delete a billing plan. Fails if tenants are actively subscribed."""
        self._http.delete(f"/admin/billing/plans/{plan_id}")

    def list_plans(self) -> list[dict[str, Any]]:
        """List all billing plans in the catalog."""
        data = self._http.get("/admin/billing/plans")
        return data.get("plans") or data.get("data") or []

    # ------------------------------------------------------------------
    # Add-ons & Minute Packs
    # ------------------------------------------------------------------

    def create_addon(self, addon: dict[str, Any]) -> dict[str, Any]:
        """Create a purchasable add-on (e.g. extra SMS bundle, premium support)."""
        return self._http.post("/admin/billing/addons", json=addon)

    def create_minute_pack(self, pack: dict[str, Any]) -> dict[str, Any]:
        """Create a minute pack (pre-paid voice minutes bundle)."""
        return self._http.post("/admin/billing/minute-packs", json=pack)

    # ------------------------------------------------------------------
    # Usage Metering
    # ------------------------------------------------------------------

    def get_usage(
        self,
        tenant_id: str,
        *,
        meter_type: str | None = None,
    ) -> dict[str, Any]:
        """Get usage data for a tenant, optionally filtered by meter type."""
        return self._http.get(
            f"/admin/billing/usage/{tenant_id}",
            params={"meter_type": meter_type},
        )

    def record_usage(
        self,
        tenant_id: str,
        meter_type: str,
        quantity: float,
    ) -> None:
        """Record a usage event for a tenant's meter."""
        self._http.post(
            f"/admin/billing/usage/{tenant_id}",
            json={
                "meter_type": meter_type,
                "quantity": quantity,
            },
        )
