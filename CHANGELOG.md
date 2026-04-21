# Changelog

## 0.5.0 (2026-04-19)

### Wave 2 of the SDK 1.0 Campaign (OlympusCloud/olympus-cloud-gcp#3216)

Mirrors the Dart SDK surface for voice, identity, smart-home, SMS, and
voice-orders so Python callers reach dart parity.

**New services:**

- `client.identity` — Olympus ID (global, cross-tenant identity & Firebase
  federation). Get-or-create identity, tenant link, Document-AI age
  verification (#3009), passphrase set/verify, and signed-upload session.
- `client.smart_home` — Smart-home integration: platforms, devices, rooms,
  scenes (#2569), automations.
- `client.sms` — Outbound SMS via voice-agent configs (`/voice/sms/*`) and
  the unified CPaaS layer (`/cpaas/messages/*`, Telnyx primary + Twilio
  fallback per #2951) with delivery status lookup.

**Rewritten services:**

- `client.voice` — rewritten wholesale against
  `olympus-sdk-dart/lib/src/services/voice_service.dart` for full dart
  parity. 60+ methods now cover agents, V2-005 cascade resolver (#3162),
  voice pool, schedule, provisioning wizard, self-service CRUD, personas,
  templates, ambiance, voice-tuning overrides, workflow templates,
  voicemail, conversations, analytics, campaigns, phone numbers + port-in,
  marketplace voices/packs, calls, speaker, profiles, the edge pipeline
  (`/voice/process`, `/ws/voice`), caller profiles (now at
  `/caller-profiles/{phone}` to match dart), escalation config per agent,
  business hours per agent, and AI-to-AI agent testing (#170).

**Behavioural change (fix):** `VoiceService` is now synchronous, matching
the rest of the SDK. The previous `async def` signatures wrapped blocking
HTTP calls and required callers to `await` dicts through `asyncio.run`.
Callers of the pre-Wave-2 voice surface must drop the `await`. No external
consumer was observed relying on the async facade (Wave 1 shipped the
cascade resolver but only under the broken async signature).

**Existing coverage:**

- `client.voice_orders` — already at dart parity since 0.3.0; Wave 2 adds
  `tests/test_voice_orders.py` fixtures that were missing.

**New models:** `OlympusIdentity`, `IdentityLink` (exported from
`olympus_sdk.models` and the top-level `olympus_sdk` package).

**Tests added:**

- `tests/test_voice.py` — 40+ cases covering every method group in the
  rewritten voice service + error propagation.
- `tests/test_identity.py` — model round-trip + service methods, happy +
  error paths.
- `tests/test_smart_home.py` — envelope unwrapping + URL-escaping +
  command passthrough.
- `tests/test_sms.py` — voice-platform and CPaaS surfaces; verifies
  `from_` → `from` rename on the wire.
- `tests/test_voice_orders.py` — backfill coverage for 0.3.0 service.

`tests/test_voice_v2.py` fixtures updated to the new sync voice surface.

**Quality gates:** `ruff check .` → 0 errors on Wave 2 files;
`pytest` → 205 passed / 0 failed; `bandit -ll` → 0 findings.

## 0.4.0 (2026-04-18)

### Wave 1 of the SDK 1.0 Campaign (OlympusCloud/olympus-cloud-gcp#3216, Wave #3217)

**New services:**

- `client.voice` — Voice AI with V2-005 cascade resolver (#3162).
- `client.connect` — marketing-funnel + pre-conversion lead capture
  (#3108).

**New methods:**

- `await client.voice.get_effective_config(agent_id)` →
  `VoiceEffectiveConfig`. Backing endpoint
  `GET /api/v1/voice-agents/configs/{id}/effective-config`.
- `await client.voice.get_pipeline(agent_id)` → `VoicePipeline`.
  Canonical subset for runtimes / provisioners.
- `await client.connect.create_lead(email=..., ...)` →
  `CreateLeadResponse`. Unauthenticated; idempotent on email over 1h.

**New models:** `VoiceEffectiveConfig`, `VoicePipeline`,
`VoiceDefaultsCascade`, `VoiceDefaultsRung`, `UTM`, `CreateLeadResponse`.
All exported from `olympus_sdk.models`.

**Deferred from Wave 1:**

- `client.auth.create_service_token(...)` — endpoint #2848 exists in Rust
  auth but is not routed through the Go gateway. Tracked in platform
  issue OlympusCloud/olympus-cloud-gcp#3220. Wave 1.5.
- Identity / training coverage — Wave 2 per campaign doc §2.

**Tests:** `tests/test_voice_v2.py` — 8/8 passing. Fixtures are real
captures from dev.api.olympuscloud.ai — same as olympus-sdk-dart#8,
olympus-sdk-typescript#1, olympus-sdk-go#1.
