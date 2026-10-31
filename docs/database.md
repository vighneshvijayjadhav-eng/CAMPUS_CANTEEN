# Database baseline

Alembic revision `6ee6efb5339d` adds new tables only; no existing user table is dropped.
Apply with DATABASE_URL configured: `uv run alembic upgrade head` from services/api.
The application requires PostgreSQL. SQLite is used only by fast local behavior tests.

Catalog: canteens → stations and menu_items → menu_variants. Category is a display value;
station is an independent tenant-scoped variant assignment. Seed source digest and original
sheet/row/column/raw price are retained. Unknown prices are NULL. Unavailable variants can
be browsed. There is no hard-coded station routing and no Excel upload endpoint.

Identity: staff_accounts → device_sessions. Account role/station constraints distinguish
admins from station operators. Token digests, not tokens, are persisted. Rate counters are
committed independently of failed requests. On PostgreSQL advisory locks serialize each
rate bucket and seed execution. Provisioning never overwrites an existing account.

Fulfillment: orders → order_lines, pickup_credentials, fulfillment_events, order_exceptions
and queue_events. Lines snapshot station name/ID, product, size and charged unit price.
Order-changing services lock the same parent row before reading/modifying lines. Quantity
checks, expected counts and idempotency keys prevent stale/replayed handovers.

Refund request intent is not a payment ledger or a confirmed refund. No gateway/payment
activation is implemented in this milestone. Existing tables will be extended through new
migrations when checkout, merchant and provider integration are implemented.

No pickup expiry field or expiry job exists. Full collection/cancellation deactivates the
credential and clears recoverable ciphertext. Key rotation/issuance is a later payment gate.

Downgrade deliberately refuses destructive deletion. Before any deployed schema rollback,
take a backup, verify restoration and obtain operational approval. For a failed additive
migration prefer a reviewed forward repair.
