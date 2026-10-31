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
  Five IOIT prices remain unknown. All variants start unverified/unavailable/unmapped and
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

## Remaining implementation gates

1. Native Android project, emulator/device tests and release-signing configuration.
2. Google token validation, student sessions/preferences and authenticated student order APIs.
3. Server checkout/cart, operating schedules, immutable checkout/payment linkage and price checks.
4. Merchant configurations, real gateway sandbox adapter, webhook verification, payment activation,
   encrypted recoverable code issuance, reconciliation and provider-confirmed refunds.
5. Approved partial-refund/exception resolution policy and corresponding financial transitions.
6. Review eligibility/photos/moderation, rankings, student notifications, receipts and reports.
7. Upload security, permission-confirmed imagery, accessibility/device checks and load tests.
8. Staging/backup restoration drill, monitoring, production approvals and release verification.

No paid service, public deployment, live charge or merchant configuration was activated.
