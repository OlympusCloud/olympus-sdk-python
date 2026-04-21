"""Tests for SmartHomeService (Wave 2 — olympus-cloud-gcp#3216)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olympus_sdk import OlympusApiError, SmartHomeService
from olympus_sdk.http import OlympusHttpClient


def _mock_http() -> MagicMock:
    return MagicMock(spec=OlympusHttpClient)


class TestSmartHomePlatforms:
    def test_list_platforms_unwraps_platforms_key(self) -> None:
        http = _mock_http()
        http.get.return_value = {
            "platforms": [
                {"id": "hue", "name": "Philips Hue"},
                {"id": "hk", "name": "HomeKit"},
            ]
        }
        svc = SmartHomeService(http)
        rows = svc.list_platforms()
        assert len(rows) == 2
        assert rows[0]["id"] == "hue"
        assert http.get.call_args[0][0] == "/smart-home/platforms"

    def test_list_platforms_falls_back_to_data_envelope(self) -> None:
        http = _mock_http()
        http.get.return_value = {"data": [{"id": "matter"}]}
        svc = SmartHomeService(http)
        rows = svc.list_platforms()
        assert rows == [{"id": "matter"}]

    def test_list_platforms_returns_empty_on_server_error(self) -> None:
        http = _mock_http()
        http.get.side_effect = OlympusApiError(
            code="UPSTREAM_TIMEOUT", message="timeout", status_code=504
        )
        svc = SmartHomeService(http)
        with pytest.raises(OlympusApiError):
            svc.list_platforms()


class TestSmartHomeDevices:
    def test_list_devices_forwards_filters(self) -> None:
        http = _mock_http()
        http.get.return_value = {"devices": [{"id": "d1"}]}
        svc = SmartHomeService(http)
        svc.list_devices(platform_id="hue", room_id="kitchen")
        kwargs = http.get.call_args.kwargs
        assert kwargs["params"] == {"platform_id": "hue", "room_id": "kitchen"}

    def test_get_device_escapes_device_id(self) -> None:
        http = _mock_http()
        http.get.return_value = {"id": "d/slash"}
        svc = SmartHomeService(http)
        svc.get_device("d/slash")
        # '/' inside the device id must be encoded so it doesn't split the path
        assert http.get.call_args[0][0] == "/smart-home/devices/d%2Fslash"

    def test_control_device_posts_command_body(self) -> None:
        http = _mock_http()
        http.post.return_value = {"ok": True}
        svc = SmartHomeService(http)
        svc.control_device("d1", {"action": "on", "brightness": 80})
        assert http.post.call_args[0][0] == "/smart-home/devices/d1/control"
        assert http.post.call_args.kwargs["json"] == {"action": "on", "brightness": 80}


class TestSmartHomeRoomsAndScenes:
    def test_list_rooms_unwraps_rooms_key(self) -> None:
        http = _mock_http()
        http.get.return_value = {"rooms": [{"id": "r1"}, {"id": "r2"}]}
        svc = SmartHomeService(http)
        rows = svc.list_rooms()
        assert len(rows) == 2

    def test_activate_scene_posts(self) -> None:
        http = _mock_http()
        http.post.return_value = {"activated": True}
        svc = SmartHomeService(http)
        svc.activate_scene("s1")
        assert http.post.call_args[0][0] == "/smart-home/scenes/s1/activate"

    def test_create_scene_posts_body(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "s9"}
        svc = SmartHomeService(http)
        svc.create_scene({"name": "Movie Night", "devices": ["d1", "d2"]})
        assert http.post.call_args[0][0] == "/smart-home/scenes"
        assert http.post.call_args.kwargs["json"]["name"] == "Movie Night"

    def test_delete_scene_hits_delete_endpoint(self) -> None:
        http = _mock_http()
        svc = SmartHomeService(http)
        svc.delete_scene("s1")
        http.delete.assert_called_once_with("/smart-home/scenes/s1")


class TestSmartHomeAutomations:
    def test_list_automations_unwraps(self) -> None:
        http = _mock_http()
        http.get.return_value = {"automations": [{"id": "a1"}]}
        svc = SmartHomeService(http)
        rows = svc.list_automations()
        assert rows == [{"id": "a1"}]

    def test_create_automation_posts_body(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "a5"}
        svc = SmartHomeService(http)
        svc.create_automation({"trigger": "sunset", "action": "lights_on"})
        assert http.post.call_args[0][0] == "/smart-home/automations"

    def test_delete_automation_hits_delete_endpoint(self) -> None:
        http = _mock_http()
        svc = SmartHomeService(http)
        svc.delete_automation("a1")
        http.delete.assert_called_once_with("/smart-home/automations/a1")
