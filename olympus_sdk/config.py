"""SDK configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OlympusEnvironment(Enum):
    """Target environment for the SDK."""

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    SANDBOX = "sandbox"


_BASE_URLS: dict[OlympusEnvironment, str] = {
    OlympusEnvironment.PRODUCTION: "https://api.olympuscloud.ai/api/v1",
    OlympusEnvironment.STAGING: "https://staging.api.olympuscloud.ai/api/v1",
    OlympusEnvironment.DEVELOPMENT: "https://dev.api.olympuscloud.ai/api/v1",
    OlympusEnvironment.SANDBOX: "https://sandbox.api.olympuscloud.ai/api/v1",
}


@dataclass(frozen=True)
class OlympusConfig:
    """Configuration for the Olympus Cloud SDK.

    Parameters:
        app_id: Your application's unique identifier (e.g. ``com.restaurant-revolution``).
        api_key: API key for authentication.
        base_url: Override the default API base URL. When *None* the URL is
            derived from *environment*.
        timeout: Request timeout in seconds.
        environment: Target environment (production, staging, development, sandbox).
    """

    app_id: str
    api_key: str
    base_url: str | None = None
    timeout: float = 30.0
    environment: OlympusEnvironment = field(default=OlympusEnvironment.PRODUCTION)

    @property
    def resolved_base_url(self) -> str:
        """Return the effective base URL, accounting for overrides."""
        if self.base_url is not None:
            return self.base_url.rstrip("/")
        return _BASE_URLS[self.environment]

    @staticmethod
    def sandbox(*, app_id: str, api_key: str) -> OlympusConfig:
        """Create a sandbox configuration for testing."""
        return OlympusConfig(
            app_id=app_id,
            api_key=api_key,
            environment=OlympusEnvironment.SANDBOX,
        )

    @staticmethod
    def dev(*, app_id: str, api_key: str) -> OlympusConfig:
        """Create a development configuration."""
        return OlympusConfig(
            app_id=app_id,
            api_key=api_key,
            environment=OlympusEnvironment.DEVELOPMENT,
        )
