"""Voice AI platform: agent configs, conversations, campaigns, phone numbers,
marketplace voices, calls, speaker profiles, analytics, and the edge voice
pipeline (STT → Ether → TTS via CF Containers).

Routes: ``/voice-agents/*``, ``/voice/phone-numbers/*``,
``/voice/marketplace/*``, ``/voice/calls/*``, ``/voice/speaker/*``,
``/voice/profiles/*``, ``/voice/process`` (edge pipeline REST),
``/ws/voice`` (edge pipeline WebSocket).

Includes the V2-005 cascade resolver (issue #3162):
``GET /voice-agents/configs/{id}/effective-config`` →
:class:`~olympus_sdk.models.voice_v2.VoiceEffectiveConfig` and
``GET /voice-agents/configs/{id}/pipeline`` →
:class:`~olympus_sdk.models.voice_v2.VoicePipeline`.

Methods are **synchronous** to match the rest of the Python SDK
(see ``http.py``). Prior versions used ``async def`` signatures with
blocking HTTP calls underneath; callers of those broken signatures must
drop the ``await`` and switch to the names below.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from olympus_sdk.models.voice_v2 import VoiceEffectiveConfig, VoicePipeline

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


def _list_from(
    body: dict[str, Any] | None,
    *,
    primary_key: str,
    fallbacks: tuple[str, ...] = ("data",),
) -> list[dict[str, Any]]:
    """Extract a list of row dicts from ``{primary_key: [...]}`` or a
    fallback envelope (defaults to ``{data: [...]}``). Mirrors the dart
    ``?? json['data']`` chain.
    """
    if not isinstance(body, dict):
        return []
    candidates = (primary_key,) + tuple(fallbacks)
    for key in candidates:
        value = body.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


class VoiceService:
    """Voice AI platform surface — agents, conversations, campaigns, numbers,
    marketplace, calls, speakers, profiles, caller profiles, escalation, and
    the edge voice pipeline.
    """

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Agents (configs)
    # ------------------------------------------------------------------

    def list_configs(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all voice agent configurations."""
        params: dict[str, Any] = {"page": page, "limit": limit}
        if tenant_id is not None:
            params["tenant_id"] = tenant_id
        body = self._http.get("/voice-agents/configs", params=params)
        return _list_from(body, primary_key="configs")

    def get_config(self, config_id: str) -> dict[str, Any]:
        """Get a single voice agent configuration."""
        return self._http.get(f"/voice-agents/configs/{quote(config_id, safe='')}")

    def create_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Create a new voice agent configuration."""
        return self._http.post("/voice-agents/configs", json=config)

    def update_config(
        self,
        config_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing voice agent configuration."""
        return self._http.put(
            f"/voice-agents/configs/{quote(config_id, safe='')}", json=config
        )

    def delete_config(self, config_id: str) -> None:
        """Delete a voice agent configuration."""
        self._http.delete(f"/voice-agents/configs/{quote(config_id, safe='')}")

    # ------------------------------------------------------------------
    # V2-005 cascade resolver (#3162)
    # ------------------------------------------------------------------

    def get_effective_config(self, agent_id: str) -> VoiceEffectiveConfig:
        """Resolve the effective voice-agent configuration after cascading
        platform → app → tenant → agent voice defaults.

        Backing endpoint:
        ``GET /api/v1/voice-agents/configs/{id}/effective-config``.
        """
        data = self._http.get(
            f"/voice-agents/configs/{quote(agent_id, safe='')}/effective-config"
        )
        return VoiceEffectiveConfig.from_dict(data)

    def get_pipeline(self, agent_id: str) -> VoicePipeline:
        """Resolve only the pipeline view of an agent's configuration.

        Cheaper than :meth:`get_effective_config` when callers only need
        the pipeline name + config.

        Backing endpoint: ``GET /api/v1/voice-agents/configs/{id}/pipeline``.
        """
        data = self._http.get(
            f"/voice-agents/configs/{quote(agent_id, safe='')}/pipeline"
        )
        return VoicePipeline.from_dict(data)

    # ------------------------------------------------------------------
    # Voice pool (persona rotation)
    # ------------------------------------------------------------------

    def get_pool(self, agent_id: str) -> list[Any]:
        """Get the voice pool (persona rotation) for an agent."""
        body = self._http.get(f"/voice-agents/{quote(agent_id, safe='')}/pool")
        if not isinstance(body, dict):
            return []
        for key in ("pool", "entries", "data"):
            value = body.get(key)
            if isinstance(value, list):
                return value
        return []

    def add_to_pool(
        self,
        agent_id: str,
        entry: dict[str, Any],
    ) -> dict[str, Any]:
        """Add a persona to an agent's voice pool."""
        return self._http.post(
            f"/voice-agents/{quote(agent_id, safe='')}/pool", json=entry
        )

    def remove_from_pool(self, agent_id: str, entry_id: str) -> None:
        """Remove a persona from an agent's voice pool."""
        self._http.delete(
            f"/voice-agents/{quote(agent_id, safe='')}/pool/{quote(entry_id, safe='')}"
        )

    # ------------------------------------------------------------------
    # Schedule
    # ------------------------------------------------------------------

    def get_schedule(self, agent_id: str) -> dict[str, Any]:
        """Get the operating schedule for an agent."""
        return self._http.get(f"/voice-agents/{quote(agent_id, safe='')}/schedule")

    def update_schedule(
        self,
        agent_id: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Update the operating schedule for an agent."""
        return self._http.put(
            f"/voice-agents/{quote(agent_id, safe='')}/schedule", json=request
        )

    # ------------------------------------------------------------------
    # Provisioning wizard
    # ------------------------------------------------------------------

    def provision_agent(
        self,
        *,
        agent_id: str,
        tenant_id: str,
        voice_name: str,
        profile: dict[str, Any],
        greeting_text: str,
    ) -> dict[str, Any]:
        """Start the provisioning wizard for a new agent."""
        return self._http.post(
            f"/ether/voice/agents/{quote(agent_id, safe='')}/provision-wizard",
            json={
                "tenant_id": tenant_id,
                "voice_name": voice_name,
                "profile": profile,
                "greeting_text": greeting_text,
            },
        )

    def get_provisioning_status(
        self,
        agent_id: str,
        job_id: str,
    ) -> dict[str, Any]:
        """Get the current status of a provisioning job."""
        return self._http.get(
            f"/ether/voice/agents/{quote(agent_id, safe='')}/provisioning-status",
            params={"job_id": job_id},
        )

    # ------------------------------------------------------------------
    # Self-service agent CRUD (dart aliases over configs)
    # ------------------------------------------------------------------

    def list_agents(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List all voice agents for the current tenant. Alias for
        :meth:`list_configs`.
        """
        return self.list_configs(page=page, limit=limit)

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        """Get a single agent by ID. Alias for :meth:`get_config`."""
        return self.get_config(agent_id)

    def create_agent(
        self,
        *,
        from_template_id: str | None = None,
        name: str | None = None,
        voice_id: str | None = None,
        persona: str | None = None,
        greeting: str | None = None,
        phone_number: str | None = None,
        location_id: str | None = None,
        ambiance_config: dict[str, Any] | None = None,
        voice_overrides: dict[str, Any] | None = None,
        business_hours: dict[str, Any] | None = None,
        escalation_rules: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a new voice agent."""
        payload: dict[str, Any] = {}
        if from_template_id is not None:
            payload["from_template_id"] = from_template_id
        if name is not None:
            payload["name"] = name
        if voice_id is not None:
            payload["voice_id"] = voice_id
        if persona is not None:
            payload["persona"] = persona
        if greeting is not None:
            payload["greeting"] = greeting
        if phone_number is not None:
            payload["phone_number"] = phone_number
        if location_id is not None:
            payload["location_id"] = location_id
        if ambiance_config is not None:
            payload["ambiance_config"] = ambiance_config
        if voice_overrides is not None:
            payload["voice_overrides"] = voice_overrides
        if business_hours is not None:
            payload["business_hours"] = business_hours
        if escalation_rules is not None:
            payload["escalation_rules"] = escalation_rules
        return self._http.post("/voice-agents/configs", json=payload)

    def update_agent(
        self,
        agent_id: str,
        *,
        name: str | None = None,
        voice_id: str | None = None,
        persona: str | None = None,
        greeting: str | None = None,
        ambiance_config: dict[str, Any] | None = None,
        voice_overrides: dict[str, Any] | None = None,
        business_hours: dict[str, Any] | None = None,
        escalation_rules: list[dict[str, Any]] | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        """Update mutable fields on an existing agent."""
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if voice_id is not None:
            payload["voice_id"] = voice_id
        if persona is not None:
            payload["persona"] = persona
        if greeting is not None:
            payload["greeting"] = greeting
        if ambiance_config is not None:
            payload["ambiance_config"] = ambiance_config
        if voice_overrides is not None:
            payload["voice_overrides"] = voice_overrides
        if business_hours is not None:
            payload["business_hours"] = business_hours
        if escalation_rules is not None:
            payload["escalation_rules"] = escalation_rules
        if is_active is not None:
            payload["is_active"] = is_active
        return self._http.put(
            f"/voice-agents/configs/{quote(agent_id, safe='')}", json=payload
        )

    def delete_agent(self, agent_id: str) -> None:
        """Delete a voice agent. Alias for :meth:`delete_config`."""
        self.delete_config(agent_id)

    def clone_agent(
        self,
        agent_id: str,
        *,
        new_name: str | None = None,
        phone_number: str | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Clone an existing agent."""
        payload: dict[str, Any] = {}
        if new_name is not None:
            payload["new_name"] = new_name
        if phone_number is not None:
            payload["phone_number"] = phone_number
        if location_id is not None:
            payload["location_id"] = location_id
        return self._http.post(
            f"/voice-agents/configs/{quote(agent_id, safe='')}/clone", json=payload
        )

    def preview_agent_voice(
        self,
        agent_id: str,
        *,
        sample_text: str,
        voice_id: str | None = None,
        voice_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a TTS preview clip for an agent."""
        payload: dict[str, Any] = {"sample_text": sample_text}
        if voice_id is not None:
            payload["voice_id"] = voice_id
        if voice_overrides is not None:
            payload["voice_overrides"] = voice_overrides
        return self._http.post(
            f"/voice-agents/configs/{quote(agent_id, safe='')}/preview", json=payload
        )

    def list_gemini_voices(
        self,
        *,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        """List the catalog of available Gemini Live voices."""
        params: dict[str, Any] = {}
        if language is not None:
            params["language"] = language
        body = self._http.get("/voice/voices", params=params)
        return _list_from(body, primary_key="voices")

    # ------------------------------------------------------------------
    # Persona library
    # ------------------------------------------------------------------

    def list_personas(
        self,
        *,
        category: str | None = None,
        industry: str | None = None,
        premium_only: bool | None = None,
    ) -> list[dict[str, Any]]:
        """List curated voice personas."""
        params: dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        if industry is not None:
            params["industry"] = industry
        if premium_only is not None:
            # dart serializes as string — preserve for wire compat
            params["premium_only"] = "true" if premium_only else "false"
        body = self._http.get("/voice/personas", params=params)
        return _list_from(body, primary_key="personas")

    def get_persona(self, id_or_slug: str) -> dict[str, Any]:
        """Get a single persona by ID or slug."""
        return self._http.get(f"/voice/personas/{quote(id_or_slug, safe='')}")

    def apply_persona_to_agent(
        self,
        agent_id: str,
        persona_id_or_slug: str,
    ) -> dict[str, Any]:
        """Apply a persona to an existing agent."""
        return self._http.post(
            f"/voice-agents/configs/{quote(agent_id, safe='')}/apply-persona",
            json={"persona": persona_id_or_slug},
        )

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def list_agent_templates(
        self,
        *,
        scope: str | None = None,
    ) -> list[dict[str, Any]]:
        """List voice-agent templates."""
        params: dict[str, Any] = {}
        if scope is not None:
            params["scope"] = scope
        body = self._http.get("/voice-agents/templates", params=params)
        return _list_from(body, primary_key="templates")

    def instantiate_agent_template(
        self,
        template_id: str,
        *,
        name: str,
        phone_number: str | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Instantiate a new agent from an existing template."""
        payload: dict[str, Any] = {"name": name}
        if phone_number is not None:
            payload["phone_number"] = phone_number
        if location_id is not None:
            payload["location_id"] = location_id
        return self._http.post(
            f"/voice-agents/templates/{quote(template_id, safe='')}/instantiate",
            json=payload,
        )

    def publish_agent_as_template(
        self,
        agent_id: str,
        *,
        scope: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Publish the current agent as a template."""
        payload: dict[str, Any] = {"scope": scope}
        if description is not None:
            payload["description"] = description
        return self._http.post(
            f"/voice-agents/configs/{quote(agent_id, safe='')}/publish-template",
            json=payload,
        )

    def list_templates(self) -> list[dict[str, Any]]:
        """List available agent templates (no filter)."""
        return _list_from(
            self._http.get("/voice-agents/templates"), primary_key="templates"
        )

    # ------------------------------------------------------------------
    # Background ambiance
    # ------------------------------------------------------------------

    def list_ambiance_library(
        self,
        *,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """List the curated library of ambient beds."""
        params: dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        body = self._http.get("/voice/ambiance/library", params=params)
        return _list_from(body, primary_key="beds")

    def upload_ambiance_bed(
        self,
        audio_bytes: bytes,
        *,
        name: str,
        time_of_day: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Upload a custom ambient bed. Audio is sent as base64."""
        payload: dict[str, Any] = {
            "name": name,
            "audio_base64": base64.b64encode(bytes(audio_bytes)).decode("ascii"),
        }
        if time_of_day is not None:
            payload["time_of_day"] = time_of_day
        if description is not None:
            payload["description"] = description
        return self._http.post("/voice/ambiance/upload", json=payload)

    def update_agent_ambiance(
        self,
        agent_id: str,
        *,
        enabled: bool | None = None,
        intensity: float | None = None,
        default_r2_key: str | None = None,
        time_of_day_variants: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Update an agent's ambiance configuration."""
        payload: dict[str, Any] = {}
        if enabled is not None:
            payload["enabled"] = enabled
        if intensity is not None:
            payload["intensity"] = intensity
        if default_r2_key is not None:
            payload["default_r2_key"] = default_r2_key
        if time_of_day_variants is not None:
            payload["time_of_day_variants"] = time_of_day_variants
        return self._http.patch(
            f"/voice-agents/configs/{quote(agent_id, safe='')}/ambiance", json=payload
        )

    def update_agent_voice_overrides(
        self,
        agent_id: str,
        *,
        pitch: float | None = None,
        speed: float | None = None,
        warmth: float | None = None,
        regional_dialect: str | None = None,
    ) -> dict[str, Any]:
        """Update an agent's voice-tuning overrides."""
        payload: dict[str, Any] = {}
        if pitch is not None:
            payload["pitch"] = pitch
        if speed is not None:
            payload["speed"] = speed
        if warmth is not None:
            payload["warmth"] = warmth
        if regional_dialect is not None:
            payload["regional_dialect"] = regional_dialect
        return self._http.patch(
            f"/voice-agents/configs/{quote(agent_id, safe='')}/voice-overrides",
            json=payload,
        )

    # ------------------------------------------------------------------
    # Workflow templates
    # ------------------------------------------------------------------

    def list_workflow_templates(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List workflow templates for the current tenant."""
        body = self._http.get(
            "/voice/workflow-templates",
            params={"page": page, "limit": limit},
        )
        return _list_from(body, primary_key="templates")

    def create_workflow_template(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new workflow template."""
        return self._http.post("/voice/workflow-templates", json=request)

    def get_workflow_template(self, template_id: str) -> dict[str, Any]:
        """Get a single workflow template by ID."""
        return self._http.get(f"/voice/workflow-templates/{quote(template_id, safe='')}")

    def delete_workflow_template(self, template_id: str) -> None:
        """Delete a workflow template."""
        self._http.delete(f"/voice/workflow-templates/{quote(template_id, safe='')}")

    def create_workflow_instance(
        self,
        template_id: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Instantiate a workflow from a template."""
        return self._http.post(
            f"/voice/workflow-templates/{quote(template_id, safe='')}/instances",
            json=params,
        )

    # ------------------------------------------------------------------
    # Voicemail
    # ------------------------------------------------------------------

    def list_voicemails(
        self,
        *,
        caller_phone: str | None = None,
        page: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List voicemails for the tenant."""
        params: dict[str, Any] = {"page": page, "limit": limit}
        if caller_phone is not None:
            params["caller_phone"] = caller_phone
        body = self._http.get("/voice/voicemails", params=params)
        return _list_from(body, primary_key="voicemails")

    def update_voicemail(
        self,
        voicemail_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a voicemail (mark as read, resolve)."""
        return self._http.patch(
            f"/voice/voicemails/{quote(voicemail_id, safe='')}", json=data
        )

    def get_voicemail_audio_url(self, voicemail_id: str) -> dict[str, Any]:
        """Get a signed URL for a voicemail audio recording."""
        return self._http.get(
            f"/voice/voicemails/{quote(voicemail_id, safe='')}/audio"
        )

    # ------------------------------------------------------------------
    # Conversations + department messages
    # ------------------------------------------------------------------

    def list_conversations(
        self,
        *,
        agent_id: str | None = None,
        status: str | None = None,
        page: int | None = None,
        limit: int | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List voice conversations with optional filters."""
        params: dict[str, Any] = {
            "agent_id": agent_id,
            "status": status,
            "page": page,
            "limit": limit,
        }
        if tenant_id is not None:
            params["tenant_id"] = tenant_id
        body = self._http.get("/voice-agents/conversations", params=params)
        return _list_from(body, primary_key="conversations")

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        """Get a single conversation with its transcript and metadata."""
        return self._http.get(
            f"/voice-agents/conversations/{quote(conversation_id, safe='')}"
        )

    def list_messages(
        self,
        *,
        department: str | None = None,
        page: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List department messages."""
        params: dict[str, Any] = {"page": page, "limit": limit}
        if department is not None:
            params["department"] = department
        body = self._http.get("/voice/messages", params=params)
        return _list_from(body, primary_key="messages")

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_analytics(
        self,
        *,
        agent_id: str | None = None,
        from_: str | None = None,
        to: str | None = None,
    ) -> dict[str, Any]:
        """Get voice analytics (call volume, duration, sentiment, etc.).

        ``from_`` uses a trailing underscore to avoid shadowing Python's
        ``from`` keyword; it is sent on the wire as the ``from`` field.
        """
        return self._http.get(
            "/voice-agents/analytics",
            params={"agent_id": agent_id, "from": from_, "to": to},
        )

    # ------------------------------------------------------------------
    # Campaigns
    # ------------------------------------------------------------------

    def list_campaigns(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List outbound voice campaigns."""
        body = self._http.get(
            "/voice-agents/campaigns", params={"page": page, "limit": limit}
        )
        return _list_from(body, primary_key="campaigns")

    def get_campaign(self, campaign_id: str) -> dict[str, Any]:
        """Get a single campaign by ID."""
        return self._http.get(f"/voice-agents/campaigns/{quote(campaign_id, safe='')}")

    def create_campaign(self, campaign: dict[str, Any]) -> dict[str, Any]:
        """Create a new outbound campaign."""
        return self._http.post("/voice-agents/campaigns", json=campaign)

    def update_campaign(
        self,
        campaign_id: str,
        campaign: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing campaign."""
        return self._http.put(
            f"/voice-agents/campaigns/{quote(campaign_id, safe='')}", json=campaign
        )

    def delete_campaign(self, campaign_id: str) -> None:
        """Delete a campaign."""
        self._http.delete(f"/voice-agents/campaigns/{quote(campaign_id, safe='')}")

    # ------------------------------------------------------------------
    # Phone numbers
    # ------------------------------------------------------------------

    def list_numbers(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List provisioned phone numbers."""
        body = self._http.get(
            "/voice/phone-numbers", params={"page": page, "limit": limit}
        )
        return _list_from(body, primary_key="numbers")

    def get_number(self, number_id: str) -> dict[str, Any]:
        """Get details for a single phone number."""
        return self._http.get(f"/voice/phone-numbers/{quote(number_id, safe='')}")

    def provision_number(self, request: dict[str, Any]) -> dict[str, Any]:
        """Provision a new phone number."""
        return self._http.post("/voice/phone-numbers/provision", json=request)

    def release_number(self, number_id: str) -> None:
        """Release a provisioned phone number."""
        self._http.delete(f"/voice/phone-numbers/{quote(number_id, safe='')}")

    def assign_number(
        self,
        number_id: str,
        agent_id: str,
    ) -> dict[str, Any]:
        """Assign a phone number to a voice agent."""
        return self._http.post(
            f"/voice/phone-numbers/{quote(number_id, safe='')}/assign",
            json={"agent_id": agent_id},
        )

    def search_numbers(
        self,
        *,
        area_code: str | None = None,
        contains: str | None = None,
        country: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search available phone numbers by area code or pattern."""
        body = self._http.get(
            "/voice/phone-numbers/search",
            params={
                "area_code": area_code,
                "contains": contains,
                "country": country,
                "limit": limit,
            },
        )
        return _list_from(body, primary_key="numbers")

    def port_number(self, port_request: dict[str, Any]) -> dict[str, Any]:
        """Initiate a number port-in request."""
        return self._http.post("/voice/phone-numbers/port", json=port_request)

    def get_port_status(self, port_id: str) -> dict[str, Any]:
        """Get the status of a port-in request."""
        return self._http.get(f"/voice/phone-numbers/port/{quote(port_id, safe='')}")

    def cancel_port(self, port_id: str) -> None:
        """Cancel a pending port-in request."""
        self._http.delete(f"/voice/phone-numbers/port/{quote(port_id, safe='')}")

    # ------------------------------------------------------------------
    # Marketplace (voices + packs)
    # ------------------------------------------------------------------

    def list_voices(
        self,
        *,
        language: str | None = None,
        gender: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List available voices in the marketplace."""
        body = self._http.get(
            "/voice/marketplace/voices",
            params={"language": language, "gender": gender, "limit": limit},
        )
        return _list_from(body, primary_key="voices")

    def get_my_voices(self) -> list[dict[str, Any]]:
        """Get voices installed for the current tenant."""
        return _list_from(
            self._http.get("/voice/marketplace/my-voices"), primary_key="voices"
        )

    def list_packs(
        self,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List voice packs (bundles of voices)."""
        body = self._http.get("/voice/marketplace/packs", params={"limit": limit})
        return _list_from(body, primary_key="packs")

    def get_pack(self, pack_id: str) -> dict[str, Any]:
        """Get a single voice pack by ID."""
        return self._http.get(f"/voice/marketplace/packs/{quote(pack_id, safe='')}")

    def install_pack(self, pack_id: str) -> dict[str, Any]:
        """Install a voice pack for the current tenant."""
        return self._http.post(f"/voice/marketplace/packs/{quote(pack_id, safe='')}/install")

    # ------------------------------------------------------------------
    # Calls
    # ------------------------------------------------------------------

    def end_call(self, call_id: str) -> None:
        """End an active call by ID."""
        self._http.post(f"/voice/calls/{quote(call_id, safe='')}/end")

    # ------------------------------------------------------------------
    # Speaker
    # ------------------------------------------------------------------

    def get_speaker_profile(self, speaker_id: str) -> dict[str, Any]:
        """Get the speaker profile for a given speaker ID."""
        return self._http.get(f"/voice/speaker/{quote(speaker_id, safe='')}")

    def enroll_speaker(self, enrollment: dict[str, Any]) -> dict[str, Any]:
        """Enroll a new speaker for voice recognition."""
        return self._http.post("/voice/speaker/enroll", json=enrollment)

    def add_words(self, speaker_id: str, words: list[str]) -> None:
        """Add custom words or phrases to a speaker's vocabulary."""
        self._http.post(
            f"/voice/speaker/{quote(speaker_id, safe='')}/words",
            json={"words": list(words)},
        )

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------

    def list_profiles(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List voice profiles for the tenant."""
        body = self._http.get(
            "/voice/profiles", params={"page": page, "limit": limit}
        )
        return _list_from(body, primary_key="profiles")

    def get_profile(self, profile_id: str) -> dict[str, Any]:
        """Get a single voice profile by ID."""
        return self._http.get(f"/voice/profiles/{quote(profile_id, safe='')}")

    def create_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Create a new voice profile."""
        return self._http.post("/voice/profiles", json=profile)

    def update_profile(
        self,
        profile_id: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing voice profile."""
        return self._http.put(
            f"/voice/profiles/{quote(profile_id, safe='')}", json=profile
        )

    # ------------------------------------------------------------------
    # Edge voice pipeline (CF Container — STT → Ether → TTS)
    # ------------------------------------------------------------------

    def process_audio(
        self,
        audio_bytes: bytes,
        *,
        language: str | None = None,
        agent_id: str | None = None,
        voice_id: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Process recorded audio through the full edge voice pipeline.

        Sends audio to the CF Container voice pipeline which runs STT
        (Workers AI Whisper, FREE) → Ether classification → AI response →
        TTS. Returns ``{transcript, response, audio_url, pipeline_ms}``.
        """
        payload: dict[str, Any] = {
            "audio": base64.b64encode(bytes(audio_bytes)).decode("ascii"),
        }
        if language is not None:
            payload["language"] = language
        if agent_id is not None:
            payload["agent_id"] = agent_id
        if voice_id is not None:
            payload["voice_id"] = voice_id
        if session_id is not None:
            payload["session_id"] = session_id
        return self._http.post("/voice/process", json=payload)

    def get_voice_websocket_url(self, *, session_id: str | None = None) -> str:
        """Build the WebSocket URL for streaming voice interaction.

        The endpoint at ``/ws/voice`` accepts:

        - ``{"type": "audio", "data": "<base64>"}`` — audio chunks
        - ``{"type": "barge_in"}`` — interrupt current response
        - ``{"type": "ping"}`` — keepalive

        And responds with:

        - ``{"type": "transcript", "text": "..."}`` — interim STT results
        - ``{"type": "response", "text": "...", "audio_url": "..."}``
        - ``{"type": "pong"}``

        Returns the full WebSocket URL based on the configured API base.
        """
        base = self._http._config.resolved_base_url  # noqa: SLF001 — intentional: WS URL shares base
        ws_base = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
        if session_id is not None:
            return f"{ws_base}/ws/voice?session_id={quote(session_id, safe='')}"
        return f"{ws_base}/ws/voice"

    def pipeline_health(self) -> dict[str, Any]:
        """Check edge voice pipeline health."""
        return self._http.get("/voice/pipeline/health")

    # ------------------------------------------------------------------
    # Caller profiles (Issue #2868) — dart uses /caller-profiles/*
    # ------------------------------------------------------------------

    def get_caller_profile(self, phone_number: str) -> dict[str, Any]:
        """Look up a caller profile by phone number for personalized voice AI.

        Returns preferences, order history, loyalty tier, and past
        interactions.
        """
        return self._http.get(f"/caller-profiles/{quote(phone_number, safe='')}")

    def list_caller_profiles(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List caller profiles for the current tenant (paginated)."""
        return self._http.get(
            "/caller-profiles",
            params={"limit": limit, "offset": offset},
        )

    def upsert_caller_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Create or update a caller profile."""
        return self._http.post("/caller-profiles", json=profile)

    def delete_caller_profile(self, profile_id: str) -> None:
        """Delete a caller profile."""
        self._http.delete(f"/caller-profiles/{quote(profile_id, safe='')}")

    def record_caller_order(
        self,
        phone_number: str,
        order_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Record an order for a caller (updates stats + loyalty points)."""
        return self._http.post(
            f"/caller-profiles/{quote(phone_number, safe='')}/orders",
            json=order_data,
        )

    # ------------------------------------------------------------------
    # Escalation + business hours (per-agent)
    # ------------------------------------------------------------------

    def get_escalation_config(self, agent_id: str) -> dict[str, Any]:
        """Get voice-agent escalation config (transfer targets, sentiment threshold)."""
        return self._http.get(
            f"/voice-agents/{quote(agent_id, safe='')}/escalation-config"
        )

    def update_escalation_config(
        self,
        agent_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Update voice-agent escalation config."""
        return self._http.put(
            f"/voice-agents/{quote(agent_id, safe='')}/escalation-config",
            json=config,
        )

    def get_business_hours(self, agent_id: str) -> dict[str, Any]:
        """Get voice-agent business hours."""
        return self._http.get(
            f"/voice-agents/{quote(agent_id, safe='')}/business-hours"
        )

    def update_business_hours(
        self,
        agent_id: str,
        hours: dict[str, Any],
    ) -> dict[str, Any]:
        """Update voice-agent business hours."""
        return self._http.put(
            f"/voice-agents/{quote(agent_id, safe='')}/business-hours",
            json=hours,
        )

    # ------------------------------------------------------------------
    # Agent testing (Issue #170)
    # ------------------------------------------------------------------

    def test_agent(
        self,
        *,
        tenant_id: str,
        scenario_count: int = 5,
    ) -> dict[str, Any]:
        """Trigger an AI-to-AI test suite against a voice agent.

        The platform generates realistic caller scenarios, executes them
        against the agent, and returns a scorecard with transcripts and
        accuracy ratings.
        """
        return self._http.post(
            "/voice-agents/test",
            json={"tenant_id": tenant_id, "scenario_count": scenario_count},
        )

    # ------------------------------------------------------------------
    # Marketplace voice reviews (#3463)
    # ------------------------------------------------------------------

    def list_voice_reviews(
        self,
        voice_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List published reviews for a marketplace voice.

        Returns ``{reviews, total, average, limit, offset}``. Each review
        carries a 16-char HMAC-hashed ``author_tenant_id`` so the consumer
        can de-duplicate authors without learning underlying tenants.
        """
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._http.get(
            f"/voice/marketplace/voices/{quote(voice_id, safe='')}/reviews",
            params=params or None,
        )

    def submit_voice_review(
        self,
        voice_id: str,
        rating: int,
        *,
        text: str = "",
    ) -> dict[str, Any]:
        """Submit a 1..5 star review for a marketplace voice.

        One review per ``(user, voice)`` — duplicate submissions return 409.
        """
        return self._http.post(
            f"/voice/marketplace/voices/{quote(voice_id, safe='')}/reviews",
            json={"rating": rating, "text": text},
        )

    def delete_voice_review(self, review_id: str) -> None:
        """Soft-delete the caller's own review."""
        self._http.delete(
            f"/voice/marketplace/voices/reviews/{quote(review_id, safe='')}"
        )
