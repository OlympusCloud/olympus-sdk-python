"""Tests for :class:`IdentityService` invite surface (#3403 §4.2 + §4.4 / PR #3410).

Lives alongside ``tests/test_identity.py`` (which covers the Wave-2
Firebase / age-verification / passphrase surface) so the invite-specific
fixtures and assertions stay isolated per #3403 §4.2.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olympus_sdk import IdentityService, InviteHandle, OlympusApiError
from olympus_sdk.http import OlympusHttpClient


def _mock_http() -> MagicMock:
    return MagicMock(spec=OlympusHttpClient)


def _invite_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "inv-1",
        "email": "new@example.com",
        "role": "manager",
        "tenant_id": "tenant-1",
        "expires_at": "2026-04-28T00:00:00Z",
        "status": "pending",
        "created_at": "2026-04-21T00:00:00Z",
        "token": "signed.invite.jwt",
    }
    base.update(overrides)
    return base


class TestIdentityInviteCreate:
    def test_invite_posts_full_payload(self) -> None:
        http = _mock_http()
        http.post.return_value = _invite_payload()
        svc = IdentityService(http)
        handle = svc.invite(
            email="new@example.com",
            role="manager",
            location_id="loc-1",
            message="Welcome aboard",
            ttl_seconds=86400,
        )
        assert isinstance(handle, InviteHandle)
        assert handle.id == "inv-1"
        assert handle.email == "new@example.com"
        assert handle.role == "manager"
        assert handle.status == "pending"
        assert handle.token == "signed.invite.jwt"

        assert http.post.call_args[0][0] == "/identity/invite"
        body = http.post.call_args.kwargs["json"]
        assert body == {
            "email": "new@example.com",
            "role": "manager",
            "location_id": "loc-1",
            "message": "Welcome aboard",
            "ttl_seconds": 86400,
        }

    def test_invite_omits_optional_fields_when_unset(self) -> None:
        http = _mock_http()
        http.post.return_value = _invite_payload(location_id=None, token=None)
        svc = IdentityService(http)
        svc.invite(email="a@b.c", role="staff")
        body = http.post.call_args.kwargs["json"]
        assert body == {"email": "a@b.c", "role": "staff"}
        assert "location_id" not in body
        assert "message" not in body
        assert "ttl_seconds" not in body

    def test_invite_propagates_invalid_role(self) -> None:
        http = _mock_http()
        http.post.side_effect = OlympusApiError(
            code="VALIDATION",
            message="role 'god' not allowed on invite surface",
            status_code=422,
        )
        svc = IdentityService(http)
        with pytest.raises(OlympusApiError) as exc:
            svc.invite(email="a@b.c", role="god")
        assert exc.value.status_code == 422

    def test_invite_propagates_forbidden_when_caller_lacks_role(self) -> None:
        http = _mock_http()
        http.post.side_effect = OlympusApiError(
            code="FORBIDDEN",
            message="manager or tenant_admin role required",
            status_code=403,
        )
        svc = IdentityService(http)
        with pytest.raises(OlympusApiError) as exc:
            svc.invite(email="a@b.c", role="manager")
        assert exc.value.status_code == 403


class TestIdentityInviteList:
    def test_list_invites_parses_list_response(self) -> None:
        http = _mock_http()
        http.get.return_value = [
            _invite_payload(id="inv-1", token=None),
            _invite_payload(id="inv-2", status="accepted", token=None, accepted_at="2026-04-22T00:00:00Z"),
        ]
        svc = IdentityService(http)
        rows = svc.list_invites()
        assert len(rows) == 2
        assert rows[0].id == "inv-1"
        # Server never echoes the token on list.
        assert rows[0].token is None
        assert rows[1].status == "accepted"
        assert rows[1].accepted_at == "2026-04-22T00:00:00Z"
        assert http.get.call_args[0][0] == "/identity/invites"

    def test_list_invites_parses_envelope_response(self) -> None:
        http = _mock_http()
        http.get.return_value = {"invites": [_invite_payload(token=None)]}
        svc = IdentityService(http)
        rows = svc.list_invites()
        assert len(rows) == 1
        assert rows[0].id == "inv-1"

    def test_list_invites_returns_empty_when_missing(self) -> None:
        http = _mock_http()
        http.get.return_value = {}
        svc = IdentityService(http)
        assert svc.list_invites() == []


class TestIdentityInviteAccept:
    def test_accept_posts_firebase_token_and_encodes_path(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "access_token": "sess-jwt",
            "refresh_token": "sess-refresh",
            "user": {"id": "u-1", "email": "new@example.com"},
            "tenant_id": "tenant-1",
        }
        svc = IdentityService(http)
        # Token intentionally contains URL-special characters to exercise
        # the quote() escaping on the path.
        token = "ey.JhbGciOi/JSUzI1NiIsImt.signed"
        result = svc.accept_invite(token, "firebase-id-token-abc")
        assert result["access_token"] == "sess-jwt"
        assert http.post.call_args[0][0].startswith("/identity/invites/")
        assert http.post.call_args[0][0].endswith("/accept")
        # Path segment must NOT contain raw '/' (besides the wrapping segments)
        # and must not contain a raw '.' token boundary that httpx might route wrong —
        # quote() with safe='' escapes both '/' and '.'? Actually '.' is a safe default
        # for urllib.parse.quote, so only '/' is guaranteed escaped. Assert the slash.
        middle = http.post.call_args[0][0].removeprefix("/identity/invites/").removesuffix("/accept")
        assert "/" not in middle
        body = http.post.call_args.kwargs["json"]
        assert body == {"firebase_id_token": "firebase-id-token-abc"}

    def test_accept_propagates_invite_expired(self) -> None:
        http = _mock_http()
        http.post.side_effect = OlympusApiError(
            code="BAD_REQUEST",
            message="invite_expired",
            status_code=400,
        )
        svc = IdentityService(http)
        with pytest.raises(OlympusApiError) as exc:
            svc.accept_invite("expired.token", "fb-token")
        assert exc.value.message == "invite_expired"

    def test_accept_propagates_email_mismatch(self) -> None:
        http = _mock_http()
        http.post.side_effect = OlympusApiError(
            code="FORBIDDEN",
            message="firebase email does not match invite email",
            status_code=403,
        )
        svc = IdentityService(http)
        with pytest.raises(OlympusApiError):
            svc.accept_invite("valid.token", "fb-wrong-email")


class TestIdentityInviteRevoke:
    def test_revoke_posts_to_invite_id_path(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = IdentityService(http)
        svc.revoke_invite("inv-1")
        assert http.post.call_args[0][0] == "/identity/invites/inv-1/revoke"

    def test_revoke_is_idempotent_on_already_revoked(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = IdentityService(http)
        svc.revoke_invite("inv-1")
        svc.revoke_invite("inv-1")  # no error on second call
        assert http.post.call_count == 2


class TestIdentityRemoveFromTenant:
    def test_remove_posts_user_id_and_reason(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "tenant_id": "tenant-1",
            "user_id": "u-1",
            "removed_at": "2026-04-21T00:00:00Z",
        }
        svc = IdentityService(http)
        resp = svc.remove_from_tenant(user_id="u-1", reason="offboarded")
        assert resp["user_id"] == "u-1"
        assert http.post.call_args[0][0] == "/identity/remove_from_tenant"
        assert http.post.call_args.kwargs["json"] == {
            "user_id": "u-1",
            "reason": "offboarded",
        }

    def test_remove_omits_reason_when_none(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = IdentityService(http)
        svc.remove_from_tenant(user_id="u-1")
        body = http.post.call_args.kwargs["json"]
        assert body == {"user_id": "u-1"}
        assert "reason" not in body

    def test_remove_propagates_forbidden(self) -> None:
        http = _mock_http()
        http.post.side_effect = OlympusApiError(
            code="FORBIDDEN",
            message="tenant_admin role required",
            status_code=403,
        )
        svc = IdentityService(http)
        with pytest.raises(OlympusApiError) as exc:
            svc.remove_from_tenant(user_id="u-1")
        assert exc.value.status_code == 403
