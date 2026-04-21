"""Tests for IdentityService (Wave 2 — olympus-cloud-gcp#3216)."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock

import pytest

from olympus_sdk import IdentityService, OlympusApiError, OlympusIdentity
from olympus_sdk.http import OlympusHttpClient


def _mock_http() -> MagicMock:
    return MagicMock(spec=OlympusHttpClient)


class TestIdentityService:
    # ------------------------------------------------------------------
    # Global identity (Firebase federation)
    # ------------------------------------------------------------------

    def test_get_or_create_from_firebase_returns_identity(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "id": "oid-1",
            "firebase_uid": "fb-abc",
            "email": "a@example.com",
            "created_at": "2026-04-19T00:00:00Z",
            "updated_at": "2026-04-19T00:00:00Z",
        }
        svc = IdentityService(http)
        identity = svc.get_or_create_from_firebase(firebase_uid="fb-abc", email="a@example.com")
        assert isinstance(identity, OlympusIdentity)
        assert identity.id == "oid-1"
        assert identity.firebase_uid == "fb-abc"
        assert identity.email == "a@example.com"
        # Path + payload shape
        assert http.post.call_args[0][0] == "/platform/identities"
        body = http.post.call_args.kwargs["json"]
        assert body["firebase_uid"] == "fb-abc"
        assert body["email"] == "a@example.com"
        # Optional fields are not included when None
        assert "phone" not in body

    def test_get_or_create_from_firebase_propagates_server_error(self) -> None:
        http = _mock_http()
        http.post.side_effect = OlympusApiError(
            code="INVALID_UID", message="bad uid", status_code=400
        )
        svc = IdentityService(http)
        with pytest.raises(OlympusApiError) as exc:
            svc.get_or_create_from_firebase(firebase_uid="")
        assert exc.value.code == "INVALID_UID"

    def test_link_to_tenant_posts_all_three_ids(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = IdentityService(http)
        svc.link_to_tenant(
            olympus_id="oid-1",
            tenant_id="ten-1",
            commerce_customer_id="cust-1",
        )
        assert http.post.call_args[0][0] == "/platform/identities/links"
        body = http.post.call_args.kwargs["json"]
        assert body == {
            "olympus_id": "oid-1",
            "tenant_id": "ten-1",
            "commerce_customer_id": "cust-1",
        }

    # ------------------------------------------------------------------
    # Age verification (Document AI)
    # ------------------------------------------------------------------

    def test_scan_id_base64_encodes_image_bytes(self) -> None:
        http = _mock_http()
        http.post.return_value = {"verified": True, "age": 34}
        svc = IdentityService(http)
        raw = b"\x89PNG\r\n\x1a\nfake-bytes"
        svc.scan_id("+15551234567", raw)
        assert http.post.call_args[0][0] == "/identity/scan-id"
        body = http.post.call_args.kwargs["json"]
        assert body["phone"] == "+15551234567"
        assert body["image"] == base64.b64encode(raw).decode("ascii")

    def test_check_verification_status_escapes_phone(self) -> None:
        http = _mock_http()
        http.get.return_value = {"status": "verified"}
        svc = IdentityService(http)
        svc.check_verification_status("+1 555-123-4567")
        # '+' and space must be URL-escaped
        assert http.get.call_args[0][0].startswith("/identity/status/")
        assert "+" not in http.get.call_args[0][0].split("/identity/status/")[1]

    def test_verify_passphrase_sends_phone_and_passphrase(self) -> None:
        http = _mock_http()
        http.post.return_value = {"verified": True}
        svc = IdentityService(http)
        svc.verify_passphrase("+15551234567", "hunter2")
        assert http.post.call_args[0][0] == "/identity/verify-passphrase"
        assert http.post.call_args.kwargs["json"] == {
            "phone": "+15551234567",
            "passphrase": "hunter2",
        }

    def test_set_passphrase_posts_to_set_endpoint(self) -> None:
        http = _mock_http()
        http.post.return_value = {"ok": True}
        svc = IdentityService(http)
        svc.set_passphrase("+15551234567", "n3w-p@ss")
        assert http.post.call_args[0][0] == "/identity/set-passphrase"
        assert http.post.call_args.kwargs["json"]["passphrase"] == "n3w-p@ss"

    def test_create_upload_session_posts_empty_body(self) -> None:
        http = _mock_http()
        http.post.return_value = {"upload_url": "https://...", "expires_at": "..."}
        svc = IdentityService(http)
        resp = svc.create_upload_session()
        assert resp["upload_url"].startswith("https://")
        assert http.post.call_args[0][0] == "/identity/create-upload-session"


class TestOlympusIdentityModel:
    def test_round_trip_preserves_optional_fields(self) -> None:
        payload = {
            "id": "oid-7",
            "firebase_uid": "fb-xyz",
            "email": "z@example.com",
            "phone": "+15550000000",
            "first_name": "Zoe",
            "last_name": "Zebra",
            "global_preferences": {"locale": "en-US"},
            "stripe_customer_id": "cus_abc",
            "created_at": "2026-04-01T00:00:00Z",
            "updated_at": "2026-04-02T00:00:00Z",
        }
        identity = OlympusIdentity.from_dict(payload)
        assert identity.email == "z@example.com"
        assert identity.stripe_customer_id == "cus_abc"
        assert identity.global_preferences == {"locale": "en-US"}
        # to_dict emits only set fields
        out = identity.to_dict()
        assert out["stripe_customer_id"] == "cus_abc"
        assert out["global_preferences"] == {"locale": "en-US"}

    def test_from_dict_tolerates_missing_optional_fields(self) -> None:
        identity = OlympusIdentity.from_dict(
            {
                "id": "oid-1",
                "firebase_uid": "fb-1",
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-01T00:00:00Z",
            }
        )
        assert identity.email is None
        assert identity.stripe_customer_id is None
        assert "email" not in identity.to_dict()
