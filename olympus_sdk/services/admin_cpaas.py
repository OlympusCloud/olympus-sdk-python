"""Admin API for managing CPaaS provider configuration and health.

Controls the Telnyx-primary / Twilio-fallback routing layer, provider
preferences per scope (tenant, brand, location), and circuit-breaker health.
Routes: ``/admin/cpaas/*``.

Requires: admin role (super_admin, platform_admin).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class AdminCpaasService:
    """Admin API for managing CPaaS provider configuration and health."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def set_provider_preference(
        self,
        scope: str,
        scope_id: str,
        provider: str,
    ) -> dict[str, Any]:
        """Set the preferred CPaaS provider for a given scope.

        *scope* is one of ``tenant``, ``brand``, or ``location``.
        *scope_id* is the ID of the scoped entity.
        *provider* is ``telnyx`` or ``twilio``.
        """
        return self._http.put(
            "/admin/cpaas/provider-preference",
            json={
                "scope": scope,
                "scope_id": scope_id,
                "provider": provider,
            },
        )

    def get_provider_health(self) -> dict[str, Any]:
        """Get the current health status of all CPaaS providers.

        Includes circuit-breaker state, latency, and failure counts.
        """
        return self._http.get("/admin/cpaas/health")
