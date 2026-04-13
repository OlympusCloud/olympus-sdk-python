"""Enterprise Context: Company 360 for AI agents (#2993).

Wraps the Olympus Enterprise Context service via the Go API Gateway.
Returns complete tenant context (brand, locations, menu, specials, FAQs,
upsells, inventory, caller profile, graph relationships) in a single call.
Routes: ``/enterprise-context/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class EnterpriseContextService:
    """Enterprise Context: full Company 360 assembly for AI agents."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def get(
        self,
        tenant_id: str,
        location_id: str | None = None,
        *,
        agent_type: str | None = None,
        caller_phone: str | None = None,
    ) -> dict[str, Any]:
        """Assemble complete Company 360 context for an AI agent.

        Returns all tenant data (brand, locations, menu, specials, FAQs,
        upsells, inventory, caller profile, graph relationships) in a
        single response. Cached for 5 minutes per (tenant_id, location_id).

        Args:
            tenant_id: The tenant to retrieve context for.
            location_id: Optional specific location. When *None*, returns
                context for the default location.
            agent_type: Agent type requesting context: ``voice``, ``chat``,
                ``pantheon``, or ``workflow``. Defaults to ``voice``.
            caller_phone: Optional caller phone number for profile lookup.
        """
        path = f"/enterprise-context/{tenant_id}"
        if location_id is not None:
            path = f"/enterprise-context/{tenant_id}/{location_id}"
        return self._http.get(
            path,
            params={"agent_type": agent_type, "caller_phone": caller_phone},
        )
