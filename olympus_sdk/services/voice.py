"""Voice AI: caller profiles, escalation, business hours, and V2-005 cascade resolver.

Wraps the Olympus Voice AI service via the Go API Gateway.
Routes: ``/voice/*``, ``/voice-agents/configs/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from olympus_sdk.models.voice_v2 import VoiceEffectiveConfig, VoicePipeline

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class VoiceService:
    """Voice AI: caller profiles, escalation configuration, and business hours."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Caller Profiles
    # ------------------------------------------------------------------

    async def get_caller_profile(self, caller_id: str) -> dict:
        """Get a caller profile by ID."""
        return self._http.get(f"/voice/callers/{caller_id}")

    async def list_caller_profiles(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> dict:
        """List caller profiles with optional pagination."""
        return self._http.get(
            "/voice/callers",
            params={"page": page, "limit": limit},
        )

    async def upsert_caller_profile(
        self,
        *,
        phone_number: str,
        name: str | None = None,
        preferences: dict[str, Any] | None = None,
        notes: str | None = None,
    ) -> dict:
        """Create or update a caller profile by phone number."""
        payload: dict[str, Any] = {"phone_number": phone_number}
        if name is not None:
            payload["name"] = name
        if preferences is not None:
            payload["preferences"] = preferences
        if notes is not None:
            payload["notes"] = notes
        return self._http.put("/voice/callers", json=payload)

    async def delete_caller_profile(self, caller_id: str) -> dict:
        """Delete a caller profile."""
        self._http.delete(f"/voice/callers/{caller_id}")
        return {}

    async def record_caller_order(
        self,
        caller_id: str,
        *,
        order_id: str,
        items: list[dict[str, Any]] | None = None,
    ) -> dict:
        """Record an order associated with a caller profile."""
        payload: dict[str, Any] = {"order_id": order_id}
        if items is not None:
            payload["items"] = items
        return self._http.post(f"/voice/callers/{caller_id}/orders", json=payload)

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------

    async def get_escalation_config(self) -> dict:
        """Get the current voice escalation configuration."""
        return self._http.get("/voice/escalation/config")

    async def update_escalation_config(
        self,
        *,
        enabled: bool | None = None,
        triggers: list[str] | None = None,
        target_phone: str | None = None,
        max_retries: int | None = None,
    ) -> dict:
        """Update the voice escalation configuration."""
        payload: dict[str, Any] = {}
        if enabled is not None:
            payload["enabled"] = enabled
        if triggers is not None:
            payload["triggers"] = triggers
        if target_phone is not None:
            payload["target_phone"] = target_phone
        if max_retries is not None:
            payload["max_retries"] = max_retries
        return self._http.patch("/voice/escalation/config", json=payload)

    # ------------------------------------------------------------------
    # Business Hours
    # ------------------------------------------------------------------

    async def get_business_hours(self) -> dict:
        """Get the configured business hours for voice AI."""
        return self._http.get("/voice/business-hours")

    async def update_business_hours(
        self,
        *,
        schedule: list[dict[str, Any]],
        timezone: str | None = None,
    ) -> dict:
        """Update the business hours schedule for voice AI.

        ``schedule`` is a list of day-specific hour entries, e.g.
        ``[{"day": "monday", "open": "09:00", "close": "17:00"}]``.
        """
        payload: dict[str, Any] = {"schedule": schedule}
        if timezone is not None:
            payload["timezone"] = timezone
        return self._http.put("/voice/business-hours", json=payload)

    # ------------------------------------------------------------------
    # V2-005 — Cascade resolver (effective-config + pipeline)
    # ------------------------------------------------------------------

    async def get_effective_config(self, agent_id: str) -> VoiceEffectiveConfig:
        """Resolve the effective voice-agent configuration after cascading
        platform → app → tenant → agent voice defaults.

        Backing endpoint: ``GET /api/v1/voice-agents/configs/{id}/effective-config``
        (Python cascade resolver — V2-005, issue
        OlympusCloud/olympus-cloud-gcp#3162).
        """
        data = self._http.get(f"/voice-agents/configs/{agent_id}/effective-config")
        return VoiceEffectiveConfig.from_dict(data)

    async def get_pipeline(self, agent_id: str) -> VoicePipeline:
        """Resolve only the pipeline view of an agent's configuration.

        Cheaper than :meth:`get_effective_config` when callers only need the
        pipeline name + config.

        Backing endpoint: ``GET /api/v1/voice-agents/configs/{id}/pipeline``.
        """
        data = self._http.get(f"/voice-agents/configs/{agent_id}/pipeline")
        return VoicePipeline.from_dict(data)
