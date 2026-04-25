"""Tests for dram-shop + payment-routing wrappers (#3316, #3312).

Mirrors the Dart fanout (olympus-sdk-dart#42 → 0.8.3) and the
TypeScript fanout (olympus-sdk-typescript#12 → 0.5.2) for the platform
endpoints landed in olympus-cloud-gcp PRs #3525, #3528, #3530:

- ``ComplianceService.record_dram_shop_event`` -> POST ``/platform/compliance/dram-shop-events``
- ``ComplianceService.list_dram_shop_events``  -> GET  ``/platform/compliance/dram-shop-events``
- ``ComplianceService.list_dram_shop_rules``   -> GET  ``/platform/compliance/dram-shop-rules``
- ``PayService.configure_routing``             -> POST ``/platform/pay/routing``
- ``PayService.get_routing``                   -> GET  ``/platform/pay/routing/{location_id}``

Mocks the http client with :class:`MagicMock`, asserts
path/params/body, returns synthesized envelopes, verifies parsed
dataclasses.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from olympus_sdk import (
    ComplianceService,
    DramShopEvent,
    DramShopEventList,
    DramShopRule,
    RoutingConfig,
)
from olympus_sdk.services.pay import PayService

# ---------------------------------------------------------------------------
# ComplianceService.record_dram_shop_event
# ---------------------------------------------------------------------------


class TestRecordDramShopEvent:
    def test_canonical_body_shape_and_response_parsing(self) -> None:
        http = MagicMock()
        http.post.return_value = {
            "event_id": "evt-uuid-1",
            "tenant_id": "ten-1",
            "location_id": "loc-1",
            "event_type": "id_check_passed",
            "customer_ref": "hashed-cust-key",
            "staff_user_id": "usr-staff",
            "estimated_bac": 0.04,
            "bac_inputs": {"gender": "F", "weight_kg": 65},
            "vertical_extensions": {"food_weight_g": 240},
            "notes": "first scan of the night",
            "occurred_at": "2026-04-25T13:00:00Z",
            "created_at": "2026-04-25T13:00:00Z",
        }
        svc = ComplianceService(http)
        event = svc.record_dram_shop_event(
            location_id="loc-1",
            event_type="id_check_passed",
            customer_ref="hashed-cust-key",
            staff_user_id="usr-staff",
            estimated_bac=0.04,
            bac_inputs={"gender": "F", "weight_kg": 65},
            vertical_extensions={"food_weight_g": 240},
            notes="first scan of the night",
            occurred_at="2026-04-25T13:00:00Z",
        )

        # Path + canonical wire body
        assert http.post.call_args[0][0] == "/platform/compliance/dram-shop-events"
        body = http.post.call_args.kwargs["json"]
        assert body == {
            "location_id": "loc-1",
            "event_type": "id_check_passed",
            "customer_ref": "hashed-cust-key",
            "staff_user_id": "usr-staff",
            "estimated_bac": 0.04,
            "bac_inputs": {"gender": "F", "weight_kg": 65},
            "vertical_extensions": {"food_weight_g": 240},
            "notes": "first scan of the night",
            "occurred_at": "2026-04-25T13:00:00Z",
        }

        # Parsed dataclass
        assert isinstance(event, DramShopEvent)
        assert event.event_id == "evt-uuid-1"
        assert event.tenant_id == "ten-1"
        assert event.location_id == "loc-1"
        assert event.event_type == "id_check_passed"
        assert event.customer_ref == "hashed-cust-key"
        assert event.staff_user_id == "usr-staff"
        assert event.estimated_bac == 0.04
        assert event.bac_inputs == {"gender": "F", "weight_kg": 65}
        assert event.vertical_extensions == {"food_weight_g": 240}
        assert event.notes == "first scan of the night"
        assert event.occurred_at == "2026-04-25T13:00:00Z"
        assert event.created_at == "2026-04-25T13:00:00Z"

    def test_omits_optional_keys_when_none(self) -> None:
        http = MagicMock()
        http.post.return_value = {
            "event_id": "evt-2",
            "tenant_id": "ten-1",
            "location_id": "loc-1",
            "event_type": "service_refused",
            "occurred_at": "2026-04-25T14:00:00Z",
            "created_at": "2026-04-25T14:00:00Z",
        }
        svc = ComplianceService(http)
        svc.record_dram_shop_event(
            location_id="loc-1",
            event_type="service_refused",
        )
        body = http.post.call_args.kwargs["json"]
        assert body == {
            "location_id": "loc-1",
            "event_type": "service_refused",
        }
        for key in (
            "customer_ref",
            "staff_user_id",
            "estimated_bac",
            "bac_inputs",
            "vertical_extensions",
            "notes",
            "occurred_at",
        ):
            assert key not in body


# ---------------------------------------------------------------------------
# ComplianceService.list_dram_shop_events
# ---------------------------------------------------------------------------


class TestListDramShopEvents:
    def test_all_filters_become_query_params(self) -> None:
        http = MagicMock()
        http.get.return_value = {"events": [], "total_returned": 0}
        svc = ComplianceService(http)
        svc.list_dram_shop_events(
            location_id="loc-1",
            from_="2026-04-01T00:00:00Z",
            to="2026-04-25T23:59:59Z",
            event_type="over_serve_warning",
            limit=250,
        )
        assert http.get.call_args[0][0] == "/platform/compliance/dram-shop-events"
        params = http.get.call_args.kwargs["params"]
        # `from_` is rewritten to `from` on the wire (Python keyword workaround)
        assert params == {
            "location_id": "loc-1",
            "from": "2026-04-01T00:00:00Z",
            "to": "2026-04-25T23:59:59Z",
            "event_type": "over_serve_warning",
            "limit": 250,
        }

    def test_no_filters_yields_empty_params_dict(self) -> None:
        http = MagicMock()
        http.get.return_value = {"events": [], "total_returned": 0}
        svc = ComplianceService(http)
        svc.list_dram_shop_events()
        params = http.get.call_args.kwargs["params"]
        assert params == {}

    def test_envelope_parses_events_and_total_returned(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "events": [
                {
                    "event_id": "evt-a",
                    "tenant_id": "ten-1",
                    "location_id": "loc-1",
                    "event_type": "id_check_passed",
                    "customer_ref": None,
                    "staff_user_id": "usr-1",
                    "estimated_bac": None,
                    "bac_inputs": None,
                    "vertical_extensions": None,
                    "notes": None,
                    "occurred_at": "2026-04-25T13:00:00Z",
                    "created_at": "2026-04-25T13:00:00Z",
                },
                {
                    "event_id": "evt-b",
                    "tenant_id": "ten-1",
                    "location_id": "loc-1",
                    "event_type": "incident_filed",
                    "occurred_at": "2026-04-25T14:00:00Z",
                    "created_at": "2026-04-25T14:00:00Z",
                },
            ],
            "total_returned": 42,
        }
        svc = ComplianceService(http)
        result = svc.list_dram_shop_events(location_id="loc-1")
        assert isinstance(result, DramShopEventList)
        assert result.total_returned == 42
        assert len(result.events) == 2
        # null -> None for optional fields
        assert result.events[0].event_id == "evt-a"
        assert result.events[0].event_type == "id_check_passed"
        assert result.events[0].customer_ref is None
        assert result.events[0].estimated_bac is None
        assert result.events[0].bac_inputs is None
        assert result.events[0].vertical_extensions is None
        assert result.events[1].event_id == "evt-b"
        assert result.events[1].event_type == "incident_filed"

    def test_total_returned_falls_back_to_event_count(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "events": [
                {
                    "event_id": "evt-a",
                    "tenant_id": "ten-1",
                    "location_id": "loc-1",
                    "event_type": "id_check_passed",
                    "occurred_at": "2026-04-25T13:00:00Z",
                    "created_at": "2026-04-25T13:00:00Z",
                },
            ],
            # total_returned omitted entirely
        }
        svc = ComplianceService(http)
        result = svc.list_dram_shop_events()
        assert result.total_returned == 1


# ---------------------------------------------------------------------------
# ComplianceService.list_dram_shop_rules
# ---------------------------------------------------------------------------


class TestListDramShopRules:
    def test_envelope_parses_every_field(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "rules": [
                {
                    "tenant_id": "ten-1",
                    "rule_id": "r1",
                    "jurisdiction_code": "US-FL",
                    "rule_type": "max_bac_serve",
                    "rule_payload": {"max_bac": 0.08},
                    "effective_from": "2026-01-01T00:00:00Z",
                    "effective_until": None,
                    "override_app_id": None,
                    "notes": None,
                    "created_at": "2026-01-01T00:00:00Z",
                },
                {
                    "tenant_id": "ten-1",
                    "rule_id": "r2",
                    "jurisdiction_code": "US-FL",
                    "rule_type": "service_window",
                    "rule_payload": {"start": "11:00", "end": "02:00"},
                    "effective_from": "2026-01-01T00:00:00Z",
                    "effective_until": "2026-12-31T00:00:00Z",
                    "override_app_id": "pizza-os",
                    "notes": "pizza vertical override",
                    "created_at": "2026-01-15T00:00:00Z",
                },
            ]
        }
        svc = ComplianceService(http)
        rules = svc.list_dram_shop_rules(
            jurisdiction_code="US-FL",
            app_id="pizza-os",
            rule_type="max_bac_serve",
        )
        assert http.get.call_args[0][0] == "/platform/compliance/dram-shop-rules"
        params = http.get.call_args.kwargs["params"]
        assert params == {
            "jurisdiction_code": "US-FL",
            "app_id": "pizza-os",
            "rule_type": "max_bac_serve",
        }
        assert len(rules) == 2
        assert isinstance(rules[0], DramShopRule)
        assert rules[0].rule_id == "r1"
        assert rules[0].jurisdiction_code == "US-FL"
        assert rules[0].rule_payload == {"max_bac": 0.08}
        assert rules[0].effective_from == "2026-01-01T00:00:00Z"
        assert rules[0].effective_until is None
        assert rules[0].override_app_id is None
        assert rules[1].override_app_id == "pizza-os"
        assert rules[1].effective_until == "2026-12-31T00:00:00Z"
        assert rules[1].notes == "pizza vertical override"

    def test_no_filters_yields_empty_params_dict(self) -> None:
        http = MagicMock()
        http.get.return_value = {"rules": []}
        svc = ComplianceService(http)
        rules = svc.list_dram_shop_rules()
        assert http.get.call_args.kwargs["params"] == {}
        assert rules == []


# ---------------------------------------------------------------------------
# PayService.configure_routing / get_routing (#3312)
# ---------------------------------------------------------------------------


class TestPayRouting:
    def test_configure_routing_canonical_body(self) -> None:
        http = MagicMock()
        http.post.return_value = {
            "tenant_id": "ten-1",
            "location_id": "loc-1",
            "preferred_processor": "square",
            "fallback_processors": ["olympus_pay"],
            "credentials_secret_ref": "olympus-merchant-credentials-loc-1-square-dev",
            "merchant_id": "MERCH-123",
            "is_active": True,
            "notes": None,
            "created_at": None,
            "updated_at": None,
        }
        svc = PayService(http)
        cfg = svc.configure_routing(
            location_id="loc-1",
            preferred_processor="square",
            fallback_processors=["olympus_pay"],
            credentials_secret_ref="olympus-merchant-credentials-loc-1-square-dev",
            merchant_id="MERCH-123",
            is_active=True,
        )
        assert http.post.call_args[0][0] == "/platform/pay/routing"
        body = http.post.call_args.kwargs["json"]
        assert body == {
            "location_id": "loc-1",
            "preferred_processor": "square",
            "fallback_processors": ["olympus_pay"],
            "is_active": True,
            "credentials_secret_ref": "olympus-merchant-credentials-loc-1-square-dev",
            "merchant_id": "MERCH-123",
        }
        assert isinstance(cfg, RoutingConfig)
        assert cfg.tenant_id == "ten-1"
        assert cfg.location_id == "loc-1"
        assert cfg.preferred_processor == "square"
        assert cfg.fallback_processors == ["olympus_pay"]
        assert cfg.credentials_secret_ref == (
            "olympus-merchant-credentials-loc-1-square-dev"
        )
        assert cfg.merchant_id == "MERCH-123"
        assert cfg.is_active is True
        assert cfg.notes is None
        assert cfg.created_at is None
        assert cfg.updated_at is None

    def test_configure_routing_omits_credentials_secret_ref_when_none(self) -> None:
        http = MagicMock()
        http.post.return_value = {
            "tenant_id": "ten-1",
            "location_id": "loc-2",
            "preferred_processor": "olympus_pay",
            "fallback_processors": [],
            "is_active": True,
        }
        svc = PayService(http)
        svc.configure_routing(
            location_id="loc-2",
            preferred_processor="olympus_pay",
        )
        body = http.post.call_args.kwargs["json"]
        # Required fields present (with empty fallback array)
        assert body["location_id"] == "loc-2"
        assert body["preferred_processor"] == "olympus_pay"
        assert body["fallback_processors"] == []
        assert body["is_active"] is True
        # Optional keys must NOT appear when None
        assert "credentials_secret_ref" not in body
        assert "merchant_id" not in body
        assert "notes" not in body

    def test_get_routing_url_encodes_location_id_path_segment(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "tenant_id": "ten-1",
            "location_id": "loc/with slash",
            "preferred_processor": "square",
            "fallback_processors": [],
            "is_active": True,
        }
        svc = PayService(http)
        svc.get_routing(location_id="loc/with slash")
        path = http.get.call_args[0][0]
        # `quote(safe='')` percent-encodes `/` and ` ` -> `%2F` / `%20`
        assert path == "/platform/pay/routing/loc%2Fwith%20slash"

    def test_get_routing_parses_response(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "tenant_id": "ten-1",
            "location_id": "loc-1",
            "preferred_processor": "adyen",
            "fallback_processors": ["olympus_pay", "square"],
            "credentials_secret_ref": "olympus-merchant-credentials-loc-1-adyen-prod",
            "merchant_id": "ADY-MERCH-9",
            "is_active": False,
            "notes": "tail-end fallback",
            "created_at": "2026-04-25T12:00:00Z",
            "updated_at": "2026-04-25T13:00:00Z",
        }
        svc = PayService(http)
        cfg = svc.get_routing(location_id="loc-1")
        assert cfg.tenant_id == "ten-1"
        assert cfg.preferred_processor == "adyen"
        assert cfg.fallback_processors == ["olympus_pay", "square"]
        assert cfg.is_active is False
        assert cfg.notes == "tail-end fallback"
        assert cfg.created_at == "2026-04-25T12:00:00Z"
        assert cfg.updated_at == "2026-04-25T13:00:00Z"
