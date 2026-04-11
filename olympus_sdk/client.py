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
from olympus_sdk.services.ai import AiService
from olympus_sdk.services.auth import AuthService
from olympus_sdk.services.billing import BillingService
from olympus_sdk.services.commerce import CommerceService
from olympus_sdk.services.data import DataService
from olympus_sdk.services.devices import DevicesService
from olympus_sdk.services.events import EventsService
from olympus_sdk.services.gating import GatingService
from olympus_sdk.services.marketplace import MarketplaceService
from olympus_sdk.services.notify import NotifyService
from olympus_sdk.services.observe import ObserveService
from olympus_sdk.services.pay import PayService
from olympus_sdk.services.storage import StorageService


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
