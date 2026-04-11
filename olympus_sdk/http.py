"""Internal HTTP client with auth interceptor and error handling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from olympus_sdk.errors import OlympusApiError, OlympusNetworkError

if TYPE_CHECKING:
    from olympus_sdk.config import OlympusConfig

_SDK_VERSION = "python/0.1.0"


class OlympusHttpClient:
    """Low-level HTTP transport for all SDK service calls.

    Automatically attaches authentication headers (Bearer token or API key)
    and translates HTTP / network errors into SDK exception types.
    """

    def __init__(self, config: OlympusConfig) -> None:
        self._config = config
        self._access_token: str | None = None
        self._client = httpx.Client(
            base_url=config.resolved_base_url,
            timeout=httpx.Timeout(config.timeout),
            headers={
                "X-App-Id": config.app_id,
                "X-SDK-Version": _SDK_VERSION,
            },
            event_hooks={
                "request": [self._inject_auth],
                "response": [self._raise_on_error],
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
        """Event hook: attach Bearer token or API key to every request."""
        token = self._access_token or self._config.api_key
        request.headers["Authorization"] = f"Bearer {token}"

    @staticmethod
    def _raise_on_error(response: httpx.Response) -> None:
        """Event hook: raise :class:`OlympusApiError` on 4xx/5xx responses."""
        if response.is_success:
            return
        try:
            body = response.json()
        except Exception:
            body = {}

        error_body = body.get("error") if isinstance(body, dict) else None
        if isinstance(error_body, dict):
            raise OlympusApiError(
                code=error_body.get("code", "UNKNOWN"),
                message=error_body.get("message", "Unknown error"),
                status_code=response.status_code,
                request_id=error_body.get("request_id"),
            )
        raise OlympusApiError(
            code="HTTP_ERROR",
            message=response.text[:500] if response.text else f"HTTP {response.status_code}",
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
