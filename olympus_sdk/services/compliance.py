"""ComplianceService — dram-shop event recording + rules lookup (#3316).

Cross-app surface used by both BarOS and PizzaOS for ID-check /
refused-service / over-serve audit trails plus the rules-lookup API
shipped in olympus-cloud-gcp PRs #3525 + #3530.

Routes:

| Method | Route                                              | Notes                       |
|--------|----------------------------------------------------|-----------------------------|
| POST   | ``/platform/compliance/dram-shop-events``          | Record one compliance event |
| GET    | ``/platform/compliance/dram-shop-events``          | List events (filtered)      |
| GET    | ``/platform/compliance/dram-shop-rules``           | List effective rules        |

The accepted ``event_type`` values are: ``id_check_passed``,
``id_check_failed``, ``service_refused``, ``over_serve_warning``,
``incident_filed``. Anything else is rejected by the server with HTTP
400.

``vertical_extensions`` is a free-form JSON envelope the platform
stores as-is for downstream BAC estimation and incident-packet export
(e.g. PizzaOS food-weighting input for the BAC estimator).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from olympus_sdk.http import OlympusHttpClient

DramShopEventType = Literal[
    "id_check_passed",
    "id_check_failed",
    "service_refused",
    "over_serve_warning",
    "incident_filed",
]


@dataclass
class DramShopEvent:
    """Single row from ``platform_dram_shop_events`` (#3316).

    ``bac_inputs`` and ``vertical_extensions`` are free-form JSON
    envelopes the server stores as-is for downstream BAC estimation
    and incident-packet export. ``event_type`` is one of the values
    enumerated by :data:`DramShopEventType` but exposed here as a
    plain ``str`` so future server-side additions don't break parsing.
    """

    event_id: str
    tenant_id: str
    location_id: str
    event_type: str
    occurred_at: str
    created_at: str
    customer_ref: str | None = None
    staff_user_id: str | None = None
    estimated_bac: float | None = None
    bac_inputs: dict[str, Any] | None = None
    vertical_extensions: dict[str, Any] | None = None
    notes: str | None = None


@dataclass
class DramShopEventList:
    """Envelope returned by ``GET /platform/compliance/dram-shop-events``."""

    events: list[DramShopEvent] = field(default_factory=list)
    total_returned: int = 0


@dataclass
class DramShopRule:
    """Single row from ``platform_dram_shop_rules`` (#3316)."""

    tenant_id: str
    rule_id: str
    jurisdiction_code: str
    rule_type: str
    effective_from: str
    rule_payload: dict[str, Any] | None = None
    effective_until: str | None = None
    override_app_id: str | None = None
    notes: str | None = None
    created_at: str | None = None


class ComplianceService:
    """Compliance audit, GDPR data requests, and dram-shop event recording."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Dram-shop compliance (#3316) — cross-app: BarOS + PizzaOS
    # ------------------------------------------------------------------

    def record_dram_shop_event(
        self,
        *,
        location_id: str,
        event_type: DramShopEventType,
        customer_ref: str | None = None,
        staff_user_id: str | None = None,
        estimated_bac: float | None = None,
        bac_inputs: dict[str, Any] | None = None,
        vertical_extensions: dict[str, Any] | None = None,
        notes: str | None = None,
        occurred_at: str | None = None,
    ) -> DramShopEvent:
        """Record a dram-shop compliance event (#3316).

        ``event_type`` must be one of: ``id_check_passed``,
        ``id_check_failed``, ``service_refused``, ``over_serve_warning``,
        ``incident_filed``. Returns the persisted event with server-set
        ``event_id`` + ``created_at``.

        ``vertical_extensions`` is an app-specific JSON payload (e.g.
        PizzaOS food-weighting input for the BAC estimator) — pass
        anything the future BAC estimator should consume on read.
        """
        payload: dict[str, Any] = {
            "location_id": location_id,
            "event_type": event_type,
        }
        if customer_ref is not None:
            payload["customer_ref"] = customer_ref
        if staff_user_id is not None:
            payload["staff_user_id"] = staff_user_id
        if estimated_bac is not None:
            payload["estimated_bac"] = estimated_bac
        if bac_inputs is not None:
            payload["bac_inputs"] = bac_inputs
        if vertical_extensions is not None:
            payload["vertical_extensions"] = vertical_extensions
        if notes is not None:
            payload["notes"] = notes
        if occurred_at is not None:
            payload["occurred_at"] = occurred_at
        body = self._http.post(
            "/platform/compliance/dram-shop-events", json=payload
        )
        return _to_dram_shop_event(body)

    def list_dram_shop_events(
        self,
        *,
        location_id: str | None = None,
        from_: str | None = None,
        to: str | None = None,
        event_type: DramShopEventType | None = None,
        limit: int | None = None,
    ) -> DramShopEventList:
        """List dram-shop events for the current tenant with optional filters.

        Used by the future incident-packet exporter (#3310) and
        compliance dashboards. ``limit`` is clamped server-side to
        ``1..=500`` (default 100).

        ``from_`` carries the trailing underscore because ``from`` is a
        Python keyword; the SDK rewrites it to ``from`` on the wire.
        """
        params: dict[str, Any] = {}
        if location_id is not None:
            params["location_id"] = location_id
        if from_ is not None:
            params["from"] = from_
        if to is not None:
            params["to"] = to
        if event_type is not None:
            params["event_type"] = event_type
        if limit is not None:
            params["limit"] = limit
        body = self._http.get(
            "/platform/compliance/dram-shop-events", params=params
        )
        rows = body.get("events") or []
        events = [_to_dram_shop_event(row) for row in rows if isinstance(row, dict)]
        total = body.get("total_returned")
        if not isinstance(total, int):
            total = len(events)
        return DramShopEventList(events=events, total_returned=total)

    def list_dram_shop_rules(
        self,
        *,
        jurisdiction_code: str | None = None,
        app_id: str | None = None,
        rule_type: str | None = None,
    ) -> list[DramShopRule]:
        """List currently-effective dram-shop rules for a tenant (#3316).

        When ``app_id`` is supplied, returns rules for that app's
        vertical override PLUS the platform default rules — so the
        caller always gets a complete rule-set. Without ``app_id``,
        returns platform defaults only.
        """
        params: dict[str, Any] = {}
        if jurisdiction_code is not None:
            params["jurisdiction_code"] = jurisdiction_code
        if app_id is not None:
            params["app_id"] = app_id
        if rule_type is not None:
            params["rule_type"] = rule_type
        body = self._http.get(
            "/platform/compliance/dram-shop-rules", params=params
        )
        rows = body.get("rules") or []
        return [_to_dram_shop_rule(row) for row in rows if isinstance(row, dict)]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _opt_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _opt_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _opt_float(value: Any) -> float | None:
    if isinstance(value, bool):  # bool is an int — exclude explicitly
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _to_dram_shop_event(row: dict[str, Any]) -> DramShopEvent:
    return DramShopEvent(
        event_id=row.get("event_id", "") or "",
        tenant_id=row.get("tenant_id", "") or "",
        location_id=row.get("location_id", "") or "",
        event_type=row.get("event_type", "") or "",
        occurred_at=row.get("occurred_at", "") or "",
        created_at=row.get("created_at", "") or "",
        customer_ref=_opt_str(row.get("customer_ref")),
        staff_user_id=_opt_str(row.get("staff_user_id")),
        estimated_bac=_opt_float(row.get("estimated_bac")),
        bac_inputs=_opt_dict(row.get("bac_inputs")),
        vertical_extensions=_opt_dict(row.get("vertical_extensions")),
        notes=_opt_str(row.get("notes")),
    )


def _to_dram_shop_rule(row: dict[str, Any]) -> DramShopRule:
    return DramShopRule(
        tenant_id=row.get("tenant_id", "") or "",
        rule_id=row.get("rule_id", "") or "",
        jurisdiction_code=row.get("jurisdiction_code", "") or "",
        rule_type=row.get("rule_type", "") or "",
        effective_from=row.get("effective_from", "") or "",
        rule_payload=_opt_dict(row.get("rule_payload")),
        effective_until=_opt_str(row.get("effective_until")),
        override_app_id=_opt_str(row.get("override_app_id")),
        notes=_opt_str(row.get("notes")),
        created_at=_opt_str(row.get("created_at")),
    )


__all__ = [
    "ComplianceService",
    "DramShopEvent",
    "DramShopEventList",
    "DramShopEventType",
    "DramShopRule",
]
