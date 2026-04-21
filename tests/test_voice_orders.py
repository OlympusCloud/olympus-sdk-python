"""Tests for VoiceOrdersService (Wave 2 coverage — already at dart parity).

The service was originally shipped in 029718a (Wave 1); Wave 2 adds the
test fixtures that were missing.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olympus_sdk.http import OlympusHttpClient
from olympus_sdk.services.voice_orders import VoiceOrdersService


def _mock_http() -> MagicMock:
    return MagicMock(spec=OlympusHttpClient)


class TestVoiceOrdersService:
    def test_create_posts_to_voice_orders_root(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "vo-1", "status": "pending"}
        svc = VoiceOrdersService(http)
        resp = svc.create({
            "location_id": "loc-1",
            "items": [{"menu_item_id": "m1", "quantity": 1, "unit_price": 999}],
            "caller_phone": "+15550000000",
        })
        assert resp["id"] == "vo-1"
        assert http.post.call_args[0][0] == "/voice-orders"
        # Dict body passes through unchanged
        assert http.post.call_args.kwargs["json"]["location_id"] == "loc-1"

    def test_get_fetches_by_id(self) -> None:
        http = _mock_http()
        http.get.return_value = {"id": "vo-2", "status": "confirmed"}
        svc = VoiceOrdersService(http)
        order = svc.get("vo-2")
        assert order["status"] == "confirmed"
        assert http.get.call_args[0][0] == "/voice-orders/vo-2"

    def test_list_sends_all_filters(self) -> None:
        http = _mock_http()
        http.get.return_value = {"orders": []}
        svc = VoiceOrdersService(http)
        svc.list(
            caller_phone="+15550000000",
            status="pending",
            location_id="loc-1",
            limit=50,
        )
        assert http.get.call_args[0][0] == "/voice-orders"
        params = http.get.call_args.kwargs["params"]
        assert params == {
            "caller_phone": "+15550000000",
            "status": "pending",
            "location_id": "loc-1",
            "limit": 50,
        }

    def test_push_to_pos_hits_subpath(self) -> None:
        http = _mock_http()
        http.post.return_value = {"pushed": True, "pos_provider": "toast"}
        svc = VoiceOrdersService(http)
        resp = svc.push_to_pos("vo-1")
        assert resp["pushed"] is True
        assert http.post.call_args[0][0] == "/voice-orders/vo-1/push-pos"

    def test_get_propagates_error(self) -> None:
        from olympus_sdk import OlympusApiError

        http = _mock_http()
        http.get.side_effect = OlympusApiError(
            code="NOT_FOUND", message="missing", status_code=404
        )
        svc = VoiceOrdersService(http)
        with pytest.raises(OlympusApiError):
            svc.get("missing-id")
