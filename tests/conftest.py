"""Shared test fixtures for the Olympus Python SDK."""

from __future__ import annotations

import httpx
import pytest

from olympus_sdk import OlympusClient
from olympus_sdk.config import OlympusConfig
from olympus_sdk.http import OlympusHttpClient


@pytest.fixture()
def config() -> OlympusConfig:
    return OlympusConfig(app_id="com.test-app", api_key="oc_test_key_123")


@pytest.fixture()
def http_client(config: OlympusConfig) -> OlympusHttpClient:
    return OlympusHttpClient(config)


@pytest.fixture()
def client(config: OlympusConfig) -> OlympusClient:
    return OlympusClient(app_id=config.app_id, api_key=config.api_key, config=config)


def mock_response(
    json: dict | list | None = None,
    status_code: int = 200,
) -> httpx.Response:
    """Create a mock httpx.Response for testing."""
    return httpx.Response(
        status_code=status_code,
        json=json or {},
        request=httpx.Request("GET", "https://test.olympuscloud.ai/api/v1/test"),
    )
