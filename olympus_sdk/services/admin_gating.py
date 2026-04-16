"""Admin API for gating / feature flag management.

Provides CRUD for feature definitions, plan-level feature assignment,
resource limits, and evaluation. Distinct from :class:`GatingService`
which is the tenant-facing policy evaluation API.
Routes: ``/admin/gating/*``.

Requires: admin role (super_admin, platform_admin).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class AdminGatingService:
    """Admin API for gating / feature flag management."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Feature Definitions
    # ------------------------------------------------------------------

    def define_feature(
        self,
        key: str,
        *,
        description: str | None = None,
        enabled: bool = False,
    ) -> dict[str, Any]:
        """Define a new feature flag."""
        return self._http.post(
            "/admin/gating/features",
            json={
                "key": key,
                "description": description,
                "enabled": enabled,
            },
        )

    def update_feature(
        self, key: str, updates: dict[str, Any]
    ) -> None:
        """Update an existing feature flag."""
        self._http.put(f"/admin/gating/features/{key}", json=updates)

    def list_features(self) -> list[dict[str, Any]]:
        """List all defined feature flags."""
        data = self._http.get("/admin/gating/features")
        return data.get("features") or data.get("data") or []

    # ------------------------------------------------------------------
    # Plan-Level Feature Assignment
    # ------------------------------------------------------------------

    def set_plan_features(
        self, plan_id: str, feature_keys: list[str]
    ) -> None:
        """Set the list of feature keys enabled for a billing plan."""
        self._http.put(
            f"/admin/gating/plans/{plan_id}/features",
            json={"feature_keys": feature_keys},
        )

    def get_plan_features(self, plan_id: str) -> dict[str, Any]:
        """Get the features assigned to a billing plan."""
        return self._http.get(f"/admin/gating/plans/{plan_id}/features")

    # ------------------------------------------------------------------
    # Resource Limits
    # ------------------------------------------------------------------

    def set_resource_limit(
        self, plan_id: str, resource: str, limit: int
    ) -> None:
        """Set a resource limit for a billing plan (e.g. max_agents, max_voice_min)."""
        self._http.put(
            f"/admin/gating/plans/{plan_id}/limits/{resource}",
            json={"limit": limit},
        )

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_feature(
        self,
        feature_key: str,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate a feature flag with optional tenant/user context."""
        payload: dict[str, Any] = {"feature_key": feature_key}
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        if user_id is not None:
            payload["user_id"] = user_id
        return self._http.post("/admin/gating/evaluate", json=payload)
