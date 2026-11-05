# Completion plan (picked up 5 Nov 2026 after Codex session stopped)

## Where the Codex session stopped

| Area | State | Verified 5 Nov 2026 |
|---|---|---|
| Backend `services/api` (FastAPI, Alembic, 2 migrations) | Identity (staff + student Google), menu seed, stations, queue/events, pickup lookup, per-line handover, cancellation domain, exceptions, student cart | `pytest`: 49 passed, 3 skipped (Postgres race tests need `TEST_DATABASE_URL`) |
| Staff web `apps/canteen-web` (React/Vite) | Login, queue, pickup, menu variants, stations, sessions, exceptions | `npm test`: 3 passed |
| Student Android `apps/student-android` | **Uncommitted** scaffold: Gradle files + one static `MainActivity` sign-in screen. No wrapper, no networking, no Google sign-in | Last build **failed: "not enough space on the disk"**. V: is a 2 GB drive; Android/Gradle caches need several GB |
| Git | Last commit `e3bb891` (student identity + cart). `.gitignore` edit and the Android scaffold are not committed | — |

Nothing for checkout, payment, reviews, notifications, reports or deployment exists yet.

## Step 0: unblock the environment — DONE 5 Nov 2026

Result: Gradle cache stays in `%USERPROFILE%\.gradle` on C:, wrapper 8.11.1 added, missing
Kotlin Compose compiler plugin added, `assembleDebug` succeeds (12 MB debug APK). Bundled Gradle
copy and test leftovers deleted (V: now 1.7 GB free). Original steps:

1. Move Gradle off V:. Set `GRADLE_USER_HOME=C:\gradle-home` (or move the repo to C:). Delete
   `apps/student-android/.gradle` and the partial build output.
2. Add a Gradle wrapper (`gradle wrapper --gradle-version 8.11.1`) so `.gradle-tooling/` and the
   131 MB `.gradle-tooling.zip` can be deleted (both already gitignored).
3. Clean test leftovers: `services/api/.test-*`, `migration-*.db` (add them to `.gitignore`).
4. Confirm `assembleDebug` passes with the Android SDK at `%LOCALAPPDATA%\Android\Sdk`, then commit
   the scaffold.

## Phases

Each phase ends with tests green, docs updated (`api.md`, `database.md`,
`implementation-progress.md`) and its own commit.

### Phase 1: checkout and orders (backend) — DONE 5 Nov 2026 (dashboard hours UI pending)
- Operating schedule per canteen (open/closed, hours); checkout refused when closed or unapproved.
- `POST /student/checkout`: freeze the cart into an immutable order with price snapshots, revalidating
  price, availability and station. Order status `PENDING_PAYMENT`. Idempotency key.
- Student order history/detail endpoints showing per-line, per-station collection state.
- Tests: price changed mid-checkout, item disabled, closed canteen, duplicate submit.

### Phase 2: payments (sandbox only)
- Choose the gateway (Razorpay, Cashfree or PhonePe PG; **owner decision**). Build a `PaymentProvider`
  interface with a fake adapter for tests and one real sandbox adapter.
- Merchant config per canteen (non-secret metadata in DB, secrets in env/secret store, never shown).
- Create a gateway order, then mark the order paid **only** on a signature-verified webhook or a
  server-side status check. Replay-safe (unique provider event ID).
- On payment: issue the six-digit code (HMAC digest for lookup, encrypted copy so the student can see
  it again), create station queue lines, emit queue events.
- Reconciliation job for orders stuck in `PENDING_PAYMENT`.
- Tests: webhook replay, bad signature, amount mismatch, late webhook after cancel.

### Phase 3: cancellation and refunds
- Connect the existing five-minute cancellation service to the student API.
- Refund through the provider; status changes to `REFUNDED` only on gateway confirmation (webhook or poll).
- Admin-initiated refund for its own canteen only. Partial handover stays in the exception workflow;
  the partial-refund policy needs **owner sign-off** before financial resolution is enabled.

### Phase 4: student Android app
- Structure: Compose + Navigation, ViewModel, Retrofit/OkHttp + kotlinx.serialization, DataStore +
  Android Keystore (EncryptedSharedPreferences replacement) for tokens with a refresh interceptor.
- Screens, using `design-references/student-app-mockup.jpg` as the visual target:
  Google sign-in (Credential Manager) → institute pick (remembered) → canteens → menu with
  ratings → item detail → cart → checkout/payment SDK → order status with pickup code and remaining
  stations → history/receipts → cancel within 5 min → notifications inbox.
- Release signing via `keystore.properties` (gitignored), R8 on, debug/release `apiBaseUrl`.
- Unit tests (ViewModels, token refresh) and a Compose UI smoke test. Android build job in CI.

### Phase 5: reviews and moderation
- Review allowed only on collected items, 1–5 stars with text and up to N photos.
- Secure upload: type/size checks, re-encode, strip EXIF, random object keys, local disk in dev and S3-compatible storage in prod.
- Abuse reports: distinct reporters; auto-hide after threshold (default 3, configurable); admin
  restore/reject with audit. Deterministic rating aggregate on menu cards.
- Admin moderation page in the web dashboard.

### Phase 6: notifications, receipts, reports
- In-app notification table plus student inbox (payment, cancellation, refund, ready/partial). No OS push.
- Receipt endpoint and screen from the order snapshot.
- Admin reports: daily/weekly/monthly and date range, item-wise sales, gross/refunds/net. Web pages.
- Merchant-config request screen in the web dashboard (metadata only).

### Phase 7: hardening and release
- Accessibility pass (web and Android), load test of queue/pickup/webhook paths, rate limits review.
- Production Docker image, `infra/compose.yml` for staging, Postgres backup plus a **restore drill**,
  structured logs, health and metrics, error alerting.
- Update `PRODUCTION_READINESS.md` checklist with evidence.

## External blockers (need you, not code)
- Gateway choice, sandbox keys; later, merchant accounts and KYC for COE and IOIT.
- Google Cloud OAuth client (Android SHA-1 + web client ID) for real sign-in.
- Verified prices for the 5 unknown IOIT items and the station mapping for every item (staff do this in the dashboard).
- Partial-refund policy approval. College/canteen authorization before any live money.
- Staging host choice (any paid hosting needs your approval).

## Suggested order and size
Step 0 → 1 → 2 (fake adapter first, real sandbox once keys exist) → 4 (Android can start against
Phase 1 endpoints in parallel) → 3 → 5 → 6 → 7. Phases 1–3 are the critical path to a first
end-to-end sandbox order.
