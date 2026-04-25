"""Feature gating and policy evaluation.

Wraps the Olympus Gating Engine (10-level policy hierarchy) via the Go API Gateway.
Routes: ``/policies/evaluate``, ``/gating/*``, ``/feature-flags/*``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from olympus_sdk.models.common import PolicyResult

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


@dataclass
class PlanEntry:
    """Single tier in the plan matrix returned by `/platform/gating/plan-details` (#3313)."""

    tier_id: str
    display_name: str
    monthly_price_usd: float | None
    features: Any
    usage_limits: Any
    ranks_higher_than_current: bool
    is_current: bool
    diff_vs_current: list[str] = field(default_factory=list)
    contact_sales: bool = False


@dataclass
class PlanDetails:
    """Response shape for `GET /platform/gating/plan-details` (#3313)."""

    current_plan: str | None
    plans: list[PlanEntry]
    as_of: str


class GatingService:
    """Feature gating and policy evaluation."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def is_enabled(self, feature_key: str) -> bool:
        """Check whether a feature key is enabled for the current context."""
        data = self._http.post("/policies/evaluate", json={"policy_key": feature_key})
        return bool(
            data.get("allowed")
            or data.get("enabled")
            or data.get("value") is True
        )

    def get_policy(self, policy_key: str) -> Any:
        """Get the raw policy value for a key.

        Returns the server-resolved value, which may be a bool, int, str,
        or dict depending on the policy definition.
        """
        data = self._http.post("/policies/evaluate", json={"policy_key": policy_key})
        return data.get("value") or data.get("result")

    def evaluate(self, policy_key: str, context: dict[str, Any]) -> PolicyResult:
        """Evaluate a policy key with additional context parameters.

        The ``context`` dict can include location_id, device_id, user_id, etc.
        to influence the 10-level policy resolution hierarchy.
        """
        data = self._http.post("/policies/evaluate", json={
            "policy_key": policy_key,
            "context": context,
        })
        return PolicyResult.from_dict(data)

    def evaluate_batch(
        self,
        policy_keys: list[str],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, PolicyResult]:
        """Batch evaluate multiple policy keys at once."""
        payload: dict[str, Any] = {"policy_keys": policy_keys}
        if context is not None:
            payload["context"] = context
        data = self._http.post("/policies/evaluate/batch", json=payload)
        results_raw = data.get("results") or {}
        return {k: PolicyResult.from_dict(v) for k, v in results_raw.items()}

    def list_feature_flags(self) -> list[dict[str, Any]]:
        """List feature flags for the tenant."""
        data = self._http.get("/feature-flags")
        return data.get("feature_flags") or data.get("data") or []

    def get_plan_details(self, *, tenant_id: str | None = None) -> PlanDetails:
        """Fetch the full plan matrix + caller's `current_plan` + per-tier
        `diff_vs_current` for a contextual upgrade UI (#3313).

        ``tenant_id`` is optional — when omitted, the platform uses the JWT's
        tenant. Cross-tenant lookup requires tenant_admin or higher.
        """
        params: dict[str, str] = {}
        if tenant_id:
            params["tenant_id"] = tenant_id
        data = self._http.get("/platform/gating/plan-details", params=params)
        plans_raw = data.get("plans") or []
        return PlanDetails(
            current_plan=data.get("current_plan"),
            plans=[
                PlanEntry(
                    tier_id=p.get("tier_id", ""),
                    display_name=p.get("display_name", ""),
                    monthly_price_usd=p.get("monthly_price_usd"),
                    features=p.get("features"),
                    usage_limits=p.get("usage_limits"),
                    ranks_higher_than_current=bool(p.get("ranks_higher_than_current", False)),
                    is_current=bool(p.get("is_current", False)),
                    diff_vs_current=list(p.get("diff_vs_current") or []),
                    contact_sales=bool(p.get("contact_sales", False)),
                )
                for p in plans_raw
            ],
            as_of=data.get("as_of", ""),
        )
