"""Main entry point for the Olympus Cloud SDK.

Provides typed access to all platform services. Create a single instance
per application::

    from olympus_sdk import OlympusClient

    oc = OlympusClient(app_id="com.my-restaurant", api_key="oc_live_...")

    # Authenticate
    session = oc.auth.login("user@example.com", "password")

    # Create an order
    order = oc.commerce.create_order(
        items=[{"catalog_id": "burger-01", "qty": 2, "price": 1299}],
        source="pos",
    )

    # Ask AI
    answer = oc.ai.query("What sold best this week?")
"""

from __future__ import annotations

from olympus_sdk.config import OlympusConfig
from olympus_sdk.http import OlympusHttpClient
from olympus_sdk.services.admin_billing import AdminBillingService
from olympus_sdk.services.admin_cpaas import AdminCpaasService
from olympus_sdk.services.admin_ether import AdminEtherService
from olympus_sdk.services.admin_gating import AdminGatingService
from olympus_sdk.services.agent_workflows import AgentWorkflowsService
from olympus_sdk.services.ai import AiService
from olympus_sdk.services.apps import AppsService
from olympus_sdk.services.auth import AuthService
from olympus_sdk.services.billing import BillingService
from olympus_sdk.services.commerce import CommerceService
from olympus_sdk.services.compliance import ComplianceService
from olympus_sdk.services.connect import ConnectService
from olympus_sdk.services.consent import ConsentService
from olympus_sdk.services.data import DataService
from olympus_sdk.services.devices import DevicesService
from olympus_sdk.services.enterprise_context import EnterpriseContextService
from olympus_sdk.services.events import EventsService
from olympus_sdk.services.gating import GatingService
from olympus_sdk.services.governance import GovernanceService
from olympus_sdk.services.identity import IdentityService
from olympus_sdk.services.marketplace import MarketplaceService
from olympus_sdk.services.messages import MessagesService
from olympus_sdk.services.notify import NotifyService
from olympus_sdk.services.observe import ObserveService
from olympus_sdk.services.pay import PayService
from olympus_sdk.services.smart_home import SmartHomeService
from olympus_sdk.services.sms import SmsService
from olympus_sdk.services.storage import StorageService
from olympus_sdk.services.tenant import TenantService
from olympus_sdk.services.tuning import TuningService
from olympus_sdk.services.voice import VoiceService
from olympus_sdk.services.voice_orders import VoiceOrdersService


class OlympusClient:
    """Main entry point for the Olympus Cloud SDK.

    Provides typed access to all 13 platform services via lazy-initialized
    property accessors.
    """

    def __init__(
        self,
        *,
        app_id: str,
        api_key: str,
        config: OlympusConfig | None = None,
    ) -> None:
        """Create a client for production.

        If a *config* is not provided, one is constructed from *app_id* and
        *api_key* using the default production environment.
        """
        self._config = config or OlympusConfig(app_id=app_id, api_key=api_key)
        self._http = OlympusHttpClient(self._config)

        # Lazy-initialized service singletons
        self._auth: AuthService | None = None
        self._commerce: CommerceService | None = None
        self._ai: AiService | None = None
        self._pay: PayService | None = None
        self._notify: NotifyService | None = None
        self._events: EventsService | None = None
        self._data: DataService | None = None
        self._storage: StorageService | None = None
        self._marketplace: MarketplaceService | None = None
        self._billing: BillingService | None = None
        self._gating: GatingService | None = None
        self._devices: DevicesService | None = None
        self._observe: ObserveService | None = None
        self._agent_workflows: AgentWorkflowsService | None = None
        self._enterprise_context: EnterpriseContextService | None = None
        self._messages: MessagesService | None = None
        self._voice_orders: VoiceOrdersService | None = None
        self._admin_ether: AdminEtherService | None = None
        self._admin_cpaas: AdminCpaasService | None = None
        self._admin_billing: AdminBillingService | None = None
        self._admin_gating: AdminGatingService | None = None
        self._tuning: TuningService | None = None
        self._voice: VoiceService | None = None
        self._connect: ConnectService | None = None
        self._consent: ConsentService | None = None
        self._governance: GovernanceService | None = None
        self._identity: IdentityService | None = None
        self._smart_home: SmartHomeService | None = None
        self._sms: SmsService | None = None
        self._tenant: TenantService | None = None
        self._apps: AppsService | None = None
        self._compliance: ComplianceService | None = None
        # Lazy-decoded scope bitset cache keyed by access token.
        self._cached_bitset_bytes: bytes | None = None
        self._cached_bitset_for_token: str | None = None

    @classmethod
    def from_config(cls, config: OlympusConfig) -> OlympusClient:
        """Create a client from a pre-built config (sandbox, dev, etc.)."""
        return cls(app_id=config.app_id, api_key=config.api_key, config=config)

    # ------------------------------------------------------------------
    # Service accessors (lazy-initialized singletons)
    # ------------------------------------------------------------------

    @property
    def auth(self) -> AuthService:
        """Authentication, user management, and API keys."""
        if self._auth is None:
            self._auth = AuthService(self._http)
        return self._auth

    @property
    def commerce(self) -> CommerceService:
        """Orders, catalog, and commerce operations."""
        if self._commerce is None:
            self._commerce = CommerceService(self._http)
        return self._commerce

    @property
    def ai(self) -> AiService:
        """AI inference, agents, embeddings, and NLP."""
        if self._ai is None:
            self._ai = AiService(self._http)
        return self._ai

    @property
    def pay(self) -> PayService:
        """Payments, refunds, balance, and payouts."""
        if self._pay is None:
            self._pay = PayService(self._http)
        return self._pay

    @property
    def notify(self) -> NotifyService:
        """Push, SMS, email, Slack, and in-app notifications."""
        if self._notify is None:
            self._notify = NotifyService(self._http)
        return self._notify

    @property
    def events(self) -> EventsService:
        """Real-time events and webhook management."""
        if self._events is None:
            self._events = EventsService(self._http)
        return self._events

    @property
    def data(self) -> DataService:
        """Data query, CRUD, and search."""
        if self._data is None:
            self._data = DataService(self._http)
        return self._data

    @property
    def storage(self) -> StorageService:
        """File storage (upload, download, presign)."""
        if self._storage is None:
            self._storage = StorageService(self._http)
        return self._storage

    @property
    def marketplace(self) -> MarketplaceService:
        """Marketplace: discover, install, and manage apps."""
        if self._marketplace is None:
            self._marketplace = MarketplaceService(self._http)
        return self._marketplace

    @property
    def billing(self) -> BillingService:
        """Subscription billing, invoices, and usage."""
        if self._billing is None:
            self._billing = BillingService(self._http)
        return self._billing

    @property
    def gating(self) -> GatingService:
        """Feature gating and policy evaluation."""
        if self._gating is None:
            self._gating = GatingService(self._http)
        return self._gating

    @property
    def devices(self) -> DevicesService:
        """Device management (MDM): enrollment, kiosk, updates, wipe."""
        if self._devices is None:
            self._devices = DevicesService(self._http)
        return self._devices

    @property
    def observe(self) -> ObserveService:
        """Client-side observability: events, errors, traces."""
        if self._observe is None:
            self._observe = ObserveService(self._http)
        return self._observe

    @property
    def agent_workflows(self) -> AgentWorkflowsService:
        """AI Agent Workflow Orchestration (#2915) — tenant-scoped multi-agent
        DAG pipelines with cron/event triggers, capability routing, billing.
        """
        if self._agent_workflows is None:
            self._agent_workflows = AgentWorkflowsService(self._http)
        return self._agent_workflows

    @property
    def enterprise_context(self) -> EnterpriseContextService:
        """Enterprise Context (#2993) — Company 360 assembly for AI agents.

        Returns complete tenant context (brand, locations, menu, specials,
        FAQs, upsells, inventory, caller profile) in a single call.
        """
        if self._enterprise_context is None:
            self._enterprise_context = EnterpriseContextService(self._http)
        return self._enterprise_context

    @property
    def messages(self) -> MessagesService:
        """Message queue (#2997) — department-routed messages from AI agents.

        Queue messages for business departments (manager, catering, sales,
        etc.) with notification dispatch and escalation rules.
        """
        if self._messages is None:
            self._messages = MessagesService(self._http)
        return self._messages

    @property
    def voice_orders(self) -> VoiceOrdersService:
        """Voice orders (#2999) — phone order placement with POS push.

        Create, track, and push voice-collected orders to POS systems
        (Toast, Square, Clover) with price validation.
        """
        if self._voice_orders is None:
            self._voice_orders = VoiceOrdersService(self._http)
        return self._voice_orders

    @property
    def admin_ether(self) -> AdminEtherService:
        """Ether AI model catalog admin -- CRUD models, tiers, catalog reload."""
        if self._admin_ether is None:
            self._admin_ether = AdminEtherService(self._http)
        return self._admin_ether

    @property
    def admin_cpaas(self) -> AdminCpaasService:
        """CPaaS provider admin -- provider preferences and health monitoring."""
        if self._admin_cpaas is None:
            self._admin_cpaas = AdminCpaasService(self._http)
        return self._admin_cpaas

    @property
    def admin_billing(self) -> AdminBillingService:
        """Billing plan catalog admin -- plans, add-ons, minute packs, usage."""
        if self._admin_billing is None:
            self._admin_billing = AdminBillingService(self._http)
        return self._admin_billing

    @property
    def admin_gating(self) -> AdminGatingService:
        """Feature flag admin -- define features, plan assignment, resource limits."""
        if self._admin_gating is None:
            self._admin_gating = AdminGatingService(self._http)
        return self._admin_gating

    @property
    def tuning(self) -> TuningService:
        """AI tuning jobs, synthetic persona generation, and chaos audio simulation."""
        if self._tuning is None:
            self._tuning = TuningService(self._http)
        return self._tuning

    @property
    def voice(self) -> VoiceService:
        """Voice AI: caller profiles, escalation, business hours, and V2-005
        cascade resolver (#3162). v0.4.0."""
        if self._voice is None:
            self._voice = VoiceService(self._http)
        return self._voice

    @property
    def connect(self) -> ConnectService:
        """Marketing funnel + pre-conversion lead capture (#3108). v0.4.0."""
        if self._connect is None:
            self._connect = ConnectService(self._http)
        return self._connect

    @property
    def consent(self) -> ConsentService:
        """App-scoped permissions consent surface (v2.0.0 — #3254 / #3234 epic).

        See docs/platform/APP-SCOPED-PERMISSIONS.md §6.
        """
        if self._consent is None:
            self._consent = ConsentService(self._http)
        return self._consent

    @property
    def governance(self) -> GovernanceService:
        """Policy exception framework (v2.0.0 — #3254 / #3259).

        Narrow scope: ``session_ttl_role_ceiling`` and ``grace_policy_category``
        only. See §17 of APP-SCOPED-PERMISSIONS.md.
        """
        if self._governance is None:
            self._governance = GovernanceService(self._http)
        return self._governance

    @property
    def identity(self) -> IdentityService:
        """Olympus ID — global cross-tenant identity, Firebase federation,
        age-verification (Document AI), and passphrase management
        (v0.5.0 — #3216 Wave 2).
        """
        if self._identity is None:
            self._identity = IdentityService(self._http)
        return self._identity

    @property
    def smart_home(self) -> SmartHomeService:
        """Smart-home integration — platforms, devices, rooms, scenes,
        automations (v0.5.0 — #3216 Wave 2).
        """
        if self._smart_home is None:
            self._smart_home = SmartHomeService(self._http)
        return self._smart_home

    @property
    def sms(self) -> SmsService:
        """SMS messaging — outbound SMS (voice-platform + CPaaS), conversation
        history, and provider delivery status (v0.5.0 — #3216 Wave 2).
        """
        if self._sms is None:
            self._sms = SmsService(self._http)
        return self._sms

    @property
    def tenant(self) -> TenantService:
        """Tenant lifecycle — ``/tenant/*`` surface (create, current, update,
        retire, unretire, my_tenants, switch_tenant). Shipped in #3403 §2
        via PR #3410.
        """
        if self._tenant is None:
            self._tenant = TenantService(self._http)
        return self._tenant

    @property
    def apps(self) -> AppsService:
        """Apps ceremony — canonical ``/apps/*`` surface (#3413 §3).

        ``install`` / ``list_installed`` / ``uninstall`` / ``get_manifest``
        plus the three pending-install endpoints (``get`` / ``approve`` /
        ``deny``) that drive the tenant_admin consent screen. Shipped in
        olympus-cloud-gcp#3422.
        """
        if self._apps is None:
            self._apps = AppsService(self._http)
        return self._apps

    @property
    def compliance(self) -> ComplianceService:
        """Compliance — audit, GDPR data requests, and dram-shop event
        recording (#3316).

        Cross-app surface used by both BarOS and PizzaOS for ID-check /
        refused-service / over-serve audit trails plus the rules-lookup
        API shipped in olympus-cloud-gcp PRs #3525 + #3530.
        """
        if self._compliance is None:
            self._compliance = ComplianceService(self._http)
        return self._compliance

    # ------------------------------------------------------------------
    # App-scoped token management (§4.5 dual-JWT flow)
    # ------------------------------------------------------------------

    def set_app_token(self, token: str) -> None:
        """Attach the App JWT obtained from ``/auth/app-tokens/mint``.

        Forwarded on every request as ``X-App-Token`` alongside the user JWT
        Authorization header per the dual-JWT flow (§4.5).
        """
        self._http.set_app_token(token)
        self._invalidate_bitset_cache()

    def clear_app_token(self) -> None:
        """Clear the app token (e.g. on logout)."""
        self._http.clear_app_token()
        self._invalidate_bitset_cache()

    def set_access_token(self, token: str) -> None:
        """Replace the active access token; invalidates cached bitset decode."""
        self._http.set_access_token(token)
        self._invalidate_bitset_cache()

    def on_catalog_stale(self, handler) -> None:
        """Register a handler for the §4.7 rolling-window stale-catalog signal.

        Called when the server returns ``X-Olympus-Catalog-Stale: true``.
        Consumers should schedule a background refresh at a randomized 0–15
        minute offset to smear token-refresh traffic.
        """
        self._http.on_catalog_stale(handler)

    def has_scope_bit(self, bit_id: int) -> bool:
        """Constant-time bitmask check against decoded ``app_scopes_bitset``.

        Returns ``False`` when no token set, for platform-shell tokens without
        a bitset, when ``bit_id`` is negative, or when ``bit_id`` is out of
        range. Used by SDK service methods to fail-fast with a typed
        :class:`ScopeDenied` BEFORE the HTTP call.
        """
        if bit_id < 0:
            return False
        bitset = self._decode_bitset_once()
        if bitset is None:
            return False
        byte_idx = bit_id // 8
        bit_idx = bit_id % 8
        if byte_idx >= len(bitset):
            return False
        return (bitset[byte_idx] & (1 << bit_idx)) != 0

    def is_app_scoped(self) -> bool:
        """True when the current access token carries an ``app_id`` claim."""
        claims = self._decoded_claims()
        return bool(claims and claims.get("app_id"))

    def _invalidate_bitset_cache(self) -> None:
        self._cached_bitset_bytes = None
        self._cached_bitset_for_token = None

    def _decoded_claims(self) -> dict | None:
        import base64
        import json

        token = self._http.get_access_token()
        if not token:
            return None
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        try:
            decoded = base64.urlsafe_b64decode(payload + padding)
            return json.loads(decoded.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return None

    def _decode_bitset_once(self) -> bytes | None:
        import base64

        token = self._http.get_access_token()
        if not token:
            return None
        if self._cached_bitset_for_token == token and self._cached_bitset_bytes is not None:
            return self._cached_bitset_bytes
        claims = self._decoded_claims()
        bitset = claims.get("app_scopes_bitset") if claims else None
        if not isinstance(bitset, str) or not bitset:
            self._cached_bitset_bytes = b""
            self._cached_bitset_for_token = token
            return self._cached_bitset_bytes
        padding = "=" * (-len(bitset) % 4)
        try:
            decoded = base64.urlsafe_b64decode(bitset + padding)
            self._cached_bitset_bytes = decoded
            self._cached_bitset_for_token = token
            return decoded
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # Configuration accessors
    # ------------------------------------------------------------------

    @property
    def config(self) -> OlympusConfig:
        """The active SDK configuration."""
        return self._config

    @property
    def http_client(self) -> OlympusHttpClient:
        """The underlying HTTP client (for advanced usage)."""
        return self._http

    def close(self) -> None:
        """Close the underlying HTTP transport."""
        self._http.close()

    def __enter__(self) -> OlympusClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
