"""Tests for :class:`TenantService` (olympus-cloud-gcp#3403 §2 + §4.4 / PR #3410).

These use ``MagicMock(spec=OlympusHttpClient)`` rather than httpx
``MockTransport`` because every other service test in this SDK uses the
same pattern and the httpx client is sync — consistency over the literal
spec wording.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olympus_sdk import (
    ExchangedSession,
    OlympusApiError,
    Tenant,
    TenantFirstAdmin,
    TenantOption,
    TenantProvisionResult,
    TenantService,
    TenantUpdate,
)
from olympus_sdk.http import OlympusHttpClient


def _mock_http() -> MagicMock:
    return MagicMock(spec=OlympusHttpClient)


def _tenant_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "11111111-1111-1111-1111-111111111111",
        "slug": "test-tenant",
        "name": "Test Tenant",
        "industry": "restaurant",
        "subscription_tier": "spark",
        "is_active": True,
        "is_suspended": False,
        "created_at": "2026-04-21T00:00:00Z",
        "updated_at": "2026-04-21T00:00:00Z",
    }
    base.update(overrides)
    return base


class TestTenantCreate:
    def test_create_posts_full_payload_and_returns_result(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "tenant": _tenant_payload(),
            "admin_user_id": "aaa-111",
            "session": {
                "access_token": None,
                "refresh_token": None,
                "access_expires_at": None,
            },
            "installed_apps": [
                {"app_id": "com.pizzaos.app", "status": "active", "installed_at": "2026-04-21T00:00:00Z"},
            ],
            "idempotent": False,
        }
        svc = TenantService(http)
        result = svc.create(
            brand_name="Test Tenant",
            slug="test-tenant",
            plan="demo",
            first_admin=TenantFirstAdmin(
                email="admin@example.com",
                first_name="Ada",
                last_name="Lovelace",
                firebase_link="fb-abc",
            ),
            install_apps=["com.pizzaos.app"],
            billing_address="1 Market St",
            tax_id="tax-001",
            idempotency_key="signup-key-1",
        )

        assert isinstance(result, TenantProvisionResult)
        assert result.tenant.slug == "test-tenant"
        assert result.admin_user_id == "aaa-111"
        assert result.idempotent is False
        assert len(result.installed_apps) == 1
        assert result.installed_apps[0].app_id == "com.pizzaos.app"

        assert http.post.call_args[0][0] == "/tenant/create"
        body = http.post.call_args.kwargs["json"]
        assert body["brand_name"] == "Test Tenant"
        assert body["slug"] == "test-tenant"
        assert body["plan"] == "demo"
        assert body["install_apps"] == ["com.pizzaos.app"]
        assert body["idempotency_key"] == "signup-key-1"
        assert body["billing_address"] == "1 Market St"
        assert body["tax_id"] == "tax-001"
        assert body["first_admin"] == {
            "email": "admin@example.com",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "firebase_link": "fb-abc",
        }

    def test_create_omits_optional_fields_when_none(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "tenant": _tenant_payload(),
            "admin_user_id": "",
            "session": {},
            "installed_apps": [],
            "idempotent": True,
        }
        svc = TenantService(http)
        svc.create(
            brand_name="Brand",
            slug="brand",
            plan="starter",
            first_admin=TenantFirstAdmin(
                email="a@b.c", first_name="A", last_name="B"
            ),
            install_apps=[],
            idempotency_key="k-1",
        )
        body = http.post.call_args.kwargs["json"]
        assert "billing_address" not in body
        assert "tax_id" not in body
        assert "firebase_link" not in body["first_admin"]

    def test_create_returns_idempotent_flag(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "tenant": _tenant_payload(),
            "admin_user_id": "",
            "session": {},
            "installed_apps": [],
            "idempotent": True,
        }
        svc = TenantService(http)
        result = svc.create(
            brand_name="B",
            slug="brand",
            plan="demo",
            first_admin=TenantFirstAdmin(email="a@b.c", first_name="A", last_name="B"),
            install_apps=[],
            idempotency_key="same-key",
        )
        assert result.idempotent is True

    def test_create_propagates_validation_error(self) -> None:
        http = _mock_http()
        http.post.side_effect = OlympusApiError(
            code="VALIDATION",
            message="slug must match [a-z0-9-]{3,63}",
            status_code=422,
        )
        svc = TenantService(http)
        with pytest.raises(OlympusApiError) as exc:
            svc.create(
                brand_name="X",
                slug="BAD SLUG",
                plan="demo",
                first_admin=TenantFirstAdmin(
                    email="a@b.c", first_name="A", last_name="B"
                ),
                install_apps=[],
                idempotency_key="k",
            )
        assert exc.value.status_code == 422


class TestTenantCurrentAndUpdate:
    def test_current_returns_tenant(self) -> None:
        http = _mock_http()
        http.get.return_value = _tenant_payload(slug="my-brand")
        svc = TenantService(http)
        tenant = svc.current()
        assert isinstance(tenant, Tenant)
        assert tenant.slug == "my-brand"
        assert http.get.call_args[0][0] == "/tenant/current"

    def test_update_patches_only_set_fields(self) -> None:
        http = _mock_http()
        http.patch.return_value = _tenant_payload(name="Updated")
        svc = TenantService(http)
        tenant = svc.update(TenantUpdate(brand_name="Updated", plan="pro"))
        assert tenant.name == "Updated"
        assert http.patch.call_args[0][0] == "/tenant/current"
        body = http.patch.call_args.kwargs["json"]
        assert body == {"brand_name": "Updated", "plan": "pro"}
        assert "billing_address" not in body
        assert "locale" not in body


class TestTenantRetireUnretire:
    def test_retire_posts_confirmation_slug_and_reason(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "tenant_id": "t-1",
            "retired_at": "2026-04-21T00:00:00Z",
            "purge_eligible_at": "2026-05-21T00:00:00Z",
        }
        svc = TenantService(http)
        svc.retire(confirmation_slug="my-brand", reason="shutting down")
        assert http.post.call_args[0][0] == "/tenant/retire"
        body = http.post.call_args.kwargs["json"]
        assert body == {"confirmation_slug": "my-brand", "reason": "shutting down"}

    def test_retire_omits_reason_when_none(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = TenantService(http)
        svc.retire(confirmation_slug="my-brand")
        body = http.post.call_args.kwargs["json"]
        assert body == {"confirmation_slug": "my-brand"}
        assert "reason" not in body

    def test_retire_propagates_mfa_required(self) -> None:
        http = _mock_http()
        http.post.side_effect = OlympusApiError(
            code="FORBIDDEN", message="mfa_required", status_code=403
        )
        svc = TenantService(http)
        with pytest.raises(OlympusApiError) as exc:
            svc.retire(confirmation_slug="my-brand")
        assert "mfa" in exc.value.message

    def test_unretire_posts_empty_body(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "tenant_id": "t-1",
            "unretired_at": "2026-04-21T00:00:00Z",
        }
        svc = TenantService(http)
        svc.unretire()
        assert http.post.call_args[0][0] == "/tenant/unretire"
        # No body passed — signal is the path alone
        assert "json" not in http.post.call_args.kwargs or http.post.call_args.kwargs.get("json") is None


class TestTenantMineAndSwitch:
    def test_my_tenants_parses_list_response(self) -> None:
        http = _mock_http()
        http.get.return_value = [
            {"tenant_id": "t-1", "slug": "one", "name": "One", "role": "tenant_admin"},
            {"tenant_id": "t-2", "slug": "two", "name": "Two", "role": None},
        ]
        svc = TenantService(http)
        options = svc.my_tenants()
        assert len(options) == 2
        assert all(isinstance(o, TenantOption) for o in options)
        assert options[0].slug == "one"
        assert options[0].role == "tenant_admin"
        assert options[1].role is None
        assert http.get.call_args[0][0] == "/tenant/mine"

    def test_my_tenants_parses_envelope_response(self) -> None:
        http = _mock_http()
        http.get.return_value = {
            "tenants": [
                {"tenant_id": "t-1", "slug": "one", "name": "One"},
            ],
        }
        svc = TenantService(http)
        options = svc.my_tenants()
        assert len(options) == 1
        assert options[0].tenant_id == "t-1"

    def test_my_tenants_returns_empty_when_server_is_empty(self) -> None:
        http = _mock_http()
        http.get.return_value = {}
        svc = TenantService(http)
        assert svc.my_tenants() == []

    def test_switch_tenant_posts_target_id(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "target_tenant_id": "t-2",
            "auth_endpoint": "/auth/switch-tenant",
            "instructions": "POST { access_token, tenant_id } to auth_endpoint",
        }
        svc = TenantService(http)
        session = svc.switch_tenant("t-2")
        # Platform returns redirect envelope (no tokens) — ExchangedSession
        # passthrough leaves fields empty.
        assert isinstance(session, ExchangedSession)
        assert session.access_token is None
        assert http.post.call_args[0][0] == "/tenant/switch"
        assert http.post.call_args.kwargs["json"] == {"tenant_id": "t-2"}

    def test_switch_tenant_carries_inline_mint(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "access_token": "new-jwt",
            "refresh_token": "new-refresh",
            "access_expires_at": "2026-04-21T01:00:00Z",
        }
        svc = TenantService(http)
        session = svc.switch_tenant("t-3")
        assert session.access_token == "new-jwt"
        assert session.refresh_token == "new-refresh"
