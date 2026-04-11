"""Developer tools: API keys, devboxes, and deployments.

Wraps the Olympus Developer platform via the Go API Gateway.
Routes: ``/developer/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class DeveloperService:
    """Developer tools: API keys, devboxes, and application deployments."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # API Keys
    # ------------------------------------------------------------------

    async def create_api_key(
        self,
        *,
        name: str,
        scopes: list[str] | None = None,
        expires_in_days: int | None = None,
    ) -> dict:
        """Create a new API key for programmatic access."""
        payload: dict[str, Any] = {"name": name}
        if scopes is not None:
            payload["scopes"] = scopes
        if expires_in_days is not None:
            payload["expires_in_days"] = expires_in_days
        return self._http.post("/developer/api-keys", json=payload)

    async def list_api_keys(self) -> dict:
        """List all API keys for the current tenant."""
        return self._http.get("/developer/api-keys")

    async def revoke_api_key(self, key_id: str) -> dict:
        """Revoke an API key by ID."""
        self._http.delete(f"/developer/api-keys/{key_id}")
        return {}

    async def rotate_api_key(self, key_id: str) -> dict:
        """Rotate an API key, generating a new secret while preserving the key ID."""
        return self._http.post(f"/developer/api-keys/{key_id}/rotate")

    # ------------------------------------------------------------------
    # Devboxes
    # ------------------------------------------------------------------

    async def provision_devbox(
        self,
        *,
        name: str,
        template: str | None = None,
    ) -> dict:
        """Provision a new cloud development environment (devbox)."""
        payload: dict[str, Any] = {"name": name}
        if template is not None:
            payload["template"] = template
        return self._http.post("/developer/devboxes", json=payload)

    async def get_devbox_session(self, devbox_id: str) -> dict:
        """Get the active session details for a devbox."""
        return self._http.get(f"/developer/devboxes/{devbox_id}/session")

    # ------------------------------------------------------------------
    # Deployments
    # ------------------------------------------------------------------

    async def deploy_app(
        self,
        *,
        app_id: str,
        version: str,
        environment: str | None = None,
    ) -> dict:
        """Deploy an application to the specified environment."""
        payload: dict[str, Any] = {"app_id": app_id, "version": version}
        if environment is not None:
            payload["environment"] = environment
        return self._http.post("/developer/deployments", json=payload)

    async def promote_deployment(
        self,
        deployment_id: str,
        *,
        target_environment: str,
    ) -> dict:
        """Promote a deployment to a higher environment (e.g. staging to prod)."""
        return self._http.post(
            f"/developer/deployments/{deployment_id}/promote",
            json={"target_environment": target_environment},
        )

    async def rollback_deployment(
        self,
        deployment_id: str,
        *,
        target_version: str | None = None,
    ) -> dict:
        """Rollback a deployment to a previous version."""
        payload: dict[str, Any] = {}
        if target_version is not None:
            payload["target_version"] = target_version
        return self._http.post(
            f"/developer/deployments/{deployment_id}/rollback",
            json=payload,
        )
