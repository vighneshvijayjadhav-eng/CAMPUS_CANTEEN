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
