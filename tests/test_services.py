"""Tests for all 13 service modules and their model deserialization."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from olympus_sdk.http import OlympusHttpClient
from olympus_sdk.models.ai import (
    AgentTask,
    SentimentResult,
)
from olympus_sdk.models.auth import AuthSession, User
from olympus_sdk.models.billing import Invoice, Plan, UsageReport
from olympus_sdk.models.commerce import (
    CatalogItem,
    Order,
)
from olympus_sdk.models.common import (
    Pagination,
    WebhookRegistration,
)
from olympus_sdk.models.device import Device
from olympus_sdk.models.marketplace import MarketplaceApp
from olympus_sdk.models.observe import TraceHandle
from olympus_sdk.models.pay import Balance, Payment, TerminalReader
from olympus_sdk.services.ai import AiService
from olympus_sdk.services.auth import AuthService
from olympus_sdk.services.billing import BillingService
from olympus_sdk.services.commerce import CommerceService
from olympus_sdk.services.data import DataService
from olympus_sdk.services.devices import DevicesService
from olympus_sdk.services.events import EventsService
from olympus_sdk.services.gating import GatingService
from olympus_sdk.services.marketplace import MarketplaceService
from olympus_sdk.services.notify import NotifyService
from olympus_sdk.services.observe import ObserveService
from olympus_sdk.services.pay import PayService
from olympus_sdk.services.storage import StorageService


def _mock_http() -> MagicMock:
    """Create a mock OlympusHttpClient."""
    return MagicMock(spec=OlympusHttpClient)


# =========================================================================
# Auth service tests
# =========================================================================


class TestAuthService:
    def test_login(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "access_token": "tok_abc",
            "token_type": "Bearer",
            "expires_in": 3600,
            "user_id": "u1",
            "tenant_id": "t1",
            "roles": ["admin"],
        }
        svc = AuthService(http)
        session = svc.login("user@test.com", "pass123")
        assert session.access_token == "tok_abc"
        assert session.user_id == "u1"
        assert session.roles == ["admin"]
        http.set_access_token.assert_called_once_with("tok_abc")

    def test_me(self) -> None:
        http = _mock_http()
        http.get.return_value = {"id": "u1", "email": "a@b.com", "name": "Alice"}
        svc = AuthService(http)
        user = svc.me()
        assert user.id == "u1"
        assert user.name == "Alice"

    def test_logout(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = AuthService(http)
        svc.logout()
        http.clear_access_token.assert_called_once()

    def test_create_user(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "u2", "email": "b@c.com", "name": "Bob"}
        svc = AuthService(http)
        user = svc.create_user(name="Bob", email="b@c.com", role="staff")
        assert user.email == "b@c.com"

    def test_check_permission(self) -> None:
        http = _mock_http()
        http.get.return_value = {"allowed": True}
        svc = AuthService(http)
        assert svc.check_permission("u1", "orders.create") is True

    def test_create_api_key(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "k1", "name": "test", "key": "oc_live_xxx", "scopes": ["read"]}
        svc = AuthService(http)
        key = svc.create_api_key("test", ["read"])
        assert key.key == "oc_live_xxx"


# =========================================================================
# has_scope / require_scope / granted_scopes helpers (#3403 §1.2)
# =========================================================================


class TestAuthServiceScopeHelpers:
    """#3403 §1.2 — client-side fail-fast scope assertion."""

    def test_granted_scopes_empty_before_login(self) -> None:
        http = _mock_http()
        svc = AuthService(http)
        assert svc.current_session is None
        assert svc.granted_scopes == frozenset()
        assert not svc.has_scope("commerce.order.read@tenant")

    def test_granted_scopes_from_login_response_body(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "access_token": "tok_abc",
            "token_type": "Bearer",
            "expires_in": 3600,
            "user_id": "u1",
            "tenant_id": "t1",
            "roles": ["manager"],
            "app_scopes": [
                "commerce.order.read@tenant",
                "commerce.order.write@tenant",
            ],
        }
        svc = AuthService(http)
        session = svc.login("u@test.com", "pw")
        assert session.app_scopes == [
            "commerce.order.read@tenant",
            "commerce.order.write@tenant",
        ]
        assert svc.current_session is session
        assert svc.granted_scopes == frozenset(
            {"commerce.order.read@tenant", "commerce.order.write@tenant"}
        )
        assert svc.has_scope("commerce.order.read@tenant")
        assert svc.has_scope("commerce.order.write@tenant")
        assert not svc.has_scope("pizza.menu.write@tenant")

    def test_granted_scopes_fall_back_to_jwt_claim(self) -> None:
        """When response body omits ``app_scopes`` but the JWT carries it."""
        import base64
        import json

        def _b64u(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

        header = _b64u(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        payload = _b64u(
            json.dumps(
                {
                    "sub": "u1",
                    "tenant_id": "t1",
                    "app_scopes": ["aura.calendar.read@user"],
                    "iat": 0,
                    "exp": 9999999999,
                }
            ).encode()
        )
        token = f"{header}.{payload}.sig"
        http = _mock_http()
        http.post.return_value = {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "user_id": "u1",
        }
        svc = AuthService(http)
        svc.login("u@test.com", "pw")
        assert svc.has_scope("aura.calendar.read@user")
        assert svc.granted_scopes == frozenset({"aura.calendar.read@user"})

    def test_require_scope_raises_when_missing(self) -> None:
        from olympus_sdk.errors import OlympusScopeRequiredError

        http = _mock_http()
        svc = AuthService(http)
        with pytest.raises(OlympusScopeRequiredError) as exc_info:
            svc.require_scope("commerce.order.write@tenant")
        assert exc_info.value.scope == "commerce.order.write@tenant"
        assert exc_info.value.code == "SCOPE_REQUIRED"
        assert exc_info.value.status_code == 403

    def test_require_scope_passes_when_granted(self) -> None:
        http = _mock_http()
        svc = AuthService(http)
        svc._current_session = AuthSession(  # type: ignore[attr-defined]
            access_token="tok",
            app_scopes=["commerce.order.write@tenant"],
        )
        # Must not raise
        svc.require_scope("commerce.order.write@tenant")

    def test_logout_clears_current_session(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "access_token": "tok_abc",
            "user_id": "u1",
            "app_scopes": ["platform.user.profile.read@user"],
        }
        svc = AuthService(http)
        svc.login("u@t.com", "pw")
        assert svc.current_session is not None
        assert svc.has_scope("platform.user.profile.read@user")

        svc.logout()
        assert svc.current_session is None
        assert svc.granted_scopes == frozenset()
        assert not svc.has_scope("platform.user.profile.read@user")

    def test_has_scope_uses_generated_constants(self) -> None:
        """The ``OlympusScopes`` generated constants are usable in ``has_scope``."""
        from olympus_sdk.constants import OlympusScopes

        http = _mock_http()
        svc = AuthService(http)
        svc._current_session = AuthSession(  # type: ignore[attr-defined]
            access_token="tok",
            app_scopes=[OlympusScopes.PLATFORM_USER_PROFILE_READ_AT_USER],
        )
        assert svc.has_scope(OlympusScopes.PLATFORM_USER_PROFILE_READ_AT_USER)


# =========================================================================
# Commerce service tests
# =========================================================================


class TestCommerceService:
    def test_create_order(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "ord-1", "status": "pending", "total": 2598}
        svc = CommerceService(http)
        order = svc.create_order(
            items=[{"catalog_id": "burger", "qty": 2, "price": 1299}],
            source="pos",
        )
        assert order.id == "ord-1"
        assert order.total == 2598

    def test_get_order(self) -> None:
        http = _mock_http()
        http.get.return_value = {"id": "ord-2", "status": "completed"}
        svc = CommerceService(http)
        order = svc.get_order("ord-2")
        assert order.status == "completed"

    def test_list_orders(self) -> None:
        http = _mock_http()
        http.get.return_value = {
            "data": [{"id": "o1", "status": "pending"}, {"id": "o2", "status": "ready"}],
            "pagination": {"page": 1, "per_page": 20, "total": 2, "total_pages": 1},
        }
        svc = CommerceService(http)
        result = svc.list_orders(status="pending")
        assert len(result.data) == 2

    def test_cancel_order(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = CommerceService(http)
        svc.cancel_order("ord-1", "changed mind")
        http.post.assert_called_once()

    def test_get_catalog(self) -> None:
        http = _mock_http()
        http.get.return_value = {"items": [{"id": "c1", "name": "Burger", "price": 999}]}
        svc = CommerceService(http)
        catalog = svc.get_catalog()
        assert len(catalog) == 1
        assert catalog[0].name == "Burger"


# =========================================================================
# AI service tests
# =========================================================================


class TestAiService:
    def test_query(self) -> None:
        http = _mock_http()
        http.post.return_value = {"content": "Burgers sold best", "tier": "T2", "tokens_used": 42}
        svc = AiService(http)
        resp = svc.query("What sold best?", tier="T2")
        assert resp.content == "Burgers sold best"
        assert resp.tier == "T2"
        assert resp.tokens_used == 42

    def test_chat(self) -> None:
        http = _mock_http()
        http.post.return_value = {"content": "Hello!"}
        svc = AiService(http)
        resp = svc.chat([{"role": "user", "content": "Hi"}])
        assert resp.content == "Hello!"

    def test_invoke_agent(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "output": "Done",
            "agent_name": "rex",
            "steps": [{"action": "analyze", "observation": "found data"}],
        }
        svc = AiService(http)
        result = svc.invoke_agent("rex", "Check inventory")
        assert result.output == "Done"
        assert len(result.steps) == 1
        assert result.steps[0].action == "analyze"

    def test_create_task(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "task-1", "status": "pending"}
        svc = AiService(http)
        task = svc.create_task("rex", "Long analysis")
        assert task.is_pending

    def test_classify(self) -> None:
        http = _mock_http()
        http.post.return_value = {"label": "food", "confidence": 0.95}
        svc = AiService(http)
        cls = svc.classify("I want a burger")
        assert cls.label == "food"
        assert cls.confidence == 0.95

    def test_sentiment(self) -> None:
        http = _mock_http()
        http.post.return_value = {"sentiment": "positive", "score": 0.87}
        svc = AiService(http)
        result = svc.sentiment("Great service!")
        assert result.sentiment == "positive"

    def test_translate(self) -> None:
        http = _mock_http()
        http.post.return_value = {"translated_text": "Hola mundo"}
        svc = AiService(http)
        text = svc.translate("Hello world", "es")
        assert text == "Hola mundo"


# =========================================================================
# Pay service tests
# =========================================================================


class TestPayService:
    def test_charge(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "pay-1", "status": "succeeded", "amount": 2499}
        svc = PayService(http)
        payment = svc.charge("ord-1", 2499, "pm_visa")
        assert payment.amount == 2499
        assert payment.status == "succeeded"

    def test_refund(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "ref-1", "payment_id": "pay-1", "status": "succeeded", "amount": 500}
        svc = PayService(http)
        refund = svc.refund("pay-1", amount=500)
        assert refund.amount == 500

    def test_get_balance(self) -> None:
        http = _mock_http()
        http.get.return_value = {"available": 100000, "pending": 5000, "currency": "USD"}
        svc = PayService(http)
        balance = svc.get_balance()
        assert balance.total == 105000
        assert balance.currency == "USD"

    def test_list_payments(self) -> None:
        http = _mock_http()
        http.get.return_value = {"payments": [{"id": "p1", "status": "succeeded"}]}
        svc = PayService(http)
        payments = svc.list_payments(status="succeeded")
        assert len(payments) == 1


# =========================================================================
# Notify service tests
# =========================================================================


class TestNotifyService:
    def test_push(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = NotifyService(http)
        svc.push("u1", "Order Ready", "Your order is ready for pickup")
        http.post.assert_called_once()

    def test_sms(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = NotifyService(http)
        svc.sms("+1234567890", "Your table is ready")
        http.post.assert_called_once()

    def test_list_notifications(self) -> None:
        http = _mock_http()
        http.get.return_value = {"notifications": [{"id": "n1", "title": "Hi"}]}
        svc = NotifyService(http)
        notifs = svc.list_notifications(limit=10)
        assert len(notifs) == 1


# =========================================================================
# Events service tests
# =========================================================================


class TestEventsService:
    def test_publish(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = EventsService(http)
        svc.publish("order.created", {"order_id": "o1"})
        http.post.assert_called_once()

    def test_webhook_register(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "wh-1", "url": "https://hook.example.com", "events": ["order.created"]}
        svc = EventsService(http)
        reg = svc.webhook_register("https://hook.example.com", ["order.created"])
        assert reg.id == "wh-1"

    def test_list_webhooks(self) -> None:
        http = _mock_http()
        http.get.return_value = {"webhooks": [{"id": "wh-1", "url": "https://h.com", "events": ["*"]}]}
        svc = EventsService(http)
        hooks = svc.list_webhooks()
        assert len(hooks) == 1


# =========================================================================
# Data service tests
# =========================================================================


class TestDataService:
    def test_query(self) -> None:
        http = _mock_http()
        http.post.return_value = {"rows": [{"id": "1", "name": "test"}]}
        svc = DataService(http)
        rows = svc.query("SELECT * FROM orders")
        assert len(rows) == 1

    def test_insert(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "new-1", "name": "item"}
        svc = DataService(http)
        result = svc.insert("products", {"name": "item"})
        assert result["id"] == "new-1"

    def test_search(self) -> None:
        http = _mock_http()
        http.post.return_value = {"results": [{"id": "r1", "score": 0.9, "content": "burger recipe"}]}
        svc = DataService(http)
        results = svc.search("burger")
        assert len(results) == 1
        assert results[0].score == 0.9


# =========================================================================
# Storage service tests
# =========================================================================


class TestStorageService:
    def test_upload(self) -> None:
        http = _mock_http()
        http.post.return_value = {"url": "https://cdn.olympuscloud.ai/img.webp"}
        svc = StorageService(http)
        url = svc.upload(b"binary-data", "images/img.webp")
        assert url.startswith("https://")

    def test_presign_upload(self) -> None:
        http = _mock_http()
        http.post.return_value = {"presigned_url": "https://r2.presign/upload?sig=abc"}
        svc = StorageService(http)
        url = svc.presign_upload("images/new.webp", expires_in=7200)
        assert "presign" in url


# =========================================================================
# Marketplace service tests
# =========================================================================


class TestMarketplaceService:
    def test_list_apps(self) -> None:
        http = _mock_http()
        http.get.return_value = {
            "apps": [{"id": "app-1", "name": "Loyalty Plus", "category": "loyalty"}]
        }
        svc = MarketplaceService(http)
        apps = svc.list_apps(category="loyalty")
        assert len(apps) == 1
        assert apps[0].name == "Loyalty Plus"

    def test_install(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "inst-1", "app_id": "app-1", "status": "active"}
        svc = MarketplaceService(http)
        inst = svc.install("app-1")
        assert inst.status == "active"


# =========================================================================
# Billing service tests
# =========================================================================


class TestBillingService:
    def test_get_current_plan(self) -> None:
        http = _mock_http()
        http.get.return_value = {
            "id": "plan-blaze",
            "name": "Blaze",
            "tier": "blaze",
            "monthly_price": 9900,
        }
        svc = BillingService(http)
        plan = svc.get_current_plan()
        assert plan.name == "Blaze"
        assert plan.monthly_price == 9900

    def test_get_invoices(self) -> None:
        http = _mock_http()
        http.get.return_value = {"invoices": [{"id": "inv-1", "status": "paid", "amount": 9900}]}
        svc = BillingService(http)
        invoices = svc.get_invoices()
        assert len(invoices) == 1
        assert invoices[0].status == "paid"

    def test_get_usage(self) -> None:
        http = _mock_http()
        http.get.return_value = {"ai_credits_used": 500, "ai_credits_limit": 15000}
        svc = BillingService(http)
        usage = svc.get_usage()
        assert usage.ai_credits_used == 500
        assert usage.ai_credits_percentage == pytest.approx(500 / 15000)


# =========================================================================
# Gating service tests
# =========================================================================


class TestGatingService:
    def test_is_enabled(self) -> None:
        http = _mock_http()
        http.post.return_value = {"allowed": True}
        svc = GatingService(http)
        assert svc.is_enabled("feature.new_checkout") is True

    def test_evaluate(self) -> None:
        http = _mock_http()
        http.post.return_value = {"allowed": True, "value": 50, "reason": "plan allows"}
        svc = GatingService(http)
        result = svc.evaluate("max_orders", {"location_id": "loc-1"})
        assert result.allowed is True
        assert result.value == 50

    def test_evaluate_batch(self) -> None:
        http = _mock_http()
        http.post.return_value = {
            "results": {
                "feat_a": {"allowed": True},
                "feat_b": {"allowed": False, "reason": "plan limit"},
            }
        }
        svc = GatingService(http)
        results = svc.evaluate_batch(["feat_a", "feat_b"])
        assert results["feat_a"].allowed is True
        assert results["feat_b"].allowed is False


# =========================================================================
# Devices service tests
# =========================================================================


class TestDevicesService:
    def test_enroll(self) -> None:
        http = _mock_http()
        http.post.return_value = {"id": "dev-1", "profile": "kiosk", "status": "active"}
        svc = DevicesService(http)
        device = svc.enroll("dev-1", "kiosk")
        assert device.profile == "kiosk"

    def test_list_devices(self) -> None:
        http = _mock_http()
        http.get.return_value = {"devices": [{"id": "d1", "status": "active"}, {"id": "d2", "status": "offline"}]}
        svc = DevicesService(http)
        devices = svc.list_devices()
        assert len(devices) == 2


# =========================================================================
# Observe service tests
# =========================================================================


class TestObserveService:
    def test_log_event(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = ObserveService(http)
        svc.log_event("page_view", {"page": "/menu"})
        http.post.assert_called_once()

    def test_start_trace(self) -> None:
        http = _mock_http()
        http.post.return_value = {}
        svc = ObserveService(http)
        handle = svc.start_trace("load_menu")
        assert handle.name == "load_menu"
        assert handle.trace_id is not None
        handle.end()
        assert handle.ended_at is not None
        http.post.assert_called_once()


# =========================================================================
# Model round-trip tests
# =========================================================================


class TestModelRoundTrips:
    def test_auth_session_round_trip(self) -> None:
        data = {"access_token": "t", "token_type": "Bearer", "expires_in": 1800, "roles": ["admin"]}
        session = AuthSession.from_dict(data)
        assert session.to_dict()["access_token"] == "t"

    def test_auth_session_app_scopes_round_trip(self) -> None:
        data = {
            "access_token": "t",
            "app_scopes": ["commerce.order.read@tenant", "platform.tenant.read@tenant"],
        }
        session = AuthSession.from_dict(data)
        assert session.app_scopes == [
            "commerce.order.read@tenant",
            "platform.tenant.read@tenant",
        ]
        assert session.to_dict()["app_scopes"] == [
            "commerce.order.read@tenant",
            "platform.tenant.read@tenant",
        ]

    def test_auth_session_app_scopes_defaults_empty(self) -> None:
        data = {"access_token": "t"}
        session = AuthSession.from_dict(data)
        assert session.app_scopes == []
        # Empty scopes should NOT round-trip into the dict payload.
        assert "app_scopes" not in session.to_dict()

    def test_user_round_trip(self) -> None:
        data = {"id": "u1", "email": "a@b.com", "created_at": "2026-01-01T00:00:00"}
        user = User.from_dict(data)
        d = user.to_dict()
        assert d["id"] == "u1"
        assert "created_at" in d

    def test_order_with_items(self) -> None:
        data = {
            "id": "o1",
            "status": "pending",
            "items": [{"catalog_id": "c1", "qty": 2, "price": 999, "modifiers": [{"id": "m1", "name": "Extra cheese"}]}],
        }
        order = Order.from_dict(data)
        assert len(order.items) == 1
        assert order.items[0].modifiers[0].name == "Extra cheese"
        d = order.to_dict()
        assert len(d["items"]) == 1

    def test_catalog_item_modifiers(self) -> None:
        data = {
            "id": "c1", "name": "Burger", "price": 1299,
            "modifiers": [{"id": "m1", "name": "Size", "options": [{"id": "o1", "name": "Large", "price": 200}]}],
        }
        item = CatalogItem.from_dict(data)
        assert len(item.modifiers) == 1
        assert len(item.modifiers[0].options) == 1

    def test_payment_from_dict(self) -> None:
        data = {"payment_id": "p1", "status": "succeeded", "amount": 2499}
        payment = Payment.from_dict(data)
        assert payment.id == "p1"

    def test_balance_total(self) -> None:
        b = Balance(available=10000, pending=2000)
        assert b.total == 12000

    def test_agent_task_status_helpers(self) -> None:
        task = AgentTask(id="t1", status="completed")
        assert task.is_completed
        assert not task.is_pending
        assert not task.is_failed

    def test_agent_task_pending(self) -> None:
        task = AgentTask(id="t2", status="running")
        assert task.is_pending

    def test_usage_report_percentages(self) -> None:
        usage = UsageReport(ai_credits_used=500, ai_credits_limit=1000, voice_minutes_used=30, voice_minutes_limit=120)
        assert usage.ai_credits_percentage == 0.5
        assert usage.voice_minutes_percentage == 0.25

    def test_usage_report_zero_limits(self) -> None:
        usage = UsageReport(ai_credits_used=0, ai_credits_limit=0)
        assert usage.ai_credits_percentage == 0.0

    def test_device_is_online(self) -> None:
        now = datetime.now(tz=timezone.utc)
        device = Device(id="d1", last_seen=now)
        assert device.is_online

    def test_device_is_offline(self) -> None:
        old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        device = Device(id="d2", last_seen=old)
        assert not device.is_online

    def test_device_no_last_seen(self) -> None:
        device = Device(id="d3")
        assert not device.is_online

    def test_pagination_helpers(self) -> None:
        p = Pagination(page=2, per_page=20, total=100, total_pages=5)
        assert p.has_next_page
        assert p.has_previous_page

    def test_pagination_first_page(self) -> None:
        p = Pagination(page=1, per_page=20, total=20, total_pages=1)
        assert not p.has_next_page
        assert not p.has_previous_page

    def test_webhook_registration_round_trip(self) -> None:
        data = {"id": "wh-1", "url": "https://hook.com", "events": ["order.created"], "secret": "s3cret"}
        reg = WebhookRegistration.from_dict(data)
        d = reg.to_dict()
        assert d["secret"] == "s3cret"

    def test_marketplace_app_rating(self) -> None:
        data = {"id": "a1", "name": "App", "rating": 4.5, "install_count": 100}
        app = MarketplaceApp.from_dict(data)
        assert app.rating == 4.5

    def test_invoice_line_items(self) -> None:
        data = {
            "id": "inv-1",
            "line_items": [{"description": "Blaze Plan", "amount": 9900, "quantity": 1}],
        }
        inv = Invoice.from_dict(data)
        assert len(inv.line_items) == 1
        assert inv.line_items[0].description == "Blaze Plan"

    def test_trace_handle_lifecycle(self) -> None:
        called = []

        def on_end(handle: TraceHandle, duration_ms: float) -> None:
            called.append(duration_ms)

        handle = TraceHandle(name="test", trace_id="t1", started_at=datetime.now(), on_end=on_end)
        assert handle.ended_at is None
        handle.end()
        assert handle.ended_at is not None
        assert len(called) == 1
        assert called[0] >= 0

    def test_sentiment_with_aspects(self) -> None:
        data = {
            "sentiment": "mixed",
            "score": 0.5,
            "aspects": [
                {"aspect": "food", "sentiment": "positive", "score": 0.9},
                {"aspect": "service", "sentiment": "negative", "score": 0.2},
            ],
        }
        result = SentimentResult.from_dict(data)
        assert len(result.aspects) == 2
        assert result.aspects[0].aspect == "food"

    def test_plan_features(self) -> None:
        data = {"id": "p1", "name": "Inferno", "features": ["ai_agents", "voice", "unlimited_locations"]}
        plan = Plan.from_dict(data)
        assert "voice" in plan.features

    def test_terminal_reader_from_dict(self) -> None:
        data = {"id": "tmr_123", "device_type": "bbpos_wisepos_e", "status": "online", "location": "tml_loc_1"}
        reader = TerminalReader.from_dict(data)
        assert reader.location_id == "tml_loc_1"
