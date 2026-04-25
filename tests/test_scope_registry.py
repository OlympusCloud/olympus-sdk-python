"""Tests for PlatformService.list_scope_registry + get_scope_registry_digest
(gcp#3517).

Wire contract:
    GET /platform/scope-registry?namespace=&owner_app_id=&include_drafts=
        → { scopes: ScopeRow[], total: int }
    GET /platform/scope-registry/digest
        → { platform_catalog_digest: hex, row_count: int }

Mocks the http client with :class:`MagicMock`, asserts path/params,
returns synthesized envelopes, verifies parsed dataclasses.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from olympus_sdk.services.platform import (
    PlatformService,
    ScopeRegistryDigest,
    ScopeRegistryListing,
    ScopeRow,
)


class TestListScopeRegistry:
    """``PlatformService.list_scope_registry`` (gcp#3517)."""

    def test_no_filters_returns_full_catalog(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "scopes": [
                {
                    "scope": "auth.session.read@user",
                    "resource": "session",
                    "action": "read",
                    "holder": "user",
                    "namespace": "auth",
                    "owner_app_id": None,
                    "description": "Read your own session metadata",
                    "is_destructive": False,
                    "requires_mfa": False,
                    "grace_behavior": "extend",
                    "consent_prompt_copy": "View your session",
                    "workshop_status": "approved",
                    "bit_id": 0,
                },
                {
                    "scope": "voice.call.write@tenant",
                    "resource": "call",
                    "action": "write",
                    "holder": "tenant",
                    "namespace": "voice",
                    "owner_app_id": "orderecho-ai",
                    "description": "Place outbound voice calls on the tenant",
                    "is_destructive": True,
                    "requires_mfa": True,
                    "grace_behavior": "deny",
                    "consent_prompt_copy": "Place outbound calls",
                    "workshop_status": "service_ok",
                    "bit_id": 12,
                },
            ],
            "total": 2,
        }
        svc = PlatformService(http)
        listing = svc.list_scope_registry()

        assert http.get.call_args.args == ("/platform/scope-registry",)
        assert http.get.call_args.kwargs.get("params") is None

        assert isinstance(listing, ScopeRegistryListing)
        assert listing.total == 2
        assert len(listing.scopes) == 2
        assert listing.scopes[0].scope == "auth.session.read@user"
        assert listing.scopes[0].bit_id == 0
        assert listing.scopes[0].owner_app_id is None
        assert listing.scopes[1].owner_app_id == "orderecho-ai"
        assert listing.scopes[1].is_destructive is True
        assert listing.scopes[1].requires_mfa is True
        assert listing.scopes[1].bit_id == 12

    def test_filters_forwarded_as_params(self) -> None:
        http = MagicMock()
        http.get.return_value = {"scopes": [], "total": 0}
        svc = PlatformService(http)
        svc.list_scope_registry(
            namespace="voice",
            owner_app_id="orderecho-ai",
            include_drafts=True,
        )
        params = http.get.call_args.kwargs["params"]
        assert params == {
            "namespace": "voice",
            "owner_app_id": "orderecho-ai",
            "include_drafts": "true",
        }

    def test_owner_app_id_empty_string_forwarded_distinctly(self) -> None:
        # Empty string MUST be sent as a param — server interprets it as
        # "platform-owned only" filter, distinct from omitted (= no filter).
        http = MagicMock()
        http.get.return_value = {"scopes": [], "total": 0}
        svc = PlatformService(http)
        svc.list_scope_registry(owner_app_id="")
        params = http.get.call_args.kwargs["params"]
        assert "owner_app_id" in params
        assert params["owner_app_id"] == ""

    def test_include_drafts_false_omits_param(self) -> None:
        http = MagicMock()
        http.get.return_value = {"scopes": [], "total": 0}
        svc = PlatformService(http)
        svc.list_scope_registry(include_drafts=False)
        # include_drafts=False (default) means omit the param so server
        # default kicks in.
        params = http.get.call_args.kwargs.get("params")
        assert params is None or "include_drafts" not in params

    def test_tolerates_missing_optional_fields(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "scopes": [
                {
                    "scope": "creator.draft.write@tenant",
                    "resource": "draft",
                    "action": "write",
                    "holder": "tenant",
                    "namespace": "creator",
                    "description": "",
                    "is_destructive": False,
                    "requires_mfa": False,
                    "grace_behavior": "extend",
                    "consent_prompt_copy": "",
                    "workshop_status": "pending",
                    # owner_app_id + bit_id deliberately omitted
                },
            ],
            "total": 1,
        }
        svc = PlatformService(http)
        listing = svc.list_scope_registry(include_drafts=True)
        assert listing.scopes[0].bit_id is None
        assert listing.scopes[0].owner_app_id is None
        assert listing.scopes[0].workshop_status == "pending"

    def test_empty_response(self) -> None:
        http = MagicMock()
        http.get.return_value = {"scopes": [], "total": 0}
        svc = PlatformService(http)
        listing = svc.list_scope_registry()
        assert listing.scopes == []
        assert listing.total == 0


class TestGetScopeRegistryDigest:
    """``PlatformService.get_scope_registry_digest`` (gcp#3517)."""

    def test_parses_hex_and_count(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "platform_catalog_digest": (
                "12398a9b0517a3576d0e4d88807a34573d940aaada6bb61def2d540009c7bc19"
            ),
            "row_count": 3,
        }
        svc = PlatformService(http)
        digest = svc.get_scope_registry_digest()

        assert http.get.call_args.args == ("/platform/scope-registry/digest",)
        assert isinstance(digest, ScopeRegistryDigest)
        assert (
            digest.platform_catalog_digest
            == "12398a9b0517a3576d0e4d88807a34573d940aaada6bb61def2d540009c7bc19"
        )
        assert digest.row_count == 3

    def test_empty_catalog(self) -> None:
        # sha256("[]") on the rust + python side — the SDK round-trips.
        http = MagicMock()
        http.get.return_value = {
            "platform_catalog_digest": (
                "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
            ),
            "row_count": 0,
        }
        svc = PlatformService(http)
        digest = svc.get_scope_registry_digest()
        assert digest.row_count == 0
        assert len(digest.platform_catalog_digest) == 64  # sha256 hex


class TestScopeRowDataclass:
    """Sanity checks on the ScopeRow dataclass — shapes match the Rust side."""

    def test_minimal_construction(self) -> None:
        # All non-optional fields required; bit_id and owner_app_id default
        # to None.
        row = ScopeRow(
            scope="x",
            resource="r",
            action="read",
            holder="user",
            namespace="ns",
            description="",
            is_destructive=False,
            requires_mfa=False,
            grace_behavior="extend",
            consent_prompt_copy="",
            workshop_status="approved",
        )
        assert row.bit_id is None
        assert row.owner_app_id is None
