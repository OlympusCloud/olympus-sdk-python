"""Authentication, user management, and API key operations.

Wraps the Olympus Auth service (Rust) via the Go API Gateway.
Routes: ``/auth/*``, ``/platform/users/*``.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from olympus_sdk.errors import OlympusScopeRequiredError
from olympus_sdk.models.auth import ApiKey, AuthSession, FirebaseLinkResult, User

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from olympus_sdk.http import OlympusHttpClient


def _decode_jwt_claims(access_token: str) -> dict | None:
    """Decode raw JWT claims without signature verification.

    Returns ``None`` when the token is missing or malformed. Authorization
    is still enforced server-side; this helper is used by client-side
    scheduling (silent refresh reading ``exp``) and scope checks.
    """
    if not access_token:
        return None
    parts = access_token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        claims = json.loads(decoded.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return claims if isinstance(claims, dict) else None


def _decode_jwt_app_scopes(access_token: str) -> list[str]:
    """Decode the ``app_scopes`` claim from an RS256/HS256 JWT payload.

    Returns an empty list if the token is malformed, unparseable, or the
    claim is absent / not a list of strings. No signature verification is
    performed — the SDK trusts the gateway's response.
    """
    claims = _decode_jwt_claims(access_token)
    if claims is None:
        return []
    raw = claims.get("app_scopes")
    if not isinstance(raw, list):
        return []
    return [str(s) for s in raw if isinstance(s, str)]


def _decode_jwt_exp_seconds(access_token: str) -> float | None:
    """Extract the JWT ``exp`` claim (seconds since Unix epoch).

    Returns ``None`` when the token is missing, malformed, or lacks a
    numeric ``exp`` claim. Used by :meth:`AuthService.start_silent_refresh`
    to schedule the refresh timer.
    """
    claims = _decode_jwt_claims(access_token)
    if claims is None:
        return None
    exp = claims.get("exp")
    if isinstance(exp, bool):  # bool is subclass of int; reject
        return None
    if isinstance(exp, (int, float)):
        return float(exp)
    return None


# ---------------------------------------------------------------------------
# Session event types (olympus-cloud-gcp#3403 §1.4 / olympus-cloud-gcp#3412)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionLoggedIn:
    """Emitted once after a successful login/SSO/PIN call.

    ``session`` is the :class:`AuthSession` returned by the login flow.
    """

    session: AuthSession


@dataclass(frozen=True)
class SessionRefreshed:
    """Emitted after a successful silent or manual refresh.

    ``session`` is the newly-refreshed :class:`AuthSession`. The SDK has
    already swapped the HTTP client's Bearer token before emission.
    """

    session: AuthSession


@dataclass(frozen=True)
class SessionExpired:
    """Emitted when silent refresh fails or no refresh token is available.

    The SDK clears the session and stops the silent-refresh timer before
    emitting. ``reason`` is a short diagnostic string (not localized, not
    user-facing) suitable for logging.
    """

    reason: str


@dataclass(frozen=True)
class SessionLoggedOut:
    """Emitted after :meth:`AuthService.logout` completes."""


SessionEvent = SessionLoggedIn | SessionRefreshed | SessionExpired | SessionLoggedOut


class SilentRefreshHandle:
    """Handle returned by :meth:`AuthService.start_silent_refresh`.

    Call :meth:`cancel` to stop the background refresh task. Inspect
    :attr:`running` to check whether the task is still active. Cancelling
    a handle does NOT emit a :class:`SessionLoggedOut` event — only
    :meth:`AuthService.logout` does.

    Idempotent: a second call to ``start_silent_refresh`` cancels the
    prior handle before returning the new one.
    """

    __slots__ = ("_task", "_cancelled")

    def __init__(self, task: asyncio.Task[None]) -> None:
        self._task = task
        self._cancelled = False

    @property
    def running(self) -> bool:
        """``True`` until :meth:`cancel` is called or the task finishes."""
        if self._cancelled:
            return False
        return not self._task.done()

    def cancel(self) -> None:
        """Cancel the background refresh task.

        Safe to call multiple times. Does NOT emit :class:`SessionLoggedOut`.
        """
        if self._cancelled:
            return
        self._cancelled = True
        if not self._task.done():
            self._task.cancel()


#: Default seconds before JWT ``exp`` to fire the silent refresh.
DEFAULT_REFRESH_MARGIN_SECONDS: float = 60.0


class AuthService:
    """Authentication, user management, and API key operations."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http
        self._current_session: AuthSession | None = None
        # Silent-refresh + event-stream state (#3403 §1.4 / #3412).
        self._refresh_task: asyncio.Task[None] | None = None
        self._refresh_handle: SilentRefreshHandle | None = None
        self._refresh_margin: float = DEFAULT_REFRESH_MARGIN_SECONDS
        # Each subscriber records (queue, loop_it_was_bound_to) so that emissions
        # from a worker thread (httpx is sync; we use asyncio.to_thread for the
        # refresh POST) are marshalled back to the subscriber's loop via
        # ``loop.call_soon_threadsafe``. Without this, ``put_nowait`` from the
        # worker thread is unsafe under PYTHONASYNCIODEBUG=1 and on non-CPython.
        self._subscribers: set[
            tuple[asyncio.Queue[SessionEvent], asyncio.AbstractEventLoop]
        ] = set()

    # ------------------------------------------------------------------
    # Session accessors (#3403 §1.2)
    # ------------------------------------------------------------------

    @property
    def current_session(self) -> AuthSession | None:
        """The last :class:`AuthSession` returned by login/refresh, if any.

        Cleared by :meth:`logout`. External consumers that call
        :meth:`OlympusClient.set_access_token` directly do NOT populate this
        field — use the scope helpers on the client for those flows.
        """
        return self._current_session

    @property
    def granted_scopes(self) -> frozenset[str]:
        """All scopes granted to the current session.

        Pulled from :attr:`AuthSession.app_scopes`, which is populated from
        the login response body and/or decoded from the JWT ``app_scopes``
        claim. Returns an empty :class:`frozenset` when no session is active.
        """
        session = self._current_session
        if session is None:
            return frozenset()
        return frozenset(session.app_scopes or [])

    def has_scope(self, scope: str) -> bool:
        """Return ``True`` if the current session has the given scope.

        Fail-fast client-side check that runs before a network call. Prefer
        :class:`olympus_sdk.constants.OlympusScopes` typed constants over
        string literals.
        """
        return scope in self.granted_scopes

    def require_scope(self, scope: str) -> None:
        """Raise :class:`OlympusScopeRequiredError` if ``scope`` is not granted.

        Used to assert a scope client-side before attempting a write that
        would otherwise round-trip only to be rejected with a
        ``scope_not_granted`` error from the gateway.
        """
        if not self.has_scope(scope):
            raise OlympusScopeRequiredError(scope)

    # ------------------------------------------------------------------
    # Login / session lifecycle
    # ------------------------------------------------------------------

    def _capture_session(
        self,
        session: AuthSession,
        *,
        event: str = "loggedIn",
    ) -> AuthSession:
        """Populate ``app_scopes`` from JWT when body omitted it, stash, emit.

        ``event`` selects which :class:`SessionEvent` is broadcast:
        ``"loggedIn"`` for initial login flows, ``"refreshed"`` for refresh
        (silent or manual). The event is emitted AFTER the session is
        stashed and the HTTP client is primed, so subscribers see the new
        state.
        """
        if not session.app_scopes:
            decoded = _decode_jwt_app_scopes(session.access_token)
            if decoded:
                session.app_scopes = decoded
        self._current_session = session
        if event == "refreshed":
            self._emit(SessionRefreshed(session=session))
        else:
            self._emit(SessionLoggedIn(session=session))
        return session

    def login(self, email: str, password: str) -> AuthSession:
        """Authenticate with email and password.

        On success the returned access token is automatically set on the
        HTTP client for subsequent requests and a :class:`SessionLoggedIn`
        event is broadcast to :meth:`session_events` subscribers.
        """
        data = self._http.post(
            "/auth/login", json={"email": email, "password": password}
        )
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return self._capture_session(session)

    def login_sso(self, provider: str) -> AuthSession:
        """Initiate SSO login via an external provider (e.g. "google", "apple")."""
        data = self._http.post("/auth/sso/initiate", json={"provider": provider})
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return self._capture_session(session)

    def login_pin(self, pin: str, *, location_id: str | None = None) -> AuthSession:
        """Authenticate staff using a PIN code."""
        payload: dict[str, str] = {"pin": pin}
        if location_id is not None:
            payload["location_id"] = location_id
        data = self._http.post("/auth/login/pin", json=payload)
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return self._capture_session(session)

    def login_with_firebase(
        self,
        firebase_id_token: str,
        *,
        tenant_slug: str | None = None,
        invite_token: str | None = None,
    ) -> AuthSession:
        """Authenticate via Firebase ID token (#3275).

        When ``tenant_slug`` is omitted the backend auto-resolves the tenant
        from the Firebase UID's identity link. When the lookup matches more
        than one tenant the call raises
        :class:`olympus_sdk.errors.TenantAmbiguous`; the app should render a
        picker from ``e.candidates`` and retry with the chosen ``tenant_slug``.

        Other typed errors (all subclass
        :class:`olympus_sdk.errors.FirebaseLoginError`):
            * ``IdentityUnlinked`` — 403; redirect user to ``e.signup_url``
            * ``NoTenantMatch`` — 404; auto-resolution found nothing
            * ``InvalidFirebaseToken`` — 400; bad signature / wrong audience
        """
        payload: dict[str, str] = {"firebase_id_token": firebase_id_token}
        if tenant_slug is not None:
            payload["tenant_slug"] = tenant_slug
        if invite_token is not None:
            payload["invite_token"] = invite_token
        data = self._http.post("/auth/firebase/exchange", json=payload)
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return self._capture_session(session)

    def link_firebase(self, firebase_id_token: str) -> FirebaseLinkResult:
        """Link a Firebase UID to the currently-authenticated Olympus identity.

        Idempotent — re-linking the same ``(firebase_uid, caller)`` returns
        the ORIGINAL ``linked_at`` timestamp, not "now".

        Raises :class:`olympus_sdk.errors.FirebaseUidAlreadyLinked` (409) if
        the Firebase UID is already bound to a different Olympus user in the
        caller's tenant.
        """
        data = self._http.post(
            "/auth/firebase/link",
            json={"firebase_id_token": firebase_id_token},
        )
        return FirebaseLinkResult.from_dict(data)

    def me(self) -> User:
        """Get the currently authenticated user profile."""
        data = self._http.get("/auth/me")
        return User.from_dict(data)

    def refresh(self, refresh_token: str) -> AuthSession:
        """Refresh the access token using a refresh token.

        Broadcasts :class:`SessionRefreshed` to :meth:`session_events`
        subscribers on success.
        """
        data = self._http.post("/auth/refresh", json={"refresh_token": refresh_token})
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return self._capture_session(session, event="refreshed")

    def logout(self) -> None:
        """Log out the current session.

        Cancels any running silent-refresh task, clears the HTTP client's
        access token, and emits :class:`SessionLoggedOut` to subscribers.
        The server-side ``/auth/logout`` call is best-effort: a failed
        network request still tears down local state and emits the event.
        """
        self._cancel_refresh_task()
        try:
            self._http.post("/auth/logout")
        finally:
            self._http.clear_access_token()
            self._current_session = None
            self._emit(SessionLoggedOut())

    def create_user(
        self,
        *,
        name: str,
        email: str,
        role: str,
        password: str | None = None,
    ) -> User:
        """Create a new user on the platform."""
        payload: dict[str, str] = {"name": name, "email": email, "role": role}
        if password is not None:
            payload["password"] = password
        data = self._http.post("/platform/users", json=payload)
        return User.from_dict(data)

    def assign_role(self, user_id: str, role: str) -> None:
        """Assign a role to a user."""
        self._http.post(f"/platform/users/{user_id}/roles", json={"role": role})

    def check_permission(self, user_id: str, permission: str) -> bool:
        """Check whether a user has a specific permission."""
        data = self._http.get(
            f"/platform/users/{user_id}/permissions/check",
            params={"permission": permission},
        )
        return bool(data.get("allowed", False))

    def create_api_key(self, name: str, scopes: list[str]) -> ApiKey:
        """Create a new API key for programmatic access."""
        data = self._http.post(
            "/platform/tenants/me/api-keys",
            json={"name": name, "scopes": scopes},
        )
        return ApiKey.from_dict(data)

    def revoke_api_key(self, key_id: str) -> None:
        """Revoke an existing API key."""
        self._http.delete(f"/platform/tenants/me/api-keys/{key_id}")

    # ------------------------------------------------------------------
    # Silent token refresh + session event stream (#3403 §1.4 / #3412)
    # ------------------------------------------------------------------

    async def session_events(self) -> AsyncIterator[SessionEvent]:
        """Async generator yielding :class:`SessionEvent` transitions.

        Each call returns a fresh, independent subscription. Events are
        delivered in order they are emitted. Consumers can drive UI state,
        logging, or test orchestration::

            async for event in auth.session_events():
                match event:
                    case SessionLoggedIn(session=s):
                        ...
                    case SessionExpired(reason=r):
                        ...

        Must be awaited from an asyncio context (a running event loop).
        The underlying :class:`asyncio.Queue` is created on entry and
        bound to the caller's loop — cross-thread subscription is not
        supported.
        """
        queue: asyncio.Queue[SessionEvent] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        entry = (queue, loop)
        self._subscribers.add(entry)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self._subscribers.discard(entry)

    def start_silent_refresh(
        self,
        refresh_margin: float = DEFAULT_REFRESH_MARGIN_SECONDS,
    ) -> SilentRefreshHandle:
        """Start a background task that refreshes the access token before TTL.

        The task decodes the JWT ``exp`` claim and sleeps until
        ``exp - refresh_margin`` seconds from now, then calls
        :meth:`refresh` with the session's ``refresh_token``. On success
        the timer reschedules against the fresh token. On failure the
        session is cleared and :class:`SessionExpired` is emitted.

        Idempotent: if a prior task is running it is cancelled (no
        :class:`SessionLoggedOut` emitted — cancellation is silent) and a
        new one is scheduled.

        **Requires a running asyncio loop**: call this from ``async``
        code or after ``asyncio.run`` has started the loop.

        :param refresh_margin: seconds before JWT ``exp`` to fire the
            refresh. Defaults to :data:`DEFAULT_REFRESH_MARGIN_SECONDS`
            (60s). Values < 0 are clamped to 0.
        :returns: a :class:`SilentRefreshHandle`. Keep a reference if you
            plan to cancel manually; otherwise rely on
            :meth:`stop_silent_refresh` or :meth:`logout`.
        """
        self._refresh_margin = max(0.0, float(refresh_margin))
        # Cancel any prior task (idempotent) — but do NOT emit.
        self._cancel_refresh_task()
        loop = asyncio.get_running_loop()
        task = loop.create_task(self._silent_refresh_loop())
        self._refresh_task = task
        self._refresh_handle = SilentRefreshHandle(task)
        return self._refresh_handle

    def stop_silent_refresh(self) -> None:
        """Cancel the background silent-refresh task if one is running.

        No-op when no task is active. Does NOT emit
        :class:`SessionLoggedOut` — use :meth:`logout` for that.
        """
        self._cancel_refresh_task()

    def _cancel_refresh_task(self) -> None:
        """Cancel the refresh task without emitting a logout event."""
        handle = self._refresh_handle
        task = self._refresh_task
        self._refresh_handle = None
        self._refresh_task = None
        if handle is not None:
            handle.cancel()
        elif task is not None and not task.done():
            task.cancel()

    async def _silent_refresh_loop(self) -> None:
        """Background loop: sleep → refresh → reschedule; handles failure."""
        try:
            while True:
                session = self._current_session
                if session is None:
                    # Nothing to refresh — nothing scheduled us with a valid
                    # session. Exit quietly; consumers will restart when
                    # login is called.
                    return
                refresh_token = session.refresh_token
                if not refresh_token:
                    self._handle_refresh_failure("no refresh token")
                    return
                delay = self._compute_refresh_delay(session.access_token)
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    raise
                # After sleep, double-check the session didn't get cleared.
                current = self._current_session
                if current is None:
                    return
                token = current.refresh_token
                if not token:
                    self._handle_refresh_failure("no refresh token")
                    return
                try:
                    # httpx.Client is sync — run the POST off the loop thread
                    # so a slow server doesn't stall the event loop.
                    await asyncio.to_thread(self.refresh, token)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    self._handle_refresh_failure(f"refresh failed: {exc!s}")
                    return
                # Loop to reschedule against the new token.
        except asyncio.CancelledError:
            # Silent cancellation — don't emit anything.
            return

    def _compute_refresh_delay(self, access_token: str) -> float:
        """Compute seconds to sleep before firing the next refresh.

        Uses JWT ``exp`` minus ``refresh_margin`` minus current time.
        Falls back to a short delay when ``exp`` is missing — the server
        will 401 soon enough and the failure path will clear state.
        """
        exp = _decode_jwt_exp_seconds(access_token)
        margin = self._refresh_margin
        if exp is None:
            # No exp claim — fall back to a conservative 30s poll. Chosen
            # defensively: we'd rather hit a 401 and recover than leak a
            # timer pinned to a token with no discoverable TTL.
            return 30.0
        now = time.time()
        delay = exp - margin - now
        return max(0.0, delay)

    def _handle_refresh_failure(self, reason: str) -> None:
        """Clear local session state and emit :class:`SessionExpired`."""
        self._current_session = None
        self._http.clear_access_token()
        # Mark handle as stopped; we're exiting the loop.
        handle = self._refresh_handle
        self._refresh_handle = None
        self._refresh_task = None
        if handle is not None:
            # Mark as non-running without cancelling (we're already done).
            handle._cancelled = True  # noqa: SLF001 — internal bookkeeping
        self._emit(SessionExpired(reason=reason))

    def _emit(self, event: SessionEvent) -> None:
        """Broadcast an event to every subscriber; swallow per-sub errors.

        Thread-safe: each subscriber records the loop it was bound to in
        :meth:`session_events`. Emissions from a worker thread (the silent
        refresh POST runs under :func:`asyncio.to_thread`) are marshalled
        onto the subscriber's loop via :meth:`call_soon_threadsafe`. When
        the current thread already owns the loop we skip the round-trip
        and call ``put_nowait`` directly.
        """
        if not self._subscribers:
            return
        # Iterate over a snapshot so subscribers can unsubscribe during
        # iteration without mutating our view. A full or closed queue must
        # not break the refresh loop or other subscribers — drop the event
        # for this sub and keep going.
        for queue, loop in list(self._subscribers):
            with contextlib.suppress(Exception):
                try:
                    running = asyncio.get_running_loop()
                except RuntimeError:
                    running = None
                if running is loop:
                    queue.put_nowait(event)
                else:
                    loop.call_soon_threadsafe(queue.put_nowait, event)
