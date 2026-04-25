"""Tests for the two platform endpoints landed via olympus-cloud-gcp PRs
#3519 + #3520:

  - GatingService.get_plan_details() → GET /platform/gating/plan-details
  - ConsentService.describe()        → GET /platform/consent-prompt

Mock the OlympusHttpClient, assert path/params, synthesize the Rust
handler's JSON envelope, verify parsed dataclasses.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from olympus_sdk import ConsentService
from olympus_sdk.services.gating import GatingService, PlanDetails


class TestGetPlanDetails:
    def test_no_tenant_id_omits_query_param(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "current_plan": "growth",
            "plans": [],
            "as_of": "2026-04-25T13:00:00Z",
        }
        svc = GatingService(http)
        details = svc.get_plan_details()

        path = http.get.call_args[0][0]
        kwargs = http.get.call_args.kwargs
        assert path == "/platform/gating/plan-details"
        # No tenant_id passed
        assert kwargs.get("params", {}) == {}

        assert isinstance(details, PlanDetails)
        assert details.current_plan == "growth"
        assert details.plans == []
        assert details.as_of == "2026-04-25T13:00:00Z"

    def test_tenant_id_passed_as_query_param(self) -> None:
        http = MagicMock()
        http.get.return_value = {"current_plan": None, "plans": [], "as_of": "2026-04-25T13:00:00Z"}
        svc = GatingService(http)
        svc.get_plan_details(tenant_id="ten-abc")

        kwargs = http.get.call_args.kwargs
        assert kwargs["params"] == {"tenant_id": "ten-abc"}

    def test_parses_full_envelope(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "current_plan": "growth",
            "plans": [
                {
                    "tier_id": "free",
                    "display_name": "Free",
                    "monthly_price_usd": 0.0,
                    "features": ["basic"],
                    "usage_limits": {},
                    "ranks_higher_than_current": False,
                    "is_current": False,
                    "diff_vs_current": [],
                    "contact_sales": False,
                },
                {
                    "tier_id": "growth",
                    "display_name": "Growth",
                    "monthly_price_usd": 99.0,
                    "features": ["basic", "analytics"],
                    "usage_limits": {"voice_minutes": 60},
                    "ranks_higher_than_current": False,
                    "is_current": True,
                    "diff_vs_current": [],
                    "contact_sales": False,
                },
                {
                    "tier_id": "enterprise",
                    "display_name": "Enterprise",
                    "monthly_price_usd": None,
                    "features": ["basic", "analytics", "sla"],
                    "usage_limits": {"voice_minutes": 300},
                    "ranks_higher_than_current": True,
                    "is_current": False,
                    "diff_vs_current": ["unlocks: sla", "+240 voice_minutes"],
                    "contact_sales": True,
                },
            ],
            "as_of": "2026-04-25T13:00:00Z",
        }
        svc = GatingService(http)
        details = svc.get_plan_details()

        assert details.current_plan == "growth"
        assert len(details.plans) == 3

        free = details.plans[0]
        assert free.tier_id == "free"
        assert free.monthly_price_usd == 0.0
        assert free.is_current is False

        growth = details.plans[1]
        assert growth.is_current is True
        assert growth.monthly_price_usd == 99.0

        ent = details.plans[2]
        assert ent.contact_sales is True
        assert ent.monthly_price_usd is None
        assert ent.ranks_higher_than_current is True
        assert "unlocks: sla" in ent.diff_vs_current
        assert "+240 voice_minutes" in ent.diff_vs_current


class TestDescribeConsentPrompt:
    def test_describe_path_and_full_envelope(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "app_id": "com.olympuscloud.maximus",
            "scope": "auth.session.read@user",
            "prompt_text": "Maximus will be able to see your active sessions.",
            "prompt_hash": "0" * 64,
            "is_destructive": False,
            "requires_mfa": False,
            "app_may_request": True,
        }
        svc = ConsentService(http)
        prompt = svc.describe(
            app_id="com.olympuscloud.maximus",
            scope="auth.session.read@user",
        )

        path = http.get.call_args[0][0]
        params = http.get.call_args.kwargs["params"]
        assert path == "/platform/consent-prompt"
        assert params == {
            "app_id": "com.olympuscloud.maximus",
            "scope": "auth.session.read@user",
        }

        assert prompt.app_id == "com.olympuscloud.maximus"
        assert prompt.scope == "auth.session.read@user"
        assert prompt.prompt_text.startswith("Maximus")
        assert len(prompt.prompt_hash) == 64
        assert prompt.is_destructive is False
        assert prompt.requires_mfa is False
        assert prompt.app_may_request is True

    def test_describe_destructive_scope(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "app_id": "com.x",
            "scope": "auth.session.delete@user",
            "prompt_text": "X will sign you out of other devices.",
            "prompt_hash": "a" * 64,
            "is_destructive": True,
            "requires_mfa": True,
            "app_may_request": True,
        }
        svc = ConsentService(http)
        prompt = svc.describe(app_id="com.x", scope="auth.session.delete@user")
        assert prompt.is_destructive is True
        assert prompt.requires_mfa is True

    def test_describe_app_may_request_false_for_cross_app_scope(self) -> None:
        http = MagicMock()
        http.get.return_value = {
            "app_id": "com.untrusted",
            "scope": "pizza.menu.read@tenant",
            "prompt_text": "untrusted will read pizza menu data.",
            "prompt_hash": "b" * 64,
            "is_destructive": False,
            "requires_mfa": False,
            "app_may_request": False,
        }
        svc = ConsentService(http)
        prompt = svc.describe(app_id="com.untrusted", scope="pizza.menu.read@tenant")
        assert prompt.app_may_request is False
