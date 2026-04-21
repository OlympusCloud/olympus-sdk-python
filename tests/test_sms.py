"""Tests for SmsService (Wave 2 — olympus-cloud-gcp#3216)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olympus_sdk import OlympusApiError, SmsService
from olympus_sdk.http import OlympusHttpClient


def _mock_http() -> MagicMock:
    return MagicMock(spec=OlympusHttpClient)


class TestVoicePlatformSms:
    def test_send_posts_to_voice_sms_send(self) -> None:
        http = _mock_http()
        http.post.return_value = {"message_id": "m1", "status": "queued"}
        svc = SmsService(http)
        resp = svc.send(config_id="cfg-1", to="+15550000000", body="Hello")
        assert resp["message_id"] == "m1"
        assert http.post.call_args[0][0] == "/voice/sms/send"
        assert http.post.call_args.kwargs["json"] == {
            "config_id": "cfg-1",
            "to": "+15550000000",
            "body": "Hello",
        }

    def test_get_conversations_escapes_phone_and_unwraps_list(self) -> None:
        http = _mock_http()
        http.get.return_value = {
            "conversations": [{"id": "c1"}, {"id": "c2"}]
        }
        svc = SmsService(http)
        rows = svc.get_conversations("+1 555-000-0000", limit=10, offset=20)
        assert len(rows) == 2
        path = http.get.call_args[0][0]
        assert path.startswith("/voice/sms/conversations/")
        # Space and + must be URL-escaped; check only that they're gone
        assert " " not in path
        assert "+" not in path.split("/voice/sms/conversations/")[1]
        assert http.get.call_args.kwargs["params"] == {"limit": 10, "offset": 20}

    def test_get_conversations_falls_back_to_data_envelope(self) -> None:
        http = _mock_http()
        http.get.return_value = {"data": [{"id": "d1"}]}
        svc = SmsService(http)
        rows = svc.get_conversations("+15550000000")
        assert rows == [{"id": "d1"}]


class TestCpaasMessaging:
    def test_send_via_cpaas_renames_from_on_the_wire(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "msg-1", "status": "queued"}
        svc = SmsService(http)
        svc.send_via_cpaas(from_="+15551110000", to="+15552220000", body="hi")
        assert http.post.call_args[0][0] == "/cpaas/messages/sms"
        body = http.post.call_args.kwargs["json"]
        # 'from_' kwarg must serialize as 'from' on the wire
        assert body["from"] == "+15551110000"
        assert "from_" not in body
        assert body["body"] == "hi"
        # webhook_url omitted when not provided
        assert "webhook_url" not in body

    def test_send_via_cpaas_includes_optional_webhook(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "msg-2"}
        svc = SmsService(http)
        svc.send_via_cpaas(
            from_="+15551110000",
            to="+15552220000",
            body="hi",
            webhook_url="https://hook.example/cpaas",
        )
        body = http.post.call_args.kwargs["json"]
        assert body["webhook_url"] == "https://hook.example/cpaas"

    def test_get_status_escapes_message_id(self) -> None:
        http = _mock_http()
        http.get.return_value = {"id": "m1", "status": "delivered"}
        svc = SmsService(http)
        svc.get_status("m/weird id")
        path = http.get.call_args[0][0]
        assert path.startswith("/cpaas/messages/")
        assert path != "/cpaas/messages/m/weird id"  # escaped, not literal

    def test_get_status_propagates_server_error(self) -> None:
        http = _mock_http()
        http.get.side_effect = OlympusApiError(
            code="NOT_FOUND", message="missing", status_code=404
        )
        svc = SmsService(http)
        with pytest.raises(OlympusApiError) as exc:
            svc.get_status("msg-404")
        assert exc.value.status_code == 404
