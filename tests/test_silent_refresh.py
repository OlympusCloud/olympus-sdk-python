"""Tests for silent token refresh + session event stream.

Covers olympus-cloud-gcp#3403 §1.4 / olympus-cloud-gcp#3412. Uses small
``refresh_margin`` values and short TTLs (encoded into JWT ``exp``) so
real ``asyncio.sleep`` pauses resolve in milliseconds — no freezegun
dependency required.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from olympus_sdk.http import OlympusHttpClient
from olympus_sdk.services.auth import (
    AuthService,
    SessionExpired,
    SessionLoggedIn,
    SessionLoggedOut,
    SessionRefreshed,
    SilentRefreshHandle,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _make_jwt(*, exp: float, scopes: list[str] | None = None) -> str:
    """Forge a JWT with a specific ``exp`` claim. Signature not verified by SDK."""
    header = _b64u(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload_obj: dict[str, Any] = {"sub": "u1", "exp": exp}
    if scopes is not None:
        payload_obj["app_scopes"] = scopes
    payload = _b64u(json.dumps(payload_obj).encode())
    return f"{header}.{payload}.sig"


def _login_response(*, exp: float, refresh_token: str = "rt_abc") -> dict[str, Any]:
    return {
        "access_token": _make_jwt(exp=exp),
        "token_type": "Bearer",
        "expires_in": int(max(1, exp - time.time())),
        "refresh_token": refresh_token,
        "user_id": "u1",
        "tenant_id": "t1",
        "roles": ["admin"],
    }


def _mock_http() -> MagicMock:
    return MagicMock(spec=OlympusHttpClient)


# ---------------------------------------------------------------------------
# Session event stream — basic wiring
# ---------------------------------------------------------------------------


class TestSessionEvents:
    async def test_login_emits_logged_in(self) -> None:
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 3600)
        svc = AuthService(http)

        # Start subscriber first — before login fires the event.
        collected: list[Any] = []
        agen = svc.session_events()

        async def _collect() -> None:
            async for event in agen:
                collected.append(event)
                return

        task = asyncio.create_task(_collect())
        # Give the subscriber a tick to register.
        await asyncio.sleep(0)
        svc.login("u@test.com", "pw")
        await asyncio.wait_for(task, timeout=1.0)
        await agen.aclose()

        assert len(collected) == 1
        assert isinstance(collected[0], SessionLoggedIn)
        assert collected[0].session.access_token.startswith("ey") or "." in collected[0].session.access_token

    async def test_refresh_emits_session_refreshed(self) -> None:
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 3600)
        svc = AuthService(http)

        # Seed a session so refresh has something to capture.
        svc.login("u@test.com", "pw")

        collected: list[Any] = []
        agen = svc.session_events()

        async def _collect() -> None:
            async for event in agen:
                collected.append(event)
                return

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        http.post.return_value = _login_response(exp=time.time() + 3600, refresh_token="rt2")
        svc.refresh("rt_abc")
        await asyncio.wait_for(task, timeout=1.0)
        await agen.aclose()

        assert len(collected) == 1
        assert isinstance(collected[0], SessionRefreshed)

    async def test_logout_emits_logged_out_and_clears(self) -> None:
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 3600)
        svc = AuthService(http)
        svc.login("u@test.com", "pw")

        collected: list[Any] = []
        agen = svc.session_events()

        async def _collect() -> None:
            async for event in agen:
                collected.append(event)
                return

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        http.post.return_value = {}
        svc.logout()
        await asyncio.wait_for(task, timeout=1.0)
        await agen.aclose()

        assert len(collected) == 1
        assert isinstance(collected[0], SessionLoggedOut)
        assert svc.current_session is None
        http.clear_access_token.assert_called()

    async def test_multiple_subscribers_each_get_events(self) -> None:
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 3600)
        svc = AuthService(http)

        a_events: list[Any] = []
        b_events: list[Any] = []

        async def _sub(bucket: list[Any]) -> None:
            agen = svc.session_events()
            try:
                async for event in agen:
                    bucket.append(event)
                    return
            finally:
                await agen.aclose()

        ta = asyncio.create_task(_sub(a_events))
        tb = asyncio.create_task(_sub(b_events))
        await asyncio.sleep(0)
        svc.login("u@t.com", "pw")
        await asyncio.wait_for(asyncio.gather(ta, tb), timeout=1.0)

        assert len(a_events) == 1 and isinstance(a_events[0], SessionLoggedIn)
        assert len(b_events) == 1 and isinstance(b_events[0], SessionLoggedIn)


# ---------------------------------------------------------------------------
# Silent refresh scheduling + success path
# ---------------------------------------------------------------------------


class TestSilentRefresh:
    async def test_fires_at_exp_minus_margin(self) -> None:
        """Timer fires when ``exp - margin`` elapses; emits SessionRefreshed."""
        http = _mock_http()
        # Initial login: token expires in 0.2s; margin 0.1s → fire in ~0.1s.
        http.post.return_value = _login_response(exp=time.time() + 0.2)
        svc = AuthService(http)
        svc.login("u@t.com", "pw")

        # Prime refresh response: next token expires far in the future so
        # we don't loop into a second refresh during the test.
        http.post.return_value = _login_response(
            exp=time.time() + 3600, refresh_token="rt_next"
        )

        collected: list[Any] = []
        agen = svc.session_events()

        async def _collect() -> None:
            async for event in agen:
                collected.append(event)
                if isinstance(event, SessionRefreshed):
                    return

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        handle = svc.start_silent_refresh(refresh_margin=0.1)
        assert isinstance(handle, SilentRefreshHandle)
        assert handle.running

        await asyncio.wait_for(task, timeout=2.0)
        await agen.aclose()
        svc.stop_silent_refresh()

        # At least one refresh event should have been observed.
        assert any(isinstance(e, SessionRefreshed) for e in collected)
        # The refresh POST should have been called with the seed refresh_token.
        refresh_calls = [
            c for c in http.post.call_args_list if c.args and c.args[0] == "/auth/refresh"
        ]
        assert len(refresh_calls) >= 1

    async def test_failed_refresh_emits_expired_and_clears(self) -> None:
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 0.2)
        svc = AuthService(http)
        svc.login("u@t.com", "pw")

        # Next /auth/refresh raises — simulates 401 / network error.
        def _boom(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("401 Unauthorized")

        http.post.side_effect = _boom

        collected: list[Any] = []
        agen = svc.session_events()

        async def _collect() -> None:
            async for event in agen:
                collected.append(event)
                if isinstance(event, SessionExpired):
                    return

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        handle = svc.start_silent_refresh(refresh_margin=0.1)
        await asyncio.wait_for(task, timeout=2.0)
        await agen.aclose()

        assert any(isinstance(e, SessionExpired) for e in collected)
        assert svc.current_session is None
        assert not handle.running
        http.clear_access_token.assert_called()

    async def test_missing_refresh_token_emits_expired(self) -> None:
        http = _mock_http()
        # Login response carries no refresh_token.
        response: dict[str, Any] = {
            "access_token": _make_jwt(exp=time.time() + 3600),
            "token_type": "Bearer",
            "expires_in": 3600,
            "user_id": "u1",
        }
        http.post.return_value = response
        svc = AuthService(http)
        svc.login("u@t.com", "pw")
        assert svc.current_session is not None
        assert svc.current_session.refresh_token is None

        collected: list[Any] = []
        agen = svc.session_events()

        async def _collect() -> None:
            async for event in agen:
                collected.append(event)
                if isinstance(event, SessionExpired):
                    return

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        handle = svc.start_silent_refresh(refresh_margin=0.1)
        await asyncio.wait_for(task, timeout=2.0)
        await agen.aclose()

        assert any(
            isinstance(e, SessionExpired) and "refresh token" in e.reason
            for e in collected
        )
        assert svc.current_session is None
        assert not handle.running

    async def test_double_start_cancels_prior_handle(self) -> None:
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 3600)
        svc = AuthService(http)
        svc.login("u@t.com", "pw")

        first = svc.start_silent_refresh(refresh_margin=0.5)
        assert first.running
        # Second call cancels first.
        second = svc.start_silent_refresh(refresh_margin=0.5)
        # Let the cancellation settle.
        await asyncio.sleep(0.01)
        assert not first.running
        assert second.running
        assert first is not second

        svc.stop_silent_refresh()
        await asyncio.sleep(0.01)
        assert not second.running

    async def test_cancel_handle_stops_task(self) -> None:
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 3600)
        svc = AuthService(http)
        svc.login("u@t.com", "pw")

        handle = svc.start_silent_refresh(refresh_margin=0.5)
        assert handle.running
        handle.cancel()
        # Second cancel is a no-op.
        handle.cancel()
        await asyncio.sleep(0.01)
        assert not handle.running

    async def test_stop_silent_refresh_does_not_emit_logout(self) -> None:
        """Cancelling the timer is silent — only logout emits LoggedOut."""
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 3600)
        svc = AuthService(http)
        svc.login("u@t.com", "pw")

        # Subscribe AFTER login so the LoggedIn event is not observed here.
        collected: list[Any] = []
        agen = svc.session_events()

        async def _collect() -> None:
            async for event in agen:
                collected.append(event)

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)

        handle = svc.start_silent_refresh(refresh_margin=1.0)
        await asyncio.sleep(0.01)
        svc.stop_silent_refresh()
        await asyncio.sleep(0.05)

        # Cancel the collector cleanly.
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await agen.aclose()

        assert not handle.running
        assert all(not isinstance(e, SessionLoggedOut) for e in collected)

    async def test_logout_cancels_refresh_and_emits_logged_out(self) -> None:
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 3600)
        svc = AuthService(http)
        svc.login("u@t.com", "pw")

        handle = svc.start_silent_refresh(refresh_margin=0.5)
        assert handle.running

        collected: list[Any] = []
        agen = svc.session_events()

        async def _collect() -> None:
            async for event in agen:
                collected.append(event)
                if isinstance(event, SessionLoggedOut):
                    return

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)

        http.post.return_value = {}
        svc.logout()
        await asyncio.wait_for(task, timeout=1.0)
        await agen.aclose()

        assert any(isinstance(e, SessionLoggedOut) for e in collected)
        assert not handle.running
        assert svc.current_session is None


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


class TestSilentRefreshRobustness:
    async def test_listener_queue_full_does_not_break_loop(self) -> None:
        """A subscriber whose queue is full/closed must not break other subs."""
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 3600)
        svc = AuthService(http)

        # Inject a rogue queue with maxsize=1 and pre-fill it so put_nowait
        # raises QueueFull on emission. Others must still receive.
        rogue: asyncio.Queue = asyncio.Queue(maxsize=1)
        rogue.put_nowait("filler")
        loop = asyncio.get_running_loop()
        svc._subscribers.add((rogue, loop))

        good_events: list[Any] = []
        agen = svc.session_events()

        async def _collect() -> None:
            async for event in agen:
                good_events.append(event)
                return

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        svc.login("u@t.com", "pw")
        await asyncio.wait_for(task, timeout=1.0)
        await agen.aclose()

        assert len(good_events) == 1
        assert isinstance(good_events[0], SessionLoggedIn)

    async def test_immediate_fire_when_exp_already_passed(self) -> None:
        """If ``exp - margin`` is in the past, refresh fires immediately."""
        http = _mock_http()
        # Token already "expired" by 10 seconds.
        http.post.return_value = _login_response(exp=time.time() - 10)
        svc = AuthService(http)
        svc.login("u@t.com", "pw")

        # Next refresh returns a long-lived token so the loop stops after one.
        http.post.return_value = _login_response(exp=time.time() + 3600)

        collected: list[Any] = []
        agen = svc.session_events()

        async def _collect() -> None:
            async for event in agen:
                collected.append(event)
                if isinstance(event, SessionRefreshed):
                    return

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        svc.start_silent_refresh(refresh_margin=60.0)
        await asyncio.wait_for(task, timeout=1.0)
        await agen.aclose()
        svc.stop_silent_refresh()

        assert any(isinstance(e, SessionRefreshed) for e in collected)


# ---------------------------------------------------------------------------
# Handle shape
# ---------------------------------------------------------------------------


class TestSilentRefreshHandle:
    async def test_handle_shape(self) -> None:
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 3600)
        svc = AuthService(http)
        svc.login("u@t.com", "pw")

        handle = svc.start_silent_refresh(refresh_margin=10.0)
        assert isinstance(handle, SilentRefreshHandle)
        assert handle.running is True
        assert callable(handle.cancel)

        handle.cancel()
        await asyncio.sleep(0.01)
        assert handle.running is False

    def test_start_without_running_loop_raises(self) -> None:
        """``start_silent_refresh`` requires a running asyncio loop."""
        http = _mock_http()
        http.post.return_value = _login_response(exp=time.time() + 3600)
        svc = AuthService(http)
        svc.login("u@t.com", "pw")

        with pytest.raises(RuntimeError):
            svc.start_silent_refresh(refresh_margin=10.0)
