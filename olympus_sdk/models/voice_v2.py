"""Voice Agent V2 cascade-resolver models (V2-005).

Source of truth: ``backend/python/app/api/voice_agent_routes.py`` cascade
resolver (``/voice-agents/configs/{id}/effective-config`` and
``/voice-agents/configs/{id}/pipeline``). Response shapes are the canonical
merged view of platform → app → tenant → agent voice defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VoiceDefaultsRung:
    """A single rung of the voice-defaults cascade."""

    pipeline: str | None = None
    pipeline_config: dict[str, Any] = field(default_factory=dict)
    tier_override: str | None = None
    log_level: str | None = None
    debug_transcripts_enabled: bool | None = None
    v2_shadow_enabled: bool | None = None
    v2_primary_enabled: bool | None = None

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> VoiceDefaultsRung | None:
        if not data:
            return None
        return VoiceDefaultsRung(
            pipeline=data.get("pipeline"),
            pipeline_config=data.get("pipelineConfig") or {},
            tier_override=data.get("tierOverride"),
            log_level=data.get("logLevel"),
            debug_transcripts_enabled=data.get("debugTranscriptsEnabled"),
            v2_shadow_enabled=data.get("v2ShadowEnabled"),
            v2_primary_enabled=data.get("v2PrimaryEnabled"),
        )


@dataclass
class VoiceDefaultsCascade:
    """The four rungs of the voice-defaults cascade."""

    platform: VoiceDefaultsRung | None = None
    app: VoiceDefaultsRung | None = None
    tenant: VoiceDefaultsRung | None = None
    agent: VoiceDefaultsRung | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> VoiceDefaultsCascade:
        return VoiceDefaultsCascade(
            platform=VoiceDefaultsRung.from_dict(data.get("platform")),
            app=VoiceDefaultsRung.from_dict(data.get("app")),
            tenant=VoiceDefaultsRung.from_dict(data.get("tenant")),
            agent=VoiceDefaultsRung.from_dict(data.get("agent")),
        )


@dataclass
class VoiceEffectiveConfig:
    """Full merged view returned by ``GET /voice-agents/configs/{id}/effective-config``."""

    agent_id: str
    tenant_id: str
    pipeline: str
    pipeline_config: dict[str, Any]
    log_level: str
    debug_transcripts_enabled: bool
    v2_shadow_enabled: bool
    v2_primary_enabled: bool
    voice_defaults: VoiceDefaultsCascade
    resolved_at: str
    cascade_version: str
    tier_override: str | None = None
    telephony_provider: str | None = None
    provider_account_ref: str | None = None
    preferred_codec: str | None = None
    preferred_sample_rate: int | None = None
    hd_audio_enabled: bool | None = None
    webhook_path_override: str | None = None
    v2_routed: bool | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> VoiceEffectiveConfig:
        return VoiceEffectiveConfig(
            agent_id=data["agentId"],
            tenant_id=data["tenantId"],
            pipeline=data["pipeline"],
            pipeline_config=data.get("pipelineConfig") or {},
            tier_override=data.get("tierOverride"),
            log_level=data["logLevel"],
            debug_transcripts_enabled=data["debugTranscriptsEnabled"],
            v2_shadow_enabled=data["v2ShadowEnabled"],
            v2_primary_enabled=data["v2PrimaryEnabled"],
            telephony_provider=data.get("telephonyProvider"),
            provider_account_ref=data.get("providerAccountRef"),
            preferred_codec=data.get("preferredCodec"),
            preferred_sample_rate=data.get("preferredSampleRate"),
            hd_audio_enabled=data.get("hdAudioEnabled"),
            webhook_path_override=data.get("webhookPathOverride"),
            v2_routed=data.get("v2Routed"),
            voice_defaults=VoiceDefaultsCascade.from_dict(data.get("voiceDefaults") or {}),
            resolved_at=data["resolvedAt"],
            cascade_version=data["cascadeVersion"],
        )


@dataclass
class VoicePipeline:
    """Pipeline-only view returned by ``GET /voice-agents/configs/{id}/pipeline``."""

    agent_id: str
    pipeline: str
    pipeline_config: dict[str, Any]
    resolved_at: str
    cascade_version: str

    @staticmethod
    def from_dict(data: dict[str, Any]) -> VoicePipeline:
        return VoicePipeline(
            agent_id=data["agentId"],
            pipeline=data["pipeline"],
            pipeline_config=data.get("pipelineConfig") or {},
            resolved_at=data["resolvedAt"],
            cascade_version=data["cascadeVersion"],
        )
