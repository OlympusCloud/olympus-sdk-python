"""Tests for OlympusClient, OlympusConfig, OlympusHttpClient, and error types."""

from __future__ import annotations

import httpx
import pytest

from olympus_sdk import OlympusApiError, OlympusClient, OlympusConfig, OlympusNetworkError
from olympus_sdk.config import OlympusEnvironment
from olympus_sdk.http import OlympusHttpClient
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

# -------------------------------------------------------------------------
# Config tests
# -------------------------------------------------------------------------


class TestOlympusConfig:
    def test_default_production_url(self) -> None:
        cfg = OlympusConfig(app_id="app", api_key="key")
        assert cfg.resolved_base_url == "https://api.olympuscloud.ai/api/v1"
        assert cfg.environment == OlympusEnvironment.PRODUCTION

    def test_dev_factory(self) -> None:
        cfg = OlympusConfig.dev(app_id="app", api_key="key")
        assert cfg.environment == OlympusEnvironment.DEVELOPMENT
        assert "dev.api" in cfg.resolved_base_url

    def test_sandbox_factory(self) -> None:
        cfg = OlympusConfig.sandbox(app_id="app", api_key="key")
        assert cfg.environment == OlympusEnvironment.SANDBOX
        assert "sandbox.api" in cfg.resolved_base_url

    def test_custom_base_url_override(self) -> None:
        cfg = OlympusConfig(app_id="a", api_key="k", base_url="https://custom.api/v1/")
        assert cfg.resolved_base_url == "https://custom.api/v1"

    def test_staging_url(self) -> None:
        cfg = OlympusConfig(app_id="a", api_key="k", environment=OlympusEnvironment.STAGING)
        assert "staging.api" in cfg.resolved_base_url

    def test_timeout_default(self) -> None:
        cfg = OlympusConfig(app_id="a", api_key="k")
        assert cfg.timeout == 30.0

    def test_frozen_config(self) -> None:
        cfg = OlympusConfig(app_id="a", api_key="k")
        with pytest.raises(AttributeError):
            cfg.app_id = "b"  # type: ignore[misc]


# -------------------------------------------------------------------------
# Client tests
# -------------------------------------------------------------------------


class TestOlympusClient:
    def test_service_accessor_types(self, client: OlympusClient) -> None:
        assert isinstance(client.auth, AuthService)
        assert isinstance(client.commerce, CommerceService)
        assert isinstance(client.ai, AiService)
        assert isinstance(client.pay, PayService)
        assert isinstance(client.notify, NotifyService)
        assert isinstance(client.events, EventsService)
        assert isinstance(client.data, DataService)
        assert isinstance(client.storage, StorageService)
        assert isinstance(client.marketplace, MarketplaceService)
        assert isinstance(client.billing, BillingService)
        assert isinstance(client.gating, GatingService)
        assert isinstance(client.devices, DevicesService)
        assert isinstance(client.observe, ObserveService)

    def test_lazy_singleton_initialization(self, client: OlympusClient) -> None:
        auth1 = client.auth
        auth2 = client.auth
        assert auth1 is auth2

    def test_all_13_services_are_singletons(self, client: OlympusClient) -> None:
        services = [
            "auth", "commerce", "ai", "pay", "notify", "events",
            "data", "storage", "marketplace", "billing", "gating",
            "devices", "observe",
        ]
        for name in services:
            svc1 = getattr(client, name)
            svc2 = getattr(client, name)
            assert svc1 is svc2, f"{name} is not singleton"

    def test_from_config(self) -> None:
        cfg = OlympusConfig.sandbox(app_id="test", api_key="key")
        client = OlympusClient.from_config(cfg)
        assert client.config.environment == OlympusEnvironment.SANDBOX

    def test_config_accessor(self, client: OlympusClient) -> None:
        assert client.config.app_id == "com.test-app"

    def test_http_client_accessor(self, client: OlympusClient) -> None:
        assert isinstance(client.http_client, OlympusHttpClient)

    def test_context_manager(self) -> None:
        with OlympusClient(app_id="a", api_key="k") as client:
            assert isinstance(client.auth, AuthService)


# -------------------------------------------------------------------------
# HTTP client tests
# -------------------------------------------------------------------------


class TestOlympusHttpClient:
    def test_auth_header_with_api_key(self, http_client: OlympusHttpClient) -> None:
        request = httpx.Request("GET", "https://test.olympuscloud.ai/api/v1/test")
        http_client._inject_auth(request)
        assert request.headers["Authorization"] == "Bearer oc_test_key_123"

    def test_auth_header_with_access_token(self, http_client: OlympusHttpClient) -> None:
        http_client.set_access_token("user_token_abc")
        request = httpx.Request("GET", "https://test.olympuscloud.ai/api/v1/test")
        http_client._inject_auth(request)
        assert request.headers["Authorization"] == "Bearer user_token_abc"

    def test_clear_access_token(self, http_client: OlympusHttpClient) -> None:
        http_client.set_access_token("token")
        http_client.clear_access_token()
        request = httpx.Request("GET", "https://test.olympuscloud.ai/api/v1/test")
        http_client._inject_auth(request)
        assert request.headers["Authorization"] == "Bearer oc_test_key_123"

    def test_raise_on_error_structured(self) -> None:
        response = httpx.Response(
            status_code=400,
            json={"error": {"code": "INVALID_INPUT", "message": "Bad request"}},
            request=httpx.Request("POST", "https://test.olympuscloud.ai/api/v1/test"),
        )
        with pytest.raises(OlympusApiError) as exc_info:
            OlympusHttpClient._raise_on_error(response)
        assert exc_info.value.code == "INVALID_INPUT"
        assert exc_info.value.message == "Bad request"
        assert exc_info.value.status_code == 400

    def test_raise_on_error_unstructured(self) -> None:
        response = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("GET", "https://test.olympuscloud.ai/api/v1/test"),
        )
        with pytest.raises(OlympusApiError) as exc_info:
            OlympusHttpClient._raise_on_error(response)
        assert exc_info.value.code == "HTTP_ERROR"
        assert exc_info.value.status_code == 500

    def test_raise_on_error_success_noop(self) -> None:
        response = httpx.Response(
            status_code=200,
            json={"data": "ok"},
            request=httpx.Request("GET", "https://test.olympuscloud.ai/api/v1/test"),
        )
        OlympusHttpClient._raise_on_error(response)  # Should not raise


# -------------------------------------------------------------------------
# Error type tests
# -------------------------------------------------------------------------


class TestErrors:
    def test_api_error_str(self) -> None:
        err = OlympusApiError(code="NOT_FOUND", message="Resource not found", status_code=404)
        assert "NOT_FOUND" in str(err)
        assert "404" in str(err)

    def test_api_error_repr(self) -> None:
        err = OlympusApiError(
            code="FORBIDDEN",
            message="Access denied",
            status_code=403,
            request_id="req-123",
        )
        rep = repr(err)
        assert "FORBIDDEN" in rep
        assert "req-123" in rep

    def test_network_error_str(self) -> None:
        err = OlympusNetworkError("Connection refused", cause=ConnectionError("refused"))
        assert "Connection refused" in str(err)

    def test_network_error_cause(self) -> None:
        cause = TimeoutError("timed out")
        err = OlympusNetworkError("Timeout", cause=cause)
        assert err.cause is cause

    def test_network_error_repr(self) -> None:
        err = OlympusNetworkError("DNS failure", cause=None)
        assert "DNS failure" in repr(err)
