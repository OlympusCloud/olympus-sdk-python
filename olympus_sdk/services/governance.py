"""GovernanceService — policy exception framework.

olympus-cloud-gcp#3254 for the Python SDK. See §17 of
docs/platform/APP-SCOPED-PERMISSIONS.md.

Narrow scope — two policy keys at launch:
    - ``session_ttl_role_ceiling`` — extend role TTL for a specific app+role
    - ``grace_policy_category``    — override whole-app grace policy

No approve/deny/revoke in the SDK — those are Cockpit-only actions requiring
platform_admin JWT. SDK callers file + list + get status.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

from olympus_sdk.http import OlympusHttpClient

PolicyKey = Literal["session_ttl_role_ceiling", "grace_policy_category"]

ExceptionStatus = Literal[
    "requested",
    "auto_approved",
    "pending_review",
    "approved",
    "denied",
    "expired_grace",
    "expired",
    "revoked",
]

RiskTier = Literal["low", "medium", "high"]


@dataclass
class ExceptionRequest:
    """A policy exception record."""

    exception_id: str
    app_id: str
    policy_key: PolicyKey
    requested_value: dict[str, Any]
    justification: str
    risk_tier: RiskTier
    risk_score: float
    risk_rationale: str
    status: ExceptionStatus
    expires_at: str
    created_at: str
    updated_at: str
    tenant_id: str | None = None
    reviewer_id: str | None = None
    reviewed_at: str | None = None
    reviewer_notes: str | None = None
    revoked_at: str | None = None
    revoke_reason: str | None = None


class GovernanceService:
    """Policy exception framework surface."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def request_exception(
        self,
        *,
        policy_key: PolicyKey,
        requested_value: dict[str, Any],
        justification: str,
        tenant_id: str | None = None,
    ) -> ExceptionRequest:
        """File a new policy exception request.

        Platform auto-scores and routes to ``auto_approved`` (low risk) or
        ``pending_review`` (medium/high). Justification must be ≥ 100 chars.
        """
        payload: dict[str, Any] = {
            "policy_key": policy_key,
            "requested_value": requested_value,
            "justification": justification,
        }
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        body = self._http.post("/api/v1/platform/exceptions", json=payload)
        return _to_exception(body)

    def list_exceptions(
        self,
        *,
        app_id: str | None = None,
        status: ExceptionStatus | None = None,
    ) -> list[ExceptionRequest]:
        """List exceptions, optionally filtered by app_id + status."""
        params: dict[str, str] = {}
        if app_id is not None:
            params["app_id"] = app_id
        if status is not None:
            params["status"] = status
        body = self._http.get("/api/v1/platform/exceptions", params=params)
        rows = body.get("exceptions", []) or []
        return [_to_exception(row) for row in rows]

    def get_exception(self, exception_id: str) -> ExceptionRequest:
        """Fetch a single exception by ID."""
        body = self._http.get(
            f"/api/v1/platform/exceptions/{quote(exception_id, safe='')}",
        )
        return _to_exception(body)


def _to_exception(row: dict[str, Any]) -> ExceptionRequest:
    return ExceptionRequest(
        exception_id=row.get("exception_id", ""),
        app_id=row.get("app_id", ""),
        tenant_id=row.get("tenant_id"),
        policy_key=row.get("policy_key", "session_ttl_role_ceiling"),
        requested_value=row.get("requested_value", {}),
        justification=row.get("justification", ""),
        risk_tier=row.get("risk_tier", "low"),
        risk_score=float(row.get("risk_score", 0)),
        risk_rationale=row.get("risk_rationale", ""),
        status=row.get("status", "requested"),
        expires_at=row.get("expires_at", ""),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
        reviewer_id=row.get("reviewer_id"),
        reviewed_at=row.get("reviewed_at"),
        reviewer_notes=row.get("reviewer_notes"),
        revoked_at=row.get("revoked_at"),
        revoke_reason=row.get("revoke_reason"),
    )
