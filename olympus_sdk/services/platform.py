"""Platform onboarding, tenant provisioning, and health checks.

Wraps the Olympus Platform service (Rust) via the Go API Gateway.
Routes: ``/platform/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class PlatformService:
    """Platform onboarding, tenant provisioning, and health checks."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    async def signup(
        self,
        *,
        company_name: str,
        owner_email: str,
        owner_name: str,
        plan: str | None = None,
    ) -> dict:
        """Sign up a new company and provision a tenant.

        Creates the company, owner user, and initial tenant resources.
        """
        payload: dict[str, Any] = {
            "company_name": company_name,
            "owner_email": owner_email,
            "owner_name": owner_name,
        }
        if plan is not None:
            payload["plan"] = plan
        return self._http.post("/platform/signup", json=payload)

    async def cleanup(self, tenant_id: str) -> dict:
        """Deprovision and clean up a tenant's resources."""
        return self._http.post(f"/platform/tenants/{tenant_id}/cleanup")

    async def get_tenant_status(self, tenant_id: str) -> dict:
        """Get the provisioning status of a tenant."""
        return self._http.get(f"/platform/tenants/{tenant_id}/status")

    async def get_tenant_health(self, tenant_id: str) -> dict:
        """Get the health status of a tenant's services."""
        return self._http.get(f"/platform/tenants/{tenant_id}/health")

    async def get_onboarding_progress(self, tenant_id: str) -> dict:
        """Get onboarding progress and remaining setup steps."""
        return self._http.get(f"/platform/tenants/{tenant_id}/onboarding")
