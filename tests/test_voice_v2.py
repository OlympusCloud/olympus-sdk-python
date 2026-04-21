"""Tests for V2-005 voice cascade resolver + /leads lead capture."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from olympus_sdk.http import OlympusHttpClient

# NB: As of Wave 2 (olympus-cloud-gcp#3216), VoiceService is synchronous —
# the ``async def`` signatures were removed to match the rest of the SDK.
# ``ConnectService.create_lead`` remains async and is exercised via
# ``asyncio.get_event_loop().run_until_complete``.
from olympus_sdk.models.voice_v2 import (
    VoiceEffectiveConfig,
    VoicePipeline,
)
from olympus_sdk.services.connect import UTM, ConnectService
from olympus_sdk.services.voice import VoiceService

# Canonical dev-gateway response captured 2026-04-18T01:31 UTC against
# dev.api.olympuscloud.ai, agent 41f239da-c492-5fe6-9334-7bbc47804a36.
EFFECTIVE_CONFIG_FIXTURE = {
    "agentId": "41f239da-c492-5fe6-9334-7bbc47804a36",
    "tenantId": "550e8400-e29b-41d4-a716-446655449100",
    "pipeline": "olympus_native",
    "pipelineConfig": {
        "defaultLogLevel": "INFO",
        "tenantSeededAt": "2026-04-17-V2-005-fix-verification",
    },
    "tierOverride": "T3",
    "logLevel": "INFO",
    "debugTranscriptsEnabled": False,
    "v2ShadowEnabled": False,
    "v2PrimaryEnabled": False,
    "telephonyProvider": "telnyx",
    "providerAccountRef": "telnyx-dev-acct-v2-005-test",
    "preferredCodec": "opus",
    "preferredSampleRate": 48000,
    "hdAudioEnabled": True,
    "webhookPathOverride": "/v2/voice/inbound",
    "v2Routed": True,
    "voiceDefaults": {
        "platform": None,
        "app": None,
        "tenant": {
            "pipelineConfig": {
                "defaultLogLevel": "INFO",
                "tenantSeededAt": "2026-04-17-V2-005-fix-verification",
            },
            "tierOverride": "T3",
        },
        "agent": {
            "pipeline": "olympus_native",
            "pipelineConfig": {},
            "tierOverride": None,
            "logLevel": "INFO",
            "debugTranscriptsEnabled": False,
            "v2ShadowEnabled": False,
            "v2PrimaryEnabled": False,
        },
    },
    "resolvedAt": "2026-04-18T01:31:52.064682+00:00",
    "cascadeVersion": "v2.1-rename",
}

PIPELINE_FIXTURE = {
    "agentId": "41f239da-c492-5fe6-9334-7bbc47804a36",
    "pipeline": "olympus_native",
    "pipelineConfig": {
        "defaultLogLevel": "INFO",
        "tenantSeededAt": "2026-04-17-V2-005-fix-verification",
    },
    "resolvedAt": "2026-04-18T01:32:52.722382+00:00",
    "cascadeVersion": "v2.1-rename",
}


def _mock_http() -> MagicMock:
    return MagicMock(spec=OlympusHttpClient)


class TestVoiceEffectiveConfigModel:
    def test_from_dict_parses_canonical_response(self) -> None:
        cfg = VoiceEffectiveConfig.from_dict(EFFECTIVE_CONFIG_FIXTURE)
        assert cfg.agent_id == "41f239da-c492-5fe6-9334-7bbc47804a36"
        assert cfg.tenant_id == "550e8400-e29b-41d4-a716-446655449100"
        assert cfg.pipeline == "olympus_native"
        assert cfg.tier_override == "T3"
        assert cfg.log_level == "INFO"
        assert cfg.telephony_provider == "telnyx"
        assert cfg.preferred_sample_rate == 48000
        assert cfg.hd_audio_enabled is True
        assert cfg.v2_routed is True
        assert cfg.cascade_version == "v2.1-rename"

    def test_cascade_rungs(self) -> None:
        cfg = VoiceEffectiveConfig.from_dict(EFFECTIVE_CONFIG_FIXTURE)
        assert cfg.voice_defaults.platform is None
        assert cfg.voice_defaults.app is None
        assert cfg.voice_defaults.tenant is not None
        assert cfg.voice_defaults.tenant.tier_override == "T3"
        assert cfg.voice_defaults.agent is not None
        assert cfg.voice_defaults.agent.pipeline == "olympus_native"
        assert cfg.voice_defaults.agent.debug_transcripts_enabled is False

    def test_tolerates_missing_optional_telephony_fields(self) -> None:
        minimal = {
            "agentId": "a",
            "tenantId": "t",
            "pipeline": "olympus_native",
            "pipelineConfig": {},
            "logLevel": "INFO",
            "debugTranscriptsEnabled": False,
            "v2ShadowEnabled": False,
            "v2PrimaryEnabled": False,
            "voiceDefaults": {},
            "resolvedAt": "2026-04-18T00:00:00Z",
            "cascadeVersion": "v2.1-rename",
        }
        cfg = VoiceEffectiveConfig.from_dict(minimal)
        assert cfg.telephony_provider is None
        assert cfg.preferred_codec is None
        assert cfg.voice_defaults.platform is None


class TestVoicePipelineModel:
    def test_from_dict_parses_canonical_response(self) -> None:
        p = VoicePipeline.from_dict(PIPELINE_FIXTURE)
        assert p.agent_id == "41f239da-c492-5fe6-9334-7bbc47804a36"
        assert p.pipeline == "olympus_native"
        assert p.cascade_version == "v2.1-rename"


class TestVoiceServiceV2:
    def test_get_effective_config(self) -> None:
        http = _mock_http()
        http.get.return_value = EFFECTIVE_CONFIG_FIXTURE
        svc = VoiceService(http)
        cfg = svc.get_effective_config("abc123")
        http.get.assert_called_once_with(
            "/voice-agents/configs/abc123/effective-config"
        )
        assert cfg.agent_id == "41f239da-c492-5fe6-9334-7bbc47804a36"
        assert cfg.pipeline == "olympus_native"

    def test_get_pipeline(self) -> None:
        http = _mock_http()
        http.get.return_value = PIPELINE_FIXTURE
        svc = VoiceService(http)
        p = svc.get_pipeline("abc123")
        http.get.assert_called_once_with("/voice-agents/configs/abc123/pipeline")
        assert p.pipeline == "olympus_native"


class TestConnectService:
    def test_create_lead_full_payload(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "lead_id": "lead-xyz",
            "status": "created",
            "created_at": "2026-04-18T03:00:00Z",
        }
        svc = ConnectService(http)
        res = asyncio.get_event_loop().run_until_complete(
            svc.create_lead(
                email="scott@example.com",
                name="Scott",
                company="Olympus",
                source="marketing-landing",
                utm=UTM(source="twitter", campaign="spring-launch"),
            )
        )
        assert res.lead_id == "lead-xyz"
        assert res.status == "created"

        # Verify the request shape
        call_args = http.post.call_args
        assert call_args.args[0] == "/leads"
        body = call_args.kwargs["json"]
        assert body["email"] == "scott@example.com"
        assert body["name"] == "Scott"
        assert body["utm"] == {"source": "twitter", "campaign": "spring-launch"}

    def test_create_lead_requires_email(self) -> None:
        http = _mock_http()
        svc = ConnectService(http)
        try:
            asyncio.get_event_loop().run_until_complete(svc.create_lead(email=""))
        except ValueError as e:
            assert "email" in str(e)
            return
        raise AssertionError("expected ValueError for empty email")
