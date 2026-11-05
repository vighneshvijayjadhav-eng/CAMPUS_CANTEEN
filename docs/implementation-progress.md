# Implementation progress

## Audit baseline — 18 October 2026

Inspected local main and fetched origin/main at `8567618`. The tracked repository contained
instructions, six specification documents, four reference images (two duplicate pairs),
the original workbook, its draft transcription and a handoff README. It contained no
Android, web or backend implementation, migration, dependency lock or test suite.
No existing application code was removed, replaced or reset. Existing history is preserved.

The 18 October revisions supersede whole-order redemption and two-login assumptions.
The approved stack remains unchanged. No destructive migration is needed for this baseline.

## First implementation milestone

Implemented:
- FastAPI module boundaries for identity, menu and order fulfillment, plus shared errors/DB setup.
- PostgreSQL schema migration with canteen/station composite foreign keys, positive prices,
  bounded fulfilled quantities and unique active pickup digests.
- Workbook reader and insert-only seed: 85 IOIT items, 42 COE items, 145 variants total.
  Five IOIT prices were unknown (owner filled them on 5 Nov 2026). All variants start unverified/unavailable/unmapped and
  both canteens unapproved/non-operating. Re-running preserves staff edits. A changed source
  workbook requires explicit source-ID review instead of silently matching shifted rows.
- Provisioned admin/station accounts, Argon2id, hashed opaque access/refresh tokens,
  rotation, 15-minute access, 30-day refresh and 90-day absolute device-session bounds.
  Device revocation and station disabling deny subsequent authenticated requests.
- Read-only, canteen-scoped pickup lookup using HMAC; no code TTL.
- Selected-line/quantity fulfillment with parent row locking, expected fulfilled count,
  request idempotency and actor/session/time audit. Partial collection preserves the code.
- Five-minute cancellation domain service, cancellation queue removal and refund request
  intent. Partial handover creates a separate staff-review exception without refunding goods.
- Admin-only exception contact notes; financial resolution remains disabled pending policy.
- Scoped queue event stream with periodic session checks; dashboard reconnect, polling,
  event deduplication and opt-in sound. Events are refresh hints; queue reads are authoritative.
- Responsive React dashboard for login, queue, pickup, menu variants and station management.

This is a tested foundation milestone, not completion of phases 1–8.

## Verification

Local checks and final CI outcomes are recorded in the delivery message and subsequent entries.
SQLite tests cover domain/API behavior only. PostgreSQL races run only when TEST_DATABASE_URL
is set; CI provisions PostgreSQL 18 and runs migrations, seed replay and concurrent transitions.
Local Docker engine was unavailable. No local PostgreSQL race pass is claimed.

## Student foundation — 31 October 2026

Implemented an additive student identity/catalog/cart increment:
- Approved institute-first discovery and COE/IOIT association during the idempotent workbook seed.
- Google ID-token verification against a configured Android OAuth audience, with any verified
  Google account accepted; persisted opaque, rotating/revocable student device sessions.
- Optional remembered institute selection and a server-side, single-canteen cart. Cart updates
  recheck approval, verified price, availability and active station; totals are server calculated.
- A migration creates institutes, students, student sessions/preferences and carts without
  changing historical fulfillment rows. Existing seed data receives an institute association on
  the next seed run.

This is not checkout or payment: the cart is mutable, no order/payment/pickup code is created,
and no live Google or merchant credential is present in the repository.

## Checkout and orders — 5 November 2026

Implemented (Phase 1 of `docs/COMPLETION_PLAN.md`):
- Canteen operating schedule: admin master switch plus optional weekly India-time hours;
  public listing shows whether a canteen is accepting orders.
- Idempotent student checkout that freezes the cart into an immutable PAYMENT_PENDING order with
  per-line price/name/size/station snapshots, rejecting a changed total, unavailable or archived
  items, inactive stations, closed or unapproved canteens and empty carts.
- Student order history and detail limited to the signed-in student.
- Migration `2520dc960e74` (additive). Android scaffold now builds (`assembleDebug`) with a
  Gradle wrapper.

Verification: `pytest` 64 passed, 5 skipped locally (PostgreSQL race tests, including two new
double-checkout races, run only in CI with TEST_DATABASE_URL). Migration verified by
`alembic upgrade head` + `alembic check` on SQLite only; PostgreSQL migration runs in CI.

Not included: payment, pickup-code issuance and expiry of abandoned PAYMENT_PENDING orders
(Phase 2), student cancellation endpoint (Phase 3), web dashboard UI for hours (follow-up).

## Razorpay payments — 5 November 2026

Implemented (Phase 2): per-canteen merchant accounts (owner CLI, secrets in configuration),
Razorpay order creation, signature-checked app callback followed by a server-side payment fetch,
signature-verified replay-safe webhooks, reconciliation polling, amount checks, flagging of
duplicate captures for refund, and pickup-code issuance (HMAC lookup + AES-GCM recoverable copy)
with a PAID queue event. Live keys are blocked outside an explicitly approved production config.

Verification: `pytest` 76 passed, 6 skipped locally. Payment tests run the real adapter against
a fake Razorpay API (no network); the new PostgreSQL callback/webhook race test runs in CI only.
Not yet exercised against the real Razorpay sandbox: that needs test keys and a public webhook URL.

## Cancellation and refunds — 5 November 2026

Implemented (Phase 3): student cancellation endpoint (five-minute rule; unpaid orders can be
abandoned), admin cancellation with a required note for paid orders with nothing handed over,
full Razorpay refunds with receipt-based de-duplication, refund webhooks and polling, automatic
refunds of duplicate and wrong-amount captures, admin refund list and retry of failed refunds.
Partly collected orders still go to staff review; partial refunds wait for policy approval.

Verification: refund/payment tests run the real adapter against a fake Razorpay API. Full suite
locally: 84 passed, 6 skipped (PostgreSQL). The owner filled the five previously unknown IOIT
prices in the workbook and draft on 5 Nov (Cut Cheese Dosa 70, Loni Spunj Dosa 72, Onion Uttappa
60, Onion Cheese Uttappa 75, Veg Cheese Sandwich 66 rupees). A database already seeded from the
old workbook refuses to re-seed by design until source IDs are reviewed; set the prices there in
the dashboard instead.

## Remaining implementation gates

1. Native Android project, emulator/device tests and release-signing configuration.
2. Native Android client, including secure token storage and actual Google Sign-In integration.
3. ~~Server checkout, operating schedules, price checks~~ (done 5 Nov); checkout/payment linkage.
4. Merchant configurations, real gateway sandbox adapter, webhook verification, payment activation,
   encrypted recoverable code issuance, reconciliation and provider-confirmed refunds.
5. Approved partial-refund/exception resolution policy and corresponding financial transitions.
6. Review eligibility/photos/moderation, rankings, student notifications, receipts and reports.
7. Upload security, permission-confirmed imagery, accessibility/device checks and load tests.
8. Staging/backup restoration drill, monitoring, production approvals and release verification.

No paid service, public deployment, live charge or merchant configuration was activated.
