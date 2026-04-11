"""Olympus Cloud Python SDK.

Official Python client for the Olympus Cloud Platform API.

Usage::

    from olympus_sdk import OlympusClient

    client = OlympusClient(app_id="com.my-restaurant", api_key="oc_live_...")

    # Authenticate
    session = client.auth.login("user@example.com", "password")

    # Create an order
    order = client.commerce.create_order(
        items=[{"catalog_id": "burger-01", "qty": 2, "price": 1299}],
        source="pos",
    )

    # Ask AI
    answer = client.ai.query("What sold best this week?")
"""

from olympus_sdk.client import OlympusClient
from olympus_sdk.config import OlympusConfig, OlympusEnvironment
from olympus_sdk.errors import OlympusApiError, OlympusNetworkError

__all__ = [
    "OlympusClient",
    "OlympusConfig",
    "OlympusEnvironment",
    "OlympusApiError",
    "OlympusNetworkError",
]

__version__ = "0.1.0"
