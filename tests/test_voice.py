"""Tests for the rewritten VoiceService (Wave 2 — olympus-cloud-gcp#3216).

Wave 2 rewrote ``olympus_sdk/services/voice.py`` wholesale against
``/tmp/wt-sdk-dart/lib/src/services/voice_service.dart`` to bring the
Python SDK to dart parity. The pre-Wave-2 file declared ``async def``
signatures while calling sync HTTP internals — those methods were
non-functional, so dropping the async surface is a behavioural fix, not a
regression.
"""

from __future__ import annotations

import base64
from unittest.mock import MagicMock

import pytest

from olympus_sdk import OlympusApiError, OlympusClient, OlympusConfig
from olympus_sdk.http import OlympusHttpClient
from olympus_sdk.services.voice import VoiceService


def _mock_http() -> MagicMock:
    return MagicMock(spec=OlympusHttpClient)


# ---------------------------------------------------------------------------
# Agents (configs)
# ---------------------------------------------------------------------------


class TestVoiceAgentConfigs:
    def test_list_configs_unwraps_envelope_and_forwards_filters(self) -> None:
        http = _mock_http()
        http.get.return_value = {"configs": [{"id": "a1"}, {"id": "a2"}]}
        svc = VoiceService(http)
        rows = svc.list_configs(page=2, limit=50, tenant_id="ten-1")
        assert [r["id"] for r in rows] == ["a1", "a2"]
        assert http.get.call_args[0][0] == "/voice-agents/configs"
        params = http.get.call_args.kwargs["params"]
        assert params == {"page": 2, "limit": 50, "tenant_id": "ten-1"}

    def test_list_configs_falls_back_to_data_envelope(self) -> None:
        http = _mock_http()
        http.get.return_value = {"data": [{"id": "a3"}]}
        svc = VoiceService(http)
        assert svc.list_configs() == [{"id": "a3"}]

    def test_get_config_escapes_id(self) -> None:
        http = _mock_http()
        http.get.return_value = {"id": "a/b"}
        svc = VoiceService(http)
        svc.get_config("a/b")
        assert http.get.call_args[0][0] == "/voice-agents/configs/a%2Fb"

    def test_update_config_puts_body(self) -> None:
        http = _mock_http()
        http.put.return_value = {"id": "a1", "name": "Updated"}
        svc = VoiceService(http)
        svc.update_config("a1", {"name": "Updated"})
        assert http.put.call_args[0][0] == "/voice-agents/configs/a1"
        assert http.put.call_args.kwargs["json"] == {"name": "Updated"}

    def test_delete_config_hits_delete_endpoint(self) -> None:
        http = _mock_http()
        svc = VoiceService(http)
        svc.delete_config("a1")
        http.delete.assert_called_once_with("/voice-agents/configs/a1")


# ---------------------------------------------------------------------------
# V2-005 cascade resolver
# ---------------------------------------------------------------------------


class TestVoiceCascadeResolver:
    # Cascade resolver emits camelCase per the Python backend's route handler —
    # see ``olympus_sdk/models/voice_v2.py::from_dict`` expectations.
    _EFFECTIVE_FIXTURE = {
        "agentId": "a1",
        "tenantId": "t1",
        "pipeline": "gemini-realtime",
        "pipelineConfig": {"tier": "T3"},
        "logLevel": "info",
        "debugTranscriptsEnabled": False,
        "v2ShadowEnabled": True,
        "v2PrimaryEnabled": False,
        "voiceDefaults": {
            "platform": {"pipeline": "baseline"},
            "app": None,
            "tenant": None,
            "agent": None,
        },
        "resolvedAt": "2026-04-18T00:00:00Z",
        "cascadeVersion": "v2",
    }

    def test_get_effective_config_returns_typed_object(self) -> None:
        http = _mock_http()
        http.get.return_value = self._EFFECTIVE_FIXTURE
        svc = VoiceService(http)
        cfg = svc.get_effective_config("a1")
        assert cfg.agent_id == "a1"
        assert cfg.pipeline == "gemini-realtime"
        assert cfg.v2_shadow_enabled is True
        assert (
            http.get.call_args[0][0]
            == "/voice-agents/configs/a1/effective-config"
        )

    def test_get_pipeline_returns_typed_pipeline(self) -> None:
        http = _mock_http()
        http.get.return_value = {
            "agentId": "a1",
            "pipeline": "gemini-realtime",
            "pipelineConfig": {"tier": "T3"},
            "resolvedAt": "2026-04-18T00:00:00Z",
            "cascadeVersion": "v2",
        }
        svc = VoiceService(http)
        pipeline = svc.get_pipeline("a1")
        assert pipeline.pipeline == "gemini-realtime"
        assert http.get.call_args[0][0] == "/voice-agents/configs/a1/pipeline"


# ---------------------------------------------------------------------------
# Pool + schedule + provisioning
# ---------------------------------------------------------------------------


class TestVoicePoolScheduleProvisioning:
    def test_get_pool_returns_list_from_pool_or_entries_or_data(self) -> None:
        http = _mock_http()
        http.get.return_value = {"entries": [{"id": "p1"}]}
        svc = VoiceService(http)
        assert svc.get_pool("a1") == [{"id": "p1"}]
        assert http.get.call_args[0][0] == "/voice-agents/a1/pool"

    def test_add_to_pool_posts(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "p1"}
        svc = VoiceService(http)
        svc.add_to_pool("a1", {"persona": "warm-server"})
        assert http.post.call_args[0][0] == "/voice-agents/a1/pool"

    def test_remove_from_pool_hits_delete(self) -> None:
        http = _mock_http()
        svc = VoiceService(http)
        svc.remove_from_pool("a1", "p1")
        http.delete.assert_called_once_with("/voice-agents/a1/pool/p1")

    def test_get_schedule_fetches(self) -> None:
        http = _mock_http()
        http.get.return_value = {"mon": "9-17"}
        svc = VoiceService(http)
        svc.get_schedule("a1")
        assert http.get.call_args[0][0] == "/voice-agents/a1/schedule"

    def test_update_schedule_puts_body(self) -> None:
        http = _mock_http()
        http.put.return_value = {"ok": True}
        svc = VoiceService(http)
        svc.update_schedule("a1", {"mon": "9-17"})
        assert http.put.call_args[0][0] == "/voice-agents/a1/schedule"
        assert http.put.call_args.kwargs["json"] == {"mon": "9-17"}

    def test_provision_agent_posts_full_body(self) -> None:
        http = _mock_http()
        http.post.return_value = {"job_id": "j1"}
        svc = VoiceService(http)
        svc.provision_agent(
            agent_id="a1",
            tenant_id="t1",
            voice_name="aria",
            profile={"tone": "warm"},
            greeting_text="Hello!",
        )
        assert (
            http.post.call_args[0][0]
            == "/ether/voice/agents/a1/provision-wizard"
        )
        body = http.post.call_args.kwargs["json"]
        assert body["voice_name"] == "aria"
        assert body["greeting_text"] == "Hello!"

    def test_get_provisioning_status_passes_job_id_param(self) -> None:
        http = _mock_http()
        http.get.return_value = {"status": "running"}
        svc = VoiceService(http)
        svc.get_provisioning_status("a1", "j1")
        assert (
            http.get.call_args[0][0]
            == "/ether/voice/agents/a1/provisioning-status"
        )
        assert http.get.call_args.kwargs["params"] == {"job_id": "j1"}


# ---------------------------------------------------------------------------
# Self-service agent CRUD
# ---------------------------------------------------------------------------


class TestVoiceAgentCrud:
    def test_create_agent_omits_unset_fields(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "a1", "name": "Test"}
        svc = VoiceService(http)
        svc.create_agent(name="Test", voice_id="v1")
        body = http.post.call_args.kwargs["json"]
        assert body == {"name": "Test", "voice_id": "v1"}
        assert http.post.call_args[0][0] == "/voice-agents/configs"

    def test_update_agent_sends_only_provided_fields(self) -> None:
        http = _mock_http()
        http.put.return_value = {"id": "a1"}
        svc = VoiceService(http)
        svc.update_agent("a1", name="New Name", is_active=False)
        body = http.put.call_args.kwargs["json"]
        assert body == {"name": "New Name", "is_active": False}

    def test_clone_agent_posts_body(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "a2"}
        svc = VoiceService(http)
        svc.clone_agent("a1", new_name="Clone", phone_number="+15550000000")
        assert http.post.call_args[0][0] == "/voice-agents/configs/a1/clone"
        body = http.post.call_args.kwargs["json"]
        assert body["new_name"] == "Clone"

    def test_preview_agent_voice_posts_sample(self) -> None:
        http = _mock_http()
        http.post.return_value = {"audio_url": "https://cdn/preview.mp3"}
        svc = VoiceService(http)
        svc.preview_agent_voice("a1", sample_text="Hello world")
        assert http.post.call_args[0][0] == "/voice-agents/configs/a1/preview"
        assert http.post.call_args.kwargs["json"]["sample_text"] == "Hello world"

    def test_list_gemini_voices_passes_language(self) -> None:
        http = _mock_http()
        http.get.return_value = {"voices": [{"id": "v1"}]}
        svc = VoiceService(http)
        svc.list_gemini_voices(language="en-US")
        assert http.get.call_args[0][0] == "/voice/voices"
        assert http.get.call_args.kwargs["params"] == {"language": "en-US"}

    def test_list_agents_is_alias_for_list_configs(self) -> None:
        http = _mock_http()
        http.get.return_value = {"configs": [{"id": "a1"}]}
        svc = VoiceService(http)
        svc.list_agents(page=1, limit=10)
        assert http.get.call_args[0][0] == "/voice-agents/configs"


# ---------------------------------------------------------------------------
# Personas + templates
# ---------------------------------------------------------------------------


class TestVoicePersonasAndTemplates:
    def test_list_personas_serializes_bool_as_string(self) -> None:
        http = _mock_http()
        http.get.return_value = {"personas": []}
        svc = VoiceService(http)
        svc.list_personas(category="hospitality", premium_only=True)
        params = http.get.call_args.kwargs["params"]
        assert params["category"] == "hospitality"
        # dart sends booleans as strings on the wire
        assert params["premium_only"] == "true"

    def test_apply_persona_to_agent_posts_persona_slug(self) -> None:
        http = _mock_http()
        http.post.return_value = {"applied": True}
        svc = VoiceService(http)
        svc.apply_persona_to_agent("a1", "warm-server")
        assert (
            http.post.call_args[0][0]
            == "/voice-agents/configs/a1/apply-persona"
        )
        assert http.post.call_args.kwargs["json"] == {"persona": "warm-server"}

    def test_instantiate_agent_template_posts_name(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "a1"}
        svc = VoiceService(http)
        svc.instantiate_agent_template("tmpl-1", name="My Agent")
        assert (
            http.post.call_args[0][0]
            == "/voice-agents/templates/tmpl-1/instantiate"
        )
        assert http.post.call_args.kwargs["json"]["name"] == "My Agent"


# ---------------------------------------------------------------------------
# Ambiance + voice overrides
# ---------------------------------------------------------------------------


class TestVoiceAmbiance:
    def test_upload_ambiance_bed_base64_encodes_audio(self) -> None:
        http = _mock_http()
        http.post.return_value = {"bed_id": "bed-1"}
        svc = VoiceService(http)
        audio = b"fake-audio-payload"
        svc.upload_ambiance_bed(audio, name="Jazz Bar", time_of_day="evening")
        body = http.post.call_args.kwargs["json"]
        assert body["audio_base64"] == base64.b64encode(audio).decode("ascii")
        assert body["name"] == "Jazz Bar"
        assert body["time_of_day"] == "evening"

    def test_update_agent_ambiance_patches_only_set_fields(self) -> None:
        http = _mock_http()
        http.patch.return_value = {"ok": True}
        svc = VoiceService(http)
        svc.update_agent_ambiance("a1", enabled=True, intensity=0.4)
        body = http.patch.call_args.kwargs["json"]
        assert body == {"enabled": True, "intensity": 0.4}

    def test_update_agent_voice_overrides_patches(self) -> None:
        http = _mock_http()
        http.patch.return_value = {"ok": True}
        svc = VoiceService(http)
        svc.update_agent_voice_overrides("a1", pitch=0.1, speed=1.0)
        assert (
            http.patch.call_args[0][0]
            == "/voice-agents/configs/a1/voice-overrides"
        )


# ---------------------------------------------------------------------------
# Workflow templates
# ---------------------------------------------------------------------------


class TestVoiceWorkflowTemplates:
    def test_list_workflow_templates_paginates(self) -> None:
        http = _mock_http()
        http.get.return_value = {"templates": [{"id": "w1"}]}
        svc = VoiceService(http)
        svc.list_workflow_templates(page=1, limit=25)
        assert http.get.call_args[0][0] == "/voice/workflow-templates"
        assert http.get.call_args.kwargs["params"] == {"page": 1, "limit": 25}

    def test_create_workflow_instance_posts_params(self) -> None:
        http = _mock_http()
        http.post.return_value = {"instance_id": "i1"}
        svc = VoiceService(http)
        svc.create_workflow_instance("w1", {"foo": "bar"})
        assert (
            http.post.call_args[0][0]
            == "/voice/workflow-templates/w1/instances"
        )


# ---------------------------------------------------------------------------
# Voicemails
# ---------------------------------------------------------------------------


class TestVoiceVoicemails:
    def test_list_voicemails_filters(self) -> None:
        http = _mock_http()
        http.get.return_value = {"voicemails": []}
        svc = VoiceService(http)
        svc.list_voicemails(caller_phone="+15550000000", limit=20)
        params = http.get.call_args.kwargs["params"]
        assert params["caller_phone"] == "+15550000000"
        assert params["limit"] == 20

    def test_update_voicemail_patches(self) -> None:
        http = _mock_http()
        http.patch.return_value = {"id": "v1"}
        svc = VoiceService(http)
        svc.update_voicemail("v1", {"status": "resolved"})
        assert http.patch.call_args[0][0] == "/voice/voicemails/v1"

    def test_get_voicemail_audio_url_fetches(self) -> None:
        http = _mock_http()
        http.get.return_value = {"audio_url": "https://..."}
        svc = VoiceService(http)
        svc.get_voicemail_audio_url("v1")
        assert http.get.call_args[0][0] == "/voice/voicemails/v1/audio"


# ---------------------------------------------------------------------------
# Conversations + analytics + campaigns
# ---------------------------------------------------------------------------


class TestVoiceConversationsAnalyticsCampaigns:
    def test_list_conversations_passes_filters(self) -> None:
        http = _mock_http()
        http.get.return_value = {"conversations": [{"id": "c1"}]}
        svc = VoiceService(http)
        svc.list_conversations(agent_id="a1", status="completed", limit=10)
        params = http.get.call_args.kwargs["params"]
        assert params["agent_id"] == "a1"
        assert params["status"] == "completed"
        assert params["limit"] == 10

    def test_get_analytics_renames_from_on_the_wire(self) -> None:
        http = _mock_http()
        http.get.return_value = {"calls": 10}
        svc = VoiceService(http)
        svc.get_analytics(
            agent_id="a1",
            from_="2026-04-01",
            to="2026-04-30",
        )
        params = http.get.call_args.kwargs["params"]
        # 'from_' kwarg must serialize as 'from' on the wire
        assert params["from"] == "2026-04-01"
        assert "from_" not in params
        assert params["to"] == "2026-04-30"

    def test_create_campaign_posts(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "cmp-1"}
        svc = VoiceService(http)
        svc.create_campaign({"name": "Spring"})
        assert http.post.call_args[0][0] == "/voice-agents/campaigns"

    def test_delete_campaign_deletes(self) -> None:
        http = _mock_http()
        svc = VoiceService(http)
        svc.delete_campaign("cmp-1")
        http.delete.assert_called_once_with("/voice-agents/campaigns/cmp-1")


# ---------------------------------------------------------------------------
# Phone numbers + marketplace
# ---------------------------------------------------------------------------


class TestVoiceNumbersAndMarketplace:
    def test_search_numbers_passes_all_filters(self) -> None:
        http = _mock_http()
        http.get.return_value = {"numbers": [{"e164": "+15550000000"}]}
        svc = VoiceService(http)
        svc.search_numbers(area_code="555", country="US", limit=5)
        params = http.get.call_args.kwargs["params"]
        assert params["area_code"] == "555"
        assert params["country"] == "US"
        assert params["limit"] == 5

    def test_assign_number_posts_agent_id(self) -> None:
        http = _mock_http()
        http.post.return_value = {"assigned": True}
        svc = VoiceService(http)
        svc.assign_number("n1", "a1")
        assert http.post.call_args[0][0] == "/voice/phone-numbers/n1/assign"
        assert http.post.call_args.kwargs["json"] == {"agent_id": "a1"}

    def test_install_pack_posts_no_body(self) -> None:
        http = _mock_http()
        http.post.return_value = {"installed": True}
        svc = VoiceService(http)
        svc.install_pack("pack-1")
        assert (
            http.post.call_args[0][0]
            == "/voice/marketplace/packs/pack-1/install"
        )


# ---------------------------------------------------------------------------
# Edge pipeline
# ---------------------------------------------------------------------------


class TestVoiceEdgePipeline:
    def test_process_audio_base64_encodes(self) -> None:
        http = _mock_http()
        http.post.return_value = {"transcript": "hi", "pipeline_ms": 123}
        svc = VoiceService(http)
        audio = b"\x00\x01\x02fake-audio"
        svc.process_audio(audio, language="en-US", session_id="sess-1")
        assert http.post.call_args[0][0] == "/voice/process"
        body = http.post.call_args.kwargs["json"]
        assert body["audio"] == base64.b64encode(audio).decode("ascii")
        assert body["language"] == "en-US"
        assert body["session_id"] == "sess-1"

    def test_pipeline_health_fetches(self) -> None:
        http = _mock_http()
        http.get.return_value = {"status": "healthy"}
        svc = VoiceService(http)
        svc.pipeline_health()
        assert http.get.call_args[0][0] == "/voice/pipeline/health"

    def test_get_voice_websocket_url_swaps_https_for_wss(self) -> None:
        client = OlympusClient(
            app_id="com.test",
            api_key="oc_test",
            config=OlympusConfig(
                app_id="com.test",
                api_key="oc_test",
                base_url="https://api.test.olympuscloud.ai/api/v1",
            ),
        )
        url = client.voice.get_voice_websocket_url(session_id="sess-42")
        assert url.startswith("wss://")
        assert "/ws/voice?session_id=sess-42" in url
        assert "https://" not in url

    def test_get_voice_websocket_url_without_session(self) -> None:
        client = OlympusClient(
            app_id="com.test",
            api_key="oc_test",
            config=OlympusConfig(
                app_id="com.test",
                api_key="oc_test",
                base_url="https://api.test.olympuscloud.ai/api/v1",
            ),
        )
        url = client.voice.get_voice_websocket_url()
        assert url.endswith("/ws/voice")


# ---------------------------------------------------------------------------
# Caller profiles + escalation + business hours
# ---------------------------------------------------------------------------


class TestVoiceCallerAndEscalation:
    def test_get_caller_profile_uses_caller_profiles_route(self) -> None:
        http = _mock_http()
        http.get.return_value = {"phone": "+15550000000", "loyalty_tier": "gold"}
        svc = VoiceService(http)
        svc.get_caller_profile("+15550000000")
        # Dart is canonical here: /caller-profiles/{phone}, not /voice/callers/{id}
        path = http.get.call_args[0][0]
        assert path.startswith("/caller-profiles/")
        assert "+" not in path.split("/caller-profiles/")[1]

    def test_list_caller_profiles_default_pagination(self) -> None:
        http = _mock_http()
        http.get.return_value = {"data": [], "total": 0}
        svc = VoiceService(http)
        svc.list_caller_profiles()
        assert http.get.call_args[0][0] == "/caller-profiles"
        params = http.get.call_args.kwargs["params"]
        assert params == {"limit": 50, "offset": 0}

    def test_record_caller_order_posts_order_data(self) -> None:
        http = _mock_http()
        http.post.return_value = {"ok": True}
        svc = VoiceService(http)
        svc.record_caller_order("+15550000000", {"order_id": "o1"})
        path = http.post.call_args[0][0]
        assert path.startswith("/caller-profiles/")
        assert path.endswith("/orders")
        assert http.post.call_args.kwargs["json"] == {"order_id": "o1"}

    def test_get_escalation_config_fetches_per_agent(self) -> None:
        http = _mock_http()
        http.get.return_value = {"enabled": True}
        svc = VoiceService(http)
        svc.get_escalation_config("a1")
        assert (
            http.get.call_args[0][0]
            == "/voice-agents/a1/escalation-config"
        )

    def test_update_business_hours_puts(self) -> None:
        http = _mock_http()
        http.put.return_value = {"ok": True}
        svc = VoiceService(http)
        svc.update_business_hours("a1", {"mon": "9-17"})
        assert http.put.call_args[0][0] == "/voice-agents/a1/business-hours"


# ---------------------------------------------------------------------------
# Agent testing
# ---------------------------------------------------------------------------


class TestVoiceAgentTesting:
    def test_test_agent_default_scenario_count(self) -> None:
        http = _mock_http()
        http.post.return_value = {"scorecard": {"passed": 5}}
        svc = VoiceService(http)
        svc.test_agent(tenant_id="t1")
        assert http.post.call_args[0][0] == "/voice-agents/test"
        body = http.post.call_args.kwargs["json"]
        assert body == {"tenant_id": "t1", "scenario_count": 5}

    def test_test_agent_custom_scenario_count(self) -> None:
        http = _mock_http()
        http.post.return_value = {"scorecard": {}}
        svc = VoiceService(http)
        svc.test_agent(tenant_id="t1", scenario_count=20)
        body = http.post.call_args.kwargs["json"]
        assert body["scenario_count"] == 20


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


class TestVoiceErrors:
    def test_list_configs_propagates_server_error(self) -> None:
        http = _mock_http()
        http.get.side_effect = OlympusApiError(
            code="UPSTREAM_UNAVAILABLE", message="voice down", status_code=503
        )
        svc = VoiceService(http)
        with pytest.raises(OlympusApiError) as exc:
            svc.list_configs()
        assert exc.value.status_code == 503

    def test_create_agent_surfaces_validation_error(self) -> None:
        http = _mock_http()
        http.post.side_effect = OlympusApiError(
            code="VALIDATION_FAILED", message="name required", status_code=400
        )
        svc = VoiceService(http)
        with pytest.raises(OlympusApiError) as exc:
            svc.create_agent()
        assert exc.value.code == "VALIDATION_FAILED"
