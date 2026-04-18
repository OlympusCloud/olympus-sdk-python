"""Tests for app-scoped permissions v2.0 surface (olympus-cloud-gcp#3254)."""

from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from olympus_sdk import (
    BillingGraceExceeded,
    ConsentRequired,
    ConsentService,
    DeviceChanged,
    GovernanceService,
    OlympusClient,
    OlympusConfig,
    ScopeDenied,
)


# ---------------------------------------------------------------------------
# JWT + bitset helpers
# ---------------------------------------------------------------------------


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _make_jwt(claims: dict[str, Any]) -> str:
    header = _b64u(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = _b64u(json.dumps(claims).encode())
    return f"{header}.{payload}.signature-placeholder"


def _make_bitset(bits: list[int], size_bytes: int = 128) -> str:
    buf = bytearray(size_bytes)
    for b in bits:
        buf[b // 8] |= 1 << (b % 8)
    return _b64u(bytes(buf))


def _make_client() -> OlympusClient:
    return OlympusClient(
        app_id="test-app",
        api_key="oc_test_key",
        config=OlympusConfig(
            app_id="test-app", api_key="oc_test_key", base_url="https://api.test"
        ),
    )


# ---------------------------------------------------------------------------
# OlympusClient helpers
# ---------------------------------------------------------------------------


class TestClientHelpers:
    def test_consent_and_governance_accessors_are_services(self) -> None:
        oc = _make_client()
        assert isinstance(oc.consent, ConsentService)
        assert isinstance(oc.governance, GovernanceService)

    def test_has_scope_bit_returns_false_without_token(self) -> None:
        oc = _make_client()
        assert not oc.has_scope_bit(0)
        assert not oc.has_scope_bit(1023)
        assert not oc.is_app_scoped()

    def test_platform_shell_token_carries_no_app_claims(self) -> None:
        oc = _make_client()
        token = _make_jwt({
            "sub": "u", "tenant_id": "t", "session_id": "s",
            "roles": ["tenant_admin"], "iat": 0, "exp": 9999999999,
            "iss": "i", "aud": "a",
        })
        oc.set_access_token(token)
        assert not oc.has_scope_bit(0)
        assert not oc.is_app_scoped()

    def test_app_scoped_token_has_bit_set_and_unset(self) -> None:
        oc = _make_client()
        bitset = _make_bitset([0, 7, 8, 127, 1023])
        token = _make_jwt({
            "sub": "u", "tenant_id": "t", "session_id": "s",
            "roles": ["staff"],
            "app_id": "pizza-os",
            "app_scopes_bitset": bitset,
            "platform_catalog_digest": "d1",
            "app_catalog_digest": "d2",
            "iat": 0, "exp": 9999999999, "iss": "i", "aud": "a",
        })
        oc.set_access_token(token)

        assert oc.is_app_scoped()
        assert oc.has_scope_bit(0)
        assert oc.has_scope_bit(7)
        assert oc.has_scope_bit(8)
        assert oc.has_scope_bit(127)
        assert oc.has_scope_bit(1023)
        # Unset
        assert not oc.has_scope_bit(1)
        assert not oc.has_scope_bit(6)
        assert not oc.has_scope_bit(500)
        # Out of range
        assert not oc.has_scope_bit(2048)
        # Negative bit_id — must NOT end-relative-index into the bitset
        assert not oc.has_scope_bit(-1)
        assert not oc.has_scope_bit(-1024)

    def test_bitset_cache_invalidated_on_token_change(self) -> None:
        oc = _make_client()
        token_a = _make_jwt({
            "sub": "u", "tenant_id": "t", "session_id": "s", "roles": [],
            "app_id": "app-a", "app_scopes_bitset": _make_bitset([0]),
            "iat": 0, "exp": 9999999999, "iss": "i", "aud": "a",
        })
        token_b = _make_jwt({
            "sub": "u", "tenant_id": "t", "session_id": "s", "roles": [],
            "app_id": "app-b", "app_scopes_bitset": _make_bitset([5]),
            "iat": 0, "exp": 9999999999, "iss": "i", "aud": "a",
        })
        oc.set_access_token(token_a)
        assert oc.has_scope_bit(0)
        assert not oc.has_scope_bit(5)
        oc.set_access_token(token_b)
        assert not oc.has_scope_bit(0)
        assert oc.has_scope_bit(5)


# ---------------------------------------------------------------------------
# HTTP error dispatch
# ---------------------------------------------------------------------------


class TestErrorDispatch:
    def test_scope_not_granted_raises_consent_required(self) -> None:
        resp = httpx.Response(
            status_code=403,
            json={
                "error": {
                    "code": "scope_not_granted",
                    "message": "commerce.order.write@tenant required",
                    "scope": "commerce.order.write@tenant",
                    "consent_url": "https://api/platform/authorize?...",
                }
            },
        )
        with pytest.raises(ConsentRequired) as exc:
            OlympusClient(app_id="x", api_key="y").http_client._raise_on_error(resp)
        assert exc.value.scope == "commerce.order.write@tenant"
        assert exc.value.consent_url == "https://api/platform/authorize?..."

    def test_scope_denied_raises_typed(self) -> None:
        resp = httpx.Response(
            status_code=403,
            json={
                "error": {"code": "scope_denied", "message": "stale", "scope": "pizza.menu.read@tenant"}
            },
        )
        with pytest.raises(ScopeDenied) as exc:
            OlympusClient(app_id="x", api_key="y").http_client._raise_on_error(resp)
        assert exc.value.scope == "pizza.menu.read@tenant"

    def test_billing_grace_exceeded_pulls_header_fallbacks(self) -> None:
        resp = httpx.Response(
            status_code=402,
            headers={
                "X-Olympus-Grace-Until": "2026-04-25T00:00:00Z",
                "X-Olympus-Upgrade-URL": "https://billing/upgrade",
            },
            json={"error": {"code": "billing_grace_exceeded", "message": "lapsed"}},
        )
        with pytest.raises(BillingGraceExceeded) as exc:
            OlympusClient(app_id="x", api_key="y").http_client._raise_on_error(resp)
        assert exc.value.grace_until == "2026-04-25T00:00:00Z"
        assert exc.value.upgrade_url == "https://billing/upgrade"

    def test_webauthn_required_raises_device_changed(self) -> None:
        resp = httpx.Response(
            status_code=401,
            json={
                "error": {
                    "code": "webauthn_required",
                    "message": "new device",
                    "challenge": "abc123",
                },
                "requires_reconsent": True,
            },
        )
        with pytest.raises(DeviceChanged) as exc:
            OlympusClient(app_id="x", api_key="y").http_client._raise_on_error(resp)
        assert exc.value.challenge == "abc123"
        assert exc.value.requires_reconsent is True


# ---------------------------------------------------------------------------
# ConsentService
# ---------------------------------------------------------------------------


class TestConsentService:
    def test_list_granted_tenant_default_hits_tenant_grants(self) -> None:
        http = MagicMock()
        http.get.return_value = {"grants": []}
        svc = ConsentService(http)
        svc.list_granted(app_id="pizza-os")
        path = http.get.call_args[0][0]
        assert path == "/api/v1/platform/apps/pizza-os/tenant-grants"

    def test_list_granted_user_holder_hits_user_grants(self) -> None:
        http = MagicMock()
        http.get.return_value = {"grants": []}
        svc = ConsentService(http)
        svc.list_granted(app_id="aura-ai", holder="user")
        path = http.get.call_args[0][0]
        assert path == "/api/v1/platform/apps/aura-ai/user-grants"

    def test_describe_returns_consent_prompt_with_hash(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "scope": "aura.calendar.read@user",
            "description": "Read calendar",
            "consent_copy": "Aura will read your calendar.",
            "prompt_hash": "abc",
            "is_destructive": False,
            "requires_mfa": False,
        }
        svc = ConsentService(http)
        prompt = svc.describe(app_id="aura-ai", scope="aura.calendar.read@user")
        assert prompt.prompt_hash == "abc"

    def test_grant_user_scope_sends_prompt_hash(self) -> None:
        http = MagicMock()
        http.post.return_value = {
            "tenant_id": "t", "app_id": "aura", "scope": "aura.calendar.read@user",
            "granted_at": "2026-04-18T00:00:00Z", "source": "admin_ui",
        }
        svc = ConsentService(http)
        svc.grant(
            app_id="aura-ai", scope="aura.calendar.read@user",
            holder="user", prompt_hash="abc123",
        )
        call_json = http.post.call_args.kwargs["json"]
        assert call_json["consent_prompt_hash"] == "abc123"

    def test_revoke_builds_correct_delete_path(self) -> None:
        http = MagicMock()
        svc = ConsentService(http)
        svc.revoke(app_id="pizza-os", scope="pizza.orders.write@tenant", holder="tenant")
        assert http.delete.call_args[0][0].endswith("pizza.orders.write%40tenant")


# ---------------------------------------------------------------------------
# GovernanceService
# ---------------------------------------------------------------------------


class TestGovernanceService:
    def test_request_exception_posts_to_platform_exceptions(self) -> None:
        http = MagicMock()
        http.post.return_value = {
            "exception_id": "ex-1",
            "app_id": "pizza-os",
            "policy_key": "session_ttl_role_ceiling",
            "requested_value": {"role": "staff", "max_seconds": 54000},
            "risk_tier": "medium",
            "risk_score": 0.47,
            "risk_rationale": "staff × 1.0",
            "status": "pending_review",
            "expires_at": "2026-07-17T00:00:00Z",
            "justification": "x" * 120,
            "created_at": "2026-04-18T00:00:00Z",
            "updated_at": "2026-04-18T00:00:00Z",
        }
        svc = GovernanceService(http)
        req = svc.request_exception(
            policy_key="session_ttl_role_ceiling",
            requested_value={"role": "staff", "max_seconds": 54000},
            justification="x" * 120,
        )
        assert req.risk_tier == "medium"
        assert req.status == "pending_review"
        assert http.post.call_args[0][0] == "/api/v1/platform/exceptions"

    def test_list_exceptions_filters(self) -> None:
        http = MagicMock()
        http.get.return_value = {"exceptions": []}
        svc = GovernanceService(http)
        svc.list_exceptions(app_id="aura-ai", status="approved")
        kwargs = http.get.call_args.kwargs
        assert kwargs["params"]["app_id"] == "aura-ai"
        assert kwargs["params"]["status"] == "approved"

    def test_get_exception_fetches_by_id(self) -> None:
        http = MagicMock()
        http.get.return_value = {"exception_id": "ex-123", "app_id": "pizza-os"}
        svc = GovernanceService(http)
        svc.get_exception("ex-123")
        assert http.get.call_args[0][0].endswith("/platform/exceptions/ex-123")


# ---------------------------------------------------------------------------
# Typed error classes direct instantiation
# ---------------------------------------------------------------------------


class TestTypedErrors:
    def test_consent_required_carries_scope_and_consent_url(self) -> None:
        e = ConsentRequired(
            scope="aura.calendar.read@user",
            consent_url="https://platform/authorize",
            message="needs consent",
            status_code=403,
        )
        assert e.scope == "aura.calendar.read@user"
        assert e.consent_url == "https://platform/authorize"
        assert e.code == "CONSENT_REQUIRED"

    def test_scope_denied_carries_scope(self) -> None:
        e = ScopeDenied(scope="pizza.orders.refund@tenant", message="no", status_code=403)
        assert e.scope == "pizza.orders.refund@tenant"
        assert e.code == "SCOPE_DENIED"
