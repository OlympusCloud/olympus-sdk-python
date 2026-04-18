"""Marketing funnel + pre-conversion lead capture.

Routes: ``/connect/*``, ``/leads``.

Issue OlympusCloud/olympus-cloud-gcp#3108 — the ``/leads`` endpoint is
intentionally unauthenticated so marketing surfaces can POST leads before
the user signs up. Idempotency is email-based over a 1h window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


@dataclass
class UTM:
    """Standard UTM tracking parameters captured from a landing page."""

    source: str | None = None
    medium: str | None = None
    campaign: str | None = None
    term: str | None = None
    content: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.source is not None:
            out["source"] = self.source
        if self.medium is not None:
            out["medium"] = self.medium
        if self.campaign is not None:
            out["campaign"] = self.campaign
        if self.term is not None:
            out["term"] = self.term
        if self.content is not None:
            out["content"] = self.content
        return out


@dataclass
class CreateLeadResponse:
    """Response from ``POST /leads``."""

    lead_id: str
    status: str  # "created" or "deduped"
    created_at: str

    @staticmethod
    def from_dict(data: dict[str, Any]) -> CreateLeadResponse:
        # Tolerate both snake_case (canonical) and camelCase for cross-SDK
        # fixture compatibility.
        return CreateLeadResponse(
            lead_id=data.get("lead_id") or data.get("leadId") or "",
            status=data.get("status", "created"),
            created_at=data.get("created_at") or data.get("createdAt") or "",
        )


class ConnectService:
    """Marketing-funnel operations: leads, identity link, connected providers."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    async def create_lead(
        self,
        *,
        email: str,
        name: str | None = None,
        phone: str | None = None,
        company: str | None = None,
        source: str | None = None,
        utm: UTM | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CreateLeadResponse:
        """Create a pre-conversion lead. Safe to retry — deduplicates on email.

        Backing endpoint: ``POST /api/v1/leads``.
        """
        if not email:
            raise ValueError("email is required")
        body: dict[str, Any] = {"email": email}
        if name is not None:
            body["name"] = name
        if phone is not None:
            body["phone"] = phone
        if company is not None:
            body["company"] = company
        if source is not None:
            body["source"] = source
        if utm is not None:
            body["utm"] = utm.to_dict()
        if metadata is not None:
            body["metadata"] = metadata
        data = self._http.post("/leads", json=body)
        return CreateLeadResponse.from_dict(data)
