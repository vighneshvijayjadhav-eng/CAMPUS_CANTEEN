# Database baseline

Alembic revisions `6ee6efb5339d`, `c4e95a58b9ea` and `2520dc960e74`, `a824997c8e58`, `f162cf38ee04`, `9e348ecd3027`, `189437663676` add tables,
nullable columns and defaulted columns only; no
existing user table is dropped.
Apply with DATABASE_URL configured: `uv run alembic upgrade head` from services/api.
The application requires PostgreSQL. SQLite is used only by fast local behavior tests.

Catalog: canteens → stations and menu_items → menu_variants. Category is a display value;
station is an independent tenant-scoped variant assignment. Seed source digest and original
sheet/row/column/raw price are retained. Unknown prices are NULL. Unavailable variants can
be browsed. There is no hard-coded station routing and no Excel upload endpoint.

Identity: staff_accounts → device_sessions and students → student_sessions. Student Google
subjects and normalized email addresses are unique; opaque token digests, not tokens, are
persisted. student_preferences holds the optional institute selection. Rate counters are
committed independently of failed requests. On PostgreSQL advisory locks serialize each rate
bucket and seed execution. Provisioning never overwrites an existing account.

Discovery/cart: institutes → canteens, with an approval gate at both levels. carts has one
student and one selected canteen; cart_lines use composite foreign keys to prevent a line from
referencing a cart or menu variant in another canteen. Cart rows are mutable pre-payment only;
they are never used as an order record or a source of charged prices.

Checkout/schedule: canteen_hours holds at most one opening window per canteen and weekday
(minutes since midnight, India time). Checkout locks the student's cart row, rechecks every
line, compares the server total with the total the student confirmed, then writes an order
plus line snapshots (including variant_id via a tenant-scoped composite foreign key) and
deletes the cart lines in one transaction. orders.checkout_request_id is unique per student so
retries return the existing order; orders.created_at orders student history.

Fulfillment: orders → order_lines, pickup_credentials, fulfillment_events, order_exceptions
and queue_events. Lines snapshot station name/ID, product, size and charged unit price.
Order-changing services lock the same parent row before reading/modifying lines. Quantity
checks, expected counts and idempotency keys prevent stale/replayed handovers.

Payments: merchant_accounts holds per-canteen Razorpay metadata (key id, test/live mode, at
most one active per canteen); secrets stay in RAZORPAY_CREDENTIALS. Accounts are never repointed,
so payment_attempts (one Razorpay order each, tenant-scoped foreign keys to order and merchant)
keep the account they used. Attempt states: CREATED, CAPTURED, AMOUNT_MISMATCH, FAILED and
CAPTURED_UNAPPLIED (money received for an already-paid order; must be refunded in Phase 3).
payment_webhook_events is the replay guard (account + event id). Capture locks the order, then
the attempt, so a webhook, app callback and reconciliation racing each other activate once.

On capture a random six-digit pickup code is issued: the HMAC digest is stored for counter
lookup, and an AES-GCM copy (key derived from PICKUP_HMAC_KEY via HKDF, order id as associated
data) lets the student app show it again. No expiry field or job exists. Full collection or
cancellation deactivates the credential and clears the ciphertext.

Refunds: one row per full refund of a payment attempt (REQUESTED -> PENDING -> PROCESSED, or
FAILED), with reason (student/staff cancellation, duplicate payment, amount mismatch), who asked,
an optional staff note and Razorpay's refund id. A partial unique index allows only one
non-failed refund per payment attempt. `next_attempt_at` schedules automatic retries of refused
or unsent refunds (index on status + next_attempt_at). The row id is sent to Razorpay as the refund `receipt`, so
reconciliation adopts a refund Razorpay already made instead of creating a second one.
orders.refund_status mirrors cancellation refunds (REQUESTED, PENDING, REFUNDED, FAILED); refunds
of duplicate or wrong-amount captures do not change the order. Partial refunds are not supported
until the partial-handover refund policy is approved.

Reviews: reviews (one per order line, unique; rating 1-5; status VISIBLE, HIDDEN or REMOVED;
tenant-scoped foreign key to the menu item), review_photos (random storage key, dimensions,
size), review_reports (primary key review + reporter, so one report per student) and
review_moderation_events (AUTO_HIDDEN, RESTORED, REMOVED with actor, session and note). A review
is hidden when the reports filed since `reports_cleared_at` reach REVIEW_REPORT_THRESHOLD
(default 3, a provisional engineering default); restoring sets `reports_cleared_at`, so earlier
reports stop counting. Removing a review deletes its photo files. Photo bytes live in MEDIA_DIR,
not in the database: back up both together.

Notifications: student_notifications is the in-app inbox (integer id so entries written in one
transaction keep their order; read_at marks them read). Reports are computed from
payment_attempts, refunds, orders and order_lines; no separate ledger table exists yet.

Downgrade deliberately refuses destructive deletion. Before any deployed schema rollback,
take a backup, verify restoration and obtain operational approval. For a failed additive
migration prefer a reviewed forward repair.
