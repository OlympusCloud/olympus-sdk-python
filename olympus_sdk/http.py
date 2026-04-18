"""Internal HTTP client with auth interceptor and error handling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import httpx

from olympus_sdk.errors import (
    BillingGraceExceeded,
    ConsentRequired,
    DeviceChanged,
    OlympusApiError,
    OlympusNetworkError,
    ScopeDenied,
)

if TYPE_CHECKING:
    from olympus_sdk.config import OlympusConfig

_SDK_VERSION = "python/0.1.0"

StaleCatalogHandler = Callable[[], None]


class OlympusHttpClient:
    """Low-level HTTP transport for all SDK service calls.

    Automatically attaches authentication headers (Bearer token or API key)
    and translates HTTP / network errors into SDK exception types.
    """

    def __init__(self, config: OlympusConfig) -> None:
        self._config = config
        self._access_token: str | None = None
        self._app_token: str | None = None
        self._on_stale_catalog: StaleCatalogHandler | None = None
        self._client = httpx.Client(
            base_url=config.resolved_base_url,
            timeout=httpx.Timeout(config.timeout),
            headers={
                "X-App-Id": config.app_id,
                "X-SDK-Version": _SDK_VERSION,
            },
            event_hooks={
                "request": [self._inject_auth],
                "response": [self._raise_on_error, self._check_stale_catalog],
            },
        )

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def set_access_token(self, token: str) -> None:
        """Set the Bearer token for user-scoped requests."""
        self._access_token = token

    def clear_access_token(self) -> None:
        """Clear the access token, reverting to API-key auth."""
        self._access_token = None

    def set_app_token(self, token: str) -> None:
        """Set the App JWT (X-App-Token per §4.5 dual-JWT flow)."""
        self._app_token = token

    def clear_app_token(self) -> None:
        """Clear the app token."""
        self._app_token = None

    def get_access_token(self) -> str | None:
        """Internal — used by OlympusClient to decode JWT bitset."""
        return self._access_token

    def on_catalog_stale(self, handler: StaleCatalogHandler | None) -> None:
        """Register a handler for ``X-Olympus-Catalog-Stale: true`` (§4.7)."""
        self._on_stale_catalog = handler

    # ------------------------------------------------------------------
    # Public HTTP verbs
    # ------------------------------------------------------------------

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GET request and return the parsed JSON body."""
        return self._request("GET", path, params=params)

    def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a POST request and return the parsed JSON body."""
        return self._request("POST", path, json=json, params=params)

    def put(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a PUT request and return the parsed JSON body."""
        return self._request("PUT", path, json=json)

    def patch(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a PATCH request and return the parsed JSON body."""
        return self._request("PATCH", path, json=json)

    def delete(self, path: str) -> None:
        """Execute a DELETE request."""
        self._request("DELETE", path)

    def stream_post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Execute a streaming POST and return the raw httpx.Response.

        The caller is responsible for iterating the response stream and
        closing the response.
        """
        try:
            return self._client.stream(
                "POST",
                path,
                json=json,
            ).__enter__()
        except httpx.HTTPError as exc:
            raise OlympusNetworkError(str(exc), cause=exc) from exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _inject_auth(self, request: httpx.Request) -> None:
        """Event hook: attach Bearer token + X-App-Token to every request."""
        token = self._access_token or self._config.api_key
        request.headers["Authorization"] = f"Bearer {token}"
        if self._app_token is not None:
            request.headers["X-App-Token"] = self._app_token

    def _check_stale_catalog(self, response: httpx.Response) -> None:
        """Event hook: fire stale-catalog handler on successful responses."""
        if response.is_success and response.headers.get("X-Olympus-Catalog-Stale") == "true":
            handler = self._on_stale_catalog
            if handler is not None:
                try:
                    handler()
                except Exception:  # noqa: BLE001
                    pass

    @staticmethod
    def _raise_on_error(response: httpx.Response) -> None:
        """Event hook: raise typed error on 4xx/5xx responses."""
        if response.is_success:
            return
        try:
            body = response.json()
        except Exception:  # noqa: BLE001
            body = {}

        error_body = body.get("error") if isinstance(body, dict) else None
        code = ""
        message = f"HTTP {response.status_code}"
        request_id: str | None = None

        if isinstance(error_body, dict):
            code = str(error_body.get("code") or "")
            message = str(error_body.get("message") or message)
            request_id = error_body.get("request_id")

        def _extract(key: str) -> str | None:
            if isinstance(error_body, dict):
                v = error_body.get(key)
                if isinstance(v, str):
                    return v
            if isinstance(body, dict):
                v = body.get(key)
                if isinstance(v, str):
                    return v
            return None

        # Route recognized app-scoped error codes to typed subclasses.
        normalized = code.lower()
        if normalized in ("scope_not_granted", "consent_required"):
            raise ConsentRequired(
                scope=_extract("scope") or "unknown",
                consent_url=(
                    _extract("consent_url")
                    or response.headers.get("X-Olympus-Consent-URL")
                ),
                message=message,
                status_code=response.status_code,
                request_id=request_id,
            )
        if normalized == "scope_denied":
            raise ScopeDenied(
                scope=_extract("scope") or "unknown",
                message=message,
                status_code=response.status_code,
                request_id=request_id,
            )
        if normalized == "billing_grace_exceeded":
            raise BillingGraceExceeded(
                message=message,
                status_code=response.status_code,
                request_id=request_id,
                grace_until=(
                    _extract("grace_until")
                    or response.headers.get("X-Olympus-Grace-Until")
                ),
                upgrade_url=(
                    _extract("upgrade_url")
                    or response.headers.get("X-Olympus-Upgrade-URL")
                ),
            )
        if normalized in ("webauthn_required", "device_changed"):
            raise DeviceChanged(
                challenge=_extract("challenge") or "",
                requires_reconsent=bool(
                    body.get("requires_reconsent") if isinstance(body, dict) else False
                ),
                message=message,
                status_code=response.status_code,
                request_id=request_id,
            )

        if code:
            raise OlympusApiError(
                code=code,
                message=message,
                status_code=response.status_code,
                request_id=request_id,
            )
        raise OlympusApiError(
            code="HTTP_ERROR",
            message=response.text[:500] if response.text else message,
            status_code=response.status_code,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request with unified error handling."""
        # Strip None values from query params
        cleaned_params: dict[str, Any] | None = None
        if params:
            cleaned_params = {k: v for k, v in params.items() if v is not None}
            if not cleaned_params:
                cleaned_params = None

        try:
            response = self._client.request(
                method,
                path,
                json=json,
                params=cleaned_params,
            )
        except OlympusApiError:
            raise
        except httpx.HTTPError as exc:
            raise OlympusNetworkError(str(exc), cause=exc) from exc

        if method == "DELETE" and response.status_code in (204, 200):
            return {}

        try:
            return response.json()  # type: ignore[no-any-return]
        except Exception:
            return {}

    def close(self) -> None:
        """Close the underlying HTTP transport."""
        self._client.close()
