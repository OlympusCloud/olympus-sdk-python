"""Tests for :class:`AppsService` — canonical ``/apps/*`` surface
(olympus-cloud-gcp#3413 §3 / PR #3422).

Uses ``httpx.MockTransport`` so the assertions cover the actual wire shape
(method / path / serialized JSON body). MockTransport exercises the SDK's
real request-injection + error-translation pipeline end-to-end, which
catches model / serialization drift a ``MagicMock`` of the HTTP client
would miss.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from olympus_sdk import (
    AppInstall,
    AppManifest,
    AppsService,
    OlympusApiError,
    PendingInstall,
    PendingInstallDetail,
)
from olympus_sdk.config import OlympusConfig
from olympus_sdk.http import OlympusHttpClient

if TYPE_CHECKING:
    from collections.abc import Callable


# ---------------------------------------------------------------------------
# MockTransport helpers
# ---------------------------------------------------------------------------


def _make_http(
    handler: Callable[[httpx.Request], httpx.Response],
) -> OlympusHttpClient:
    """Build an :class:`OlympusHttpClient` wired to an ``httpx.MockTransport``.

    The returned client is fully functional — event hooks run, auth headers
    inject, error translation fires — but every request is intercepted by
    ``handler`` so no real network traffic is made.
    """
    config = OlympusConfig(
        app_id="com.test-app",
        api_key="oc_test_key_123",
        base_url="https://test.invalid/api/v1",
    )
    client = OlympusHttpClient(config)
    # Swap in the mock transport while keeping the original base URL / headers.
    client._client = httpx.Client(  # type: ignore[attr-defined]  # noqa: SLF001
        base_url=config.resolved_base_url,
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(config.timeout),
        headers=dict(client._client.headers),  # noqa: SLF001
        event_hooks={
            "request": [client._inject_auth],  # noqa: SLF001
            "response": [client._raise_on_error, client._check_stale_catalog],  # noqa: SLF001
        },
    )
    return client


def _json_response(
    request: httpx.Request,
    payload: Any,
    status_code: int = 200,
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        request=request,
    )


def _error_response(
    request: httpx.Request,
    *,
    code: str,
    message: str,
    status_code: int,
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(
            {"error": {"code": code, "message": message, "request_id": "req-123"}}
        ).encode("utf-8"),
        headers={"content-type": "application/json"},
        request=request,
    )


def _install_fixture(
    *,
    tenant_id: str = "ten-abc",
    app_id: str = "com.pizzaos",
    installed_by: str = "usr-admin",
    status: str = "active",
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "app_id": app_id,
        "installed_at": "2026-04-21T15:00:00Z",
        "installed_by": installed_by,
        "scopes_granted": scopes
        if scopes is not None
        else ["pizza.menu.read@tenant", "pizza.orders.write@tenant"],
        "status": status,
    }


def _manifest_fixture(
    *,
    app_id: str = "com.pizzaos",
    version: str = "1.0.0",
) -> dict[str, Any]:
    return {
        "app_id": app_id,
        "version": version,
        "name": "PizzaOS",
        "publisher": "NebusAI",
        "logo_url": f"https://cdn.olympuscloud.ai/apps/{app_id}/logo.png",
        "scopes_required": [
            "pizza.menu.read@tenant",
            "pizza.orders.write@tenant",
        ],
        "scopes_optional": ["pizza.analytics.read@tenant"],
        "privacy_url": "https://pizzaos.com/privacy",
        "tos_url": "https://pizzaos.com/tos",
    }


# ===========================================================================
# install
# ===========================================================================


class TestInstall:
    def test_posts_full_body_and_parses_response(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["body"] = json.loads(request.content.decode("utf-8"))
            return _json_response(
                request,
                {
                    "pending_install_id": "pend-uuid-1",
                    "consent_url": (
                        "https://platform.olympuscloud.ai/apps/consent/pend-uuid-1"
                    ),
                    "expires_at": "2026-04-21T15:10:00Z",
                },
                status_code=201,
            )

        http = _make_http(handler)
        try:
            result = AppsService(http).install(
                app_id="com.pizzaos",
                scopes=["pizza.menu.read@tenant", "pizza.orders.write@tenant"],
                return_to="https://pizzaos.com/settings/permissions",
                idempotency_key="device-fingerprint-abc",
            )
        finally:
            http.close()

        assert captured["method"] == "POST"
        assert captured["path"] == "/api/v1/apps/install"
        assert captured["body"] == {
            "app_id": "com.pizzaos",
            "scopes": [
                "pizza.menu.read@tenant",
                "pizza.orders.write@tenant",
            ],
            "return_to": "https://pizzaos.com/settings/permissions",
            "idempotency_key": "device-fingerprint-abc",
        }

        assert isinstance(result, PendingInstall)
        assert result.pending_install_id == "pend-uuid-1"
        assert (
            result.consent_url
            == "https://platform.olympuscloud.ai/apps/consent/pend-uuid-1"
        )
        assert result.expires_at == "2026-04-21T15:10:00Z"
        # raw preserves every response field for forward-compat consumers.
        assert result.raw["pending_install_id"] == "pend-uuid-1"

    def test_omits_idempotency_key_when_not_provided(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content.decode("utf-8"))
            return _json_response(
                request,
                {
                    "pending_install_id": "pend-uuid-2",
                    "consent_url": (
                        "https://platform.olympuscloud.ai/apps/consent/pend-uuid-2"
                    ),
                    "expires_at": "2026-04-21T15:10:00Z",
                },
                status_code=201,
            )

        http = _make_http(handler)
        try:
            AppsService(http).install(
                app_id="com.pizzaos",
                scopes=[],
                return_to="https://pizzaos.com/cb",
            )
        finally:
            http.close()

        assert "idempotency_key" not in captured["body"]
        assert captured["body"]["scopes"] == []

    def test_surfaces_mfa_required_403_as_api_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _error_response(
                request,
                code="mfa_required",
                message="mfa_required",
                status_code=403,
            )

        http = _make_http(handler)
        try:
            with pytest.raises(OlympusApiError) as exc:
                AppsService(http).install(
                    app_id="com.pizzaos",
                    scopes=[],
                    return_to="https://pizzaos.com/cb",
                )
        finally:
            http.close()
        assert exc.value.status_code == 403
        assert exc.value.code == "mfa_required"


# ===========================================================================
# list_installed
# ===========================================================================


class TestListInstalled:
    def test_gets_installed_and_parses_list(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            return _json_response(
                request,
                [
                    _install_fixture(),
                    _install_fixture(app_id="com.barOS", installed_by="usr-2"),
                ],
            )

        http = _make_http(handler)
        try:
            installs = AppsService(http).list_installed()
        finally:
            http.close()

        assert captured["method"] == "GET"
        assert captured["path"] == "/api/v1/apps/installed"

        assert len(installs) == 2
        assert all(isinstance(i, AppInstall) for i in installs)
        assert installs[0].app_id == "com.pizzaos"
        assert installs[0].tenant_id == "ten-abc"
        assert installs[0].installed_by == "usr-admin"
        assert installs[0].scopes_granted == [
            "pizza.menu.read@tenant",
            "pizza.orders.write@tenant",
        ]
        assert installs[0].status == "active"
        assert installs[1].app_id == "com.barOS"
        assert installs[1].installed_by == "usr-2"

    def test_parses_envelope_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(request, {"installs": [_install_fixture()]})

        http = _make_http(handler)
        try:
            installs = AppsService(http).list_installed()
        finally:
            http.close()
        assert len(installs) == 1
        assert installs[0].app_id == "com.pizzaos"

    def test_returns_empty_list_when_body_unexpected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(request, {})

        http = _make_http(handler)
        try:
            assert AppsService(http).list_installed() == []
        finally:
            http.close()


# ===========================================================================
# uninstall
# ===========================================================================


class TestUninstall:
    def test_posts_uninstall_with_escaped_app_id(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["body"] = request.content
            return _json_response(request, {}, status_code=204)

        http = _make_http(handler)
        try:
            AppsService(http).uninstall("com.pizzaos")
        finally:
            http.close()
        assert captured["method"] == "POST"
        assert captured["path"] == "/api/v1/apps/uninstall/com.pizzaos"
        # No JSON body on uninstall — signal is the path alone.
        assert captured["body"] in (b"", b"null")

    def test_escapes_path_unsafe_chars_in_app_id(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            # ``raw_path`` preserves percent-encoding; ``path`` is the
            # decoded form. We care about the former — the server routes
            # on the raw bytes.
            captured["raw_path"] = request.url.raw_path
            return _json_response(request, {})

        http = _make_http(handler)
        try:
            AppsService(http).uninstall("weird/id with space")
        finally:
            http.close()
        # '/' and ' ' must be percent-escaped so they stay in the single
        # path segment the server routes on.
        assert captured["raw_path"] == (
            b"/api/v1/apps/uninstall/weird%2Fid%20with%20space"
        )

    def test_propagates_404_when_app_not_installed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _error_response(
                request,
                code="not_found",
                message="app not installed on tenant",
                status_code=404,
            )

        http = _make_http(handler)
        try:
            with pytest.raises(OlympusApiError) as exc:
                AppsService(http).uninstall("com.pizzaos")
        finally:
            http.close()
        assert exc.value.status_code == 404


# ===========================================================================
# get_manifest
# ===========================================================================


class TestGetManifest:
    def test_gets_manifest_and_parses_fields(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            return _json_response(request, _manifest_fixture())

        http = _make_http(handler)
        try:
            manifest = AppsService(http).get_manifest("com.pizzaos")
        finally:
            http.close()

        assert captured["method"] == "GET"
        assert captured["path"] == "/api/v1/apps/manifest/com.pizzaos"

        assert isinstance(manifest, AppManifest)
        assert manifest.app_id == "com.pizzaos"
        assert manifest.version == "1.0.0"
        assert manifest.name == "PizzaOS"
        assert manifest.publisher == "NebusAI"
        assert manifest.scopes_required == [
            "pizza.menu.read@tenant",
            "pizza.orders.write@tenant",
        ]
        assert manifest.scopes_optional == ["pizza.analytics.read@tenant"]
        assert manifest.logo_url == (
            "https://cdn.olympuscloud.ai/apps/com.pizzaos/logo.png"
        )
        assert manifest.privacy_url == "https://pizzaos.com/privacy"
        assert manifest.tos_url == "https://pizzaos.com/tos"

    def test_propagates_404_when_manifest_missing(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _error_response(
                request,
                code="not_found",
                message="manifest not found",
                status_code=404,
            )

        http = _make_http(handler)
        try:
            with pytest.raises(OlympusApiError) as exc:
                AppsService(http).get_manifest("com.unknown")
        finally:
            http.close()
        assert exc.value.status_code == 404


# ===========================================================================
# get_pending_install — anonymous
# ===========================================================================


class TestGetPendingInstall:
    def test_gets_pending_and_eager_loads_manifest(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            return _json_response(
                request,
                {
                    "id": "pend-uuid-1",
                    "app_id": "com.pizzaos",
                    "tenant_id": "ten-abc",
                    "requested_scopes": [
                        "pizza.menu.read@tenant",
                        "pizza.orders.write@tenant",
                    ],
                    "return_to": "https://pizzaos.com/settings/permissions",
                    "status": "pending",
                    "expires_at": "2026-04-21T15:10:00Z",
                    "manifest": _manifest_fixture(),
                },
            )

        http = _make_http(handler)
        try:
            detail = AppsService(http).get_pending_install("pend-uuid-1")
        finally:
            http.close()

        assert captured["method"] == "GET"
        assert captured["path"] == "/api/v1/apps/pending_install/pend-uuid-1"

        assert isinstance(detail, PendingInstallDetail)
        assert detail.id == "pend-uuid-1"
        assert detail.app_id == "com.pizzaos"
        assert detail.tenant_id == "ten-abc"
        assert detail.status == "pending"
        assert detail.requested_scopes == [
            "pizza.menu.read@tenant",
            "pizza.orders.write@tenant",
        ]
        assert detail.return_to == "https://pizzaos.com/settings/permissions"
        assert detail.manifest is not None
        assert detail.manifest.app_id == "com.pizzaos"
        assert detail.manifest.scopes_required == [
            "pizza.menu.read@tenant",
            "pizza.orders.write@tenant",
        ]

    def test_parses_detail_when_manifest_missing(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(
                request,
                {
                    "id": "pend-uuid-2",
                    "app_id": "com.pizzaos",
                    "tenant_id": "ten-abc",
                    "requested_scopes": [],
                    "return_to": "https://pizzaos.com/cb",
                    "status": "approved",
                    "expires_at": "2026-04-21T15:10:00Z",
                },
            )

        http = _make_http(handler)
        try:
            detail = AppsService(http).get_pending_install("pend-uuid-2")
        finally:
            http.close()
        assert detail.manifest is None
        assert detail.status == "approved"

    def test_surfaces_410_gone_when_expired(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _error_response(
                request,
                code="gone",
                message="pending install expired",
                status_code=410,
            )

        http = _make_http(handler)
        try:
            with pytest.raises(OlympusApiError) as exc:
                AppsService(http).get_pending_install("pend-uuid-expired")
        finally:
            http.close()
        assert exc.value.status_code == 410


# ===========================================================================
# approve_pending_install
# ===========================================================================


class TestApprovePendingInstall:
    def test_posts_approve_and_parses_install_record(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            return _json_response(request, _install_fixture())

        http = _make_http(handler)
        try:
            install = AppsService(http).approve_pending_install("pend-uuid-1")
        finally:
            http.close()

        assert captured["method"] == "POST"
        assert captured["path"] == (
            "/api/v1/apps/pending_install/pend-uuid-1/approve"
        )

        assert isinstance(install, AppInstall)
        assert install.tenant_id == "ten-abc"
        assert install.app_id == "com.pizzaos"
        assert install.installed_by == "usr-admin"
        assert install.status == "active"
        assert install.scopes_granted == [
            "pizza.menu.read@tenant",
            "pizza.orders.write@tenant",
        ]

    def test_surfaces_400_when_already_resolved(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _error_response(
                request,
                code="already_resolved",
                message="pending install already approved",
                status_code=400,
            )

        http = _make_http(handler)
        try:
            with pytest.raises(OlympusApiError) as exc:
                AppsService(http).approve_pending_install("pend-uuid-1")
        finally:
            http.close()
        assert exc.value.status_code == 400
        assert exc.value.code == "already_resolved"


# ===========================================================================
# deny_pending_install
# ===========================================================================


class TestDenyPendingInstall:
    def test_posts_deny_with_no_body(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["body"] = request.content
            return _json_response(request, {}, status_code=204)

        http = _make_http(handler)
        try:
            AppsService(http).deny_pending_install("pend-uuid-1")
        finally:
            http.close()
        assert captured["method"] == "POST"
        assert captured["path"] == (
            "/api/v1/apps/pending_install/pend-uuid-1/deny"
        )
        assert captured["body"] in (b"", b"null")

    def test_surfaces_410_when_expired(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _error_response(
                request,
                code="gone",
                message="pending install expired",
                status_code=410,
            )

        http = _make_http(handler)
        try:
            with pytest.raises(OlympusApiError) as exc:
                AppsService(http).deny_pending_install("pend-uuid-expired")
        finally:
            http.close()
        assert exc.value.status_code == 410

    def test_surfaces_403_when_not_admin(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _error_response(
                request,
                code="forbidden",
                message="tenant_admin required",
                status_code=403,
            )

        http = _make_http(handler)
        try:
            with pytest.raises(OlympusApiError) as exc:
                AppsService(http).deny_pending_install("pend-uuid-1")
        finally:
            http.close()
        assert exc.value.status_code == 403
