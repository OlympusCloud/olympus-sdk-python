"""Olympus Cloud Python SDK.

Official Python client for the Olympus Cloud Platform API.

Usage::

    from olympus_sdk import OlympusClient

    client = OlympusClient(app_id="com.my-restaurant", api_key="oc_live_...")

    # Authenticate
    session = client.auth.login("user@example.com", "password")

    # Create an order
    order = client.commerce.create_order(
        items=[{"catalog_id": "burger-01", "qty": 2, "price": 1299}],
        source="pos",
    )

    # Ask AI
    answer = client.ai.query("What sold best this week?")
"""

from olympus_sdk.client import OlympusClient
from olympus_sdk.config import OlympusConfig, OlympusEnvironment
from olympus_sdk.constants import (
    OLYMPUS_ROLES_ALL,
    OLYMPUS_SCOPES_ALL,
    OlympusRoles,
    OlympusScopes,
)
from olympus_sdk.errors import (
    BillingGraceExceeded,
    ConsentRequired,
    DeviceChanged,
    ExceptionExpired,
    ExceptionRequestError,
    OlympusApiError,
    OlympusNetworkError,
    OlympusScopeRequiredError,
    ScopeDenied,
)
from olympus_sdk.models.apps import (
    AppInstall,
    AppManifest,
    PendingInstall,
    PendingInstallDetail,
)
from olympus_sdk.models.identity import IdentityLink, OlympusIdentity
from olympus_sdk.models.tenant import (
    ExchangedSession,
    InviteHandle,
    Tenant,
    TenantAppInstall,
    TenantFirstAdmin,
    TenantOption,
    TenantProvisionResult,
    TenantUpdate,
)
from olympus_sdk.services.apps import AppsService
from olympus_sdk.services.auth import (
    AuthService,
    SessionEvent,
    SessionExpired,
    SessionLoggedIn,
    SessionLoggedOut,
    SessionRefreshed,
    SilentRefreshHandle,
)
from olympus_sdk.services.consent import ConsentPrompt, ConsentService, Grant
from olympus_sdk.services.governance import (
    ExceptionRequest,
    ExceptionStatus,
    GovernanceService,
    PolicyKey,
    RiskTier,
)
from olympus_sdk.services.identity import IdentityService
from olympus_sdk.services.smart_home import SmartHomeService
from olympus_sdk.services.sms import SmsService
from olympus_sdk.services.tenant import TenantService

__all__ = [
    "OlympusClient",
    "OlympusConfig",
    "OlympusEnvironment",
    "OlympusApiError",
    "OlympusNetworkError",
    # App-scoped permissions v2.0 (olympus-cloud-gcp#3234 / #3254)
    "ConsentService",
    "ConsentPrompt",
    "Grant",
    "GovernanceService",
    "ExceptionRequest",
    "ExceptionStatus",
    "PolicyKey",
    "RiskTier",
    "ConsentRequired",
    "ScopeDenied",
    "BillingGraceExceeded",
    "DeviceChanged",
    "ExceptionRequestError",
    "ExceptionExpired",
    # Client-side scope assertion (olympus-cloud-gcp#3403 §1.2)
    "OlympusScopeRequiredError",
    "OlympusScopes",
    "OlympusRoles",
    "OLYMPUS_SCOPES_ALL",
    "OLYMPUS_ROLES_ALL",
    # Wave 2 — olympus-cloud-gcp#3216 (voice + identity + smart-home + sms)
    "IdentityService",
    "IdentityLink",
    "OlympusIdentity",
    "SmartHomeService",
    "SmsService",
    # Silent token refresh + session event stream (#3403 §1.4 / #3412)
    "AuthService",
    "SessionEvent",
    "SessionLoggedIn",
    "SessionRefreshed",
    "SessionExpired",
    "SessionLoggedOut",
    "SilentRefreshHandle",
    # Tenant lifecycle + identity invites (#3403 §2 + §4.2 / #3410)
    "TenantService",
    "Tenant",
    "TenantFirstAdmin",
    "TenantProvisionResult",
    "TenantUpdate",
    "TenantOption",
    "ExchangedSession",
    "TenantAppInstall",
    "InviteHandle",
    # Apps.install ceremony (#3413 §3 / #3422)
    "AppsService",
    "AppInstall",
    "AppManifest",
    "PendingInstall",
    "PendingInstallDetail",
]

__version__ = "0.5.0"
