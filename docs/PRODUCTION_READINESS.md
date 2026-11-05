# Production readiness and authorization gates

Production-grade code and staging verification are the target, but **live production operation cannot be claimed** before real organizational approvals and working gateway accounts. Never collect actual student payments without authorization.

## Delivery gates
- Android APK signed for release (signing keys provided out of band), reproducible builds and supported-device testing.
- Admin and counter interfaces: accessible, stable sessions, precise permissions, reconnect recovery, multi-user concurrency and on-device performance at peak volume.
- Database: PostgreSQL migrations, seed idempotency, transaction/financial consistency, secure backups and tested restoration.
- Payments: approved per-canteen merchant accounts, verified provider webhooks and refunds, reconciliation for delayed/duplicate payments, verified KYC and legal settlement ownership. Backend does not treat free-form UPI ID edits as gateway settlement changes.
- Security: rate limits, audit logs, encrypted secrets, account/device revocation, CSRF for web, safe image upload, privacy/retention policy, incident response and secret-rotation guidance.
- Observability: health/readiness checks, structured redacted logs, error tracking, uptime alerts, load-testing results, backups and documented recovery targets.
- Canteen operations: staff training, station map sign-off, cancellation vs partially handed-over order policy sign-off, confirmed default menu prices and product images rights.
- Governance: written campus/canteen approval, ownership/maintenance agreement, merchant onboarding, tax/invoicing requirements and hosting/payout access transferred appropriately.

## Deployment boundaries
Codex may implement, test, create staging scripts, build artifacts and push verified source to repository. It must not charge live UPI accounts, activate production payouts, deploy publicly, spend money or assume institutional permission without explicit approval. Blocked production launch must be reported distinctly from finished development.

## Status against the gates — 5 November 2026

Legend: **Done** (implemented and verified, evidence given), **Partial**, **Open** (not started
or needs people/approvals outside the code).

| Gate | Status | Evidence / what is missing |
|---|---|---|
| Release-signed Android APK | Partial | `assembleRelease` with R8 builds; signing reads `keystore.properties` (not provided). Not run on real devices; only the sign-in screen was seen on an emulator. |
| Admin/counter UI: permissions, sessions, reconnect | Partial | Station/admin authorization and session revocation are covered by API tests; SSE reconnect with polling fallback exists. No multi-device field test yet. |
| Accessibility | Partial | Web: labelled inputs, visible focus outlines, `lang`, alert/status roles, keyboard-operable buttons. Android: content descriptions on icon buttons, pickup code read digit by digit, Material 3 enforces 48 dp touch targets. No screen-reader session or contrast audit with real users yet. |
| PostgreSQL migrations and seed | Done | Locally on PostgreSQL 18: `alembic upgrade head` + `alembic check` clean; seed inserted 127 items, re-run inserted 0. Also in CI. |
| Concurrency (pickup, cancel vs collect, double checkout, payment races) | Done | 6 PostgreSQL race tests passed locally on PostgreSQL 18 and run in CI. |
| Backups and tested restoration | Done (drill) / Open (schedule) | Restore drill run locally: pg_dump → restore into a separate database → `python -m app.ops.verify` passed on both with identical counts. Repeated in CI (`restore-drill` job). `infra/scripts/backup.sh` and `restore-drill.sh` exist. Backup schedule, off-site copy, retention, RPO/RTO and owner not yet decided. |
| Payments: verified webhooks, refunds, reconciliation | Done in code / Open externally | Signature-verified, replay-safe webhooks; server-side payment fetch; refund de-duplication; reconciliation job. Tested against a fake Razorpay API only. Needs Razorpay test keys for a sandbox run, then approved per-canteen merchant accounts and KYC. |
| Security: rate limits, audit, secrets, CSRF, uploads | Partial | Rate limits on login, refresh, pickup, uploads and reports; audit events; Origin checks for cookie writes; secrets only in env; uploads re-encoded. Behind a proxy, set `FORWARDED_ALLOW_IPS` so limits see real client IPs. Privacy/retention policy, incident response and secret-rotation runbook still to write. |
| Observability | Partial | `/health` (GET/HEAD), `/ready` (DB), JSON access logs with request ids and no bodies/tokens/codes, generic 500s with request id, integrity check `app.ops.verify`. No error tracker or uptime alerting configured (needs a chosen service). |
| Load testing | Partial | `infra/loadtest/loadtest.py`; 30-user, 30 s smoke on a 6 GB Windows laptop against PostgreSQL: 639 requests, 0 errors, p50 0.4–0.8 s, p95 2.4–3.2 s. Laptop numbers are not a capacity result; repeat on staging hardware. |
| Production images and staging stack | Done (built) / Open (hosted) | `services/api/Dockerfile` (non-root, health check) and `apps/canteen-web/Dockerfile` (nginx, CSP) built and run together locally; `infra/compose.staging.yml` validated. Not deployed anywhere: hosting choice and HTTPS domain need approval. |
| Canteen operations sign-off | Open | Station mapping, menu prices (5 IOIT prices filled by owner, still unverified in the app), partial-refund policy and staff training. |
| Governance | Open | Written campus/canteen approval, ownership and maintenance agreement, merchant onboarding, tax/invoicing, hosting and payout access. |
