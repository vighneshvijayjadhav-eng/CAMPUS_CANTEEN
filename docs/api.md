# API implementation status

Run `uvicorn app.main:create_app --factory` from services/api. OpenAPI is served at
`/openapi.json`; `/docs` provides the interactive contract. `/health` explicitly returns
`release_ready: false`; `/ready` checks the database only.

- Public catalog: GET /api/v1/institutes, /institutes/{id}/canteens, /canteens and
  /canteens/{id}/menu. Only approved institutes and canteens are disclosed.
- Student identity: POST /api/v1/auth/google and /auth/student/refresh; GET
  /student/me and /student/sessions; PATCH /student/preferences/institute; POST
  /student/sessions/revoke. Google ID tokens are validated against the configured Android
  OAuth client ID; no institution email restriction is applied.
- Student cart: GET/DELETE /api/v1/student/cart and PUT
  /student/cart/lines/{variant_id}. Bearer access tokens identify the student. A cart has
  one canteen; prices and orderability are always rechecked on the server.
- Student checkout: POST /api/v1/student/checkout with `request_id` (UUID, generated once per
  tap and reused on retry) and `expected_total_paise` (the total the student confirmed).
  Returns 201 and the order detail in PAYMENT_PENDING; the cart is emptied. Errors:
  CART_EMPTY, CART_ITEM_UNAVAILABLE, PRICE_CHANGED (refetch the cart and reconfirm),
  CANTEEN_NOT_OPERATING, CANTEEN_CLOSED, CANTEEN_NOT_APPROVED, IDEMPOTENCY_CONFLICT (same
  request_id, different total). No payment is started and no pickup code is issued yet.
- Student orders: GET /api/v1/student/orders (newest first, 50 max) and
  /student/orders/{id} (own orders only; others return 404). Detail includes charged line
  snapshots, remaining quantity per station, `payment` (latest attempt status) and
  `pickup_code` (the six-digit code while the order is paid and not fully collected).
- Student payment (Razorpay): POST /api/v1/student/orders/{id}/payment returns Checkout
  parameters (`key_id`, `provider_order_id`, `amount_paise`, `currency`, `merchant_name`,
  `mode`); repeated calls reuse the open attempt. After Razorpay Checkout succeeds the app POSTs
  /student/orders/{id}/payment/confirm with `provider_order_id`, `provider_payment_id` and
  `signature`. The server checks the signature, then fetches the payment from Razorpay; the order
  becomes PAID_ACTIVE only for a captured payment of the exact amount. `payment_status`
  CREATED means still processing (poll the order). Errors: ORDER_NOT_PAYABLE,
  PAYMENTS_NOT_CONFIGURED (503), PAYMENT_SIGNATURE_INVALID (400), PAYMENT_PROVIDER_* (502/503).
- Razorpay webhook: POST /api/v1/payments/razorpay/webhooks/{merchant_account_id}, verified with
  that account's webhook secret over the raw body (`X-Razorpay-Signature`). Handles
  payment.captured, order.paid, payment.failed and refund.created/processed/failed; replays (same `X-Razorpay-Event-Id`, or same
  body) return DUPLICATE. Other events are recorded and IGNORED.
- Student cancellation: POST /api/v1/student/orders/{id}/cancel. Unpaid orders are simply
  cancelled. Paid orders within five minutes of payment with nothing handed over are cancelled,
  the pickup code is withdrawn and a full Razorpay refund is requested; the response is the order
  detail including `refund_status` (REQUESTED, PENDING, REFUNDED, FAILED) and `refunds`. If any
  item was handed over it becomes a staff exception instead (no refund). Errors:
  CANCELLATION_WINDOW_CLOSED, ORDER_NOT_CANCELLABLE. Repeating the call is harmless.
- Staff cancellation: admin POST /api/v1/staff/orders/{id}/cancel with `note` (why, e.g. closing
  time after contacting the student). Only for paid orders with nothing handed over; otherwise
  PARTIAL_REFUND_POLICY_REQUIRED. Refunds the full amount.
- Refunds: admin GET /api/v1/staff/refunds (own canteen, newest 200) and POST
  /staff/refunds/{id}/retry for a FAILED refund (creates a new refund row; the failed one stays).
  REFUNDED/PROCESSED is set only from Razorpay's own refund state.
- Reviews (public): GET /api/v1/menu-items/{item_id}/reviews (visible reviews, newest first,
  author first name only). The public canteen menu adds `rating_average` and `rating_count` per
  item. Photos: GET /api/v1/media/reviews/{key} (only for visible reviews; the canteen admin can
  also open photos of hidden reviews while moderating).
- Reviews (student): POST /api/v1/student/order-lines/{line_id}/review with `rating` 1-5 and
  optional `body` (max 1000), allowed once per order line after at least one unit was handed
  over (REVIEW_REQUIRES_COLLECTION, REVIEW_EXISTS). PATCH /student/reviews/{id} edits;
  GET /student/reviews lists your own. Order detail lines include `reviewable` and `review_id`.
  Photos: POST /student/reviews/{id}/photos with the raw image as the body and
  `Content-Type: image/jpeg|png|webp` (max 5 MB, 3 per review; INVALID_IMAGE 415,
  IMAGE_TOO_LARGE 413, TOO_MANY_PHOTOS). DELETE /student/reviews/{id}/photos/{photo_id}.
  Report: POST /student/reviews/{id}/report with `reason` (SPAM, OFFENSIVE, IRRELEVANT, PRIVACY,
  OTHER) and optional `note`; only students who have collected food at that canteen, once per
  review, never your own.
- Review moderation: admin GET /api/v1/staff/reviews?status=HIDDEN|VISIBLE (with reports),
  POST /staff/reviews/{id}/restore and /staff/reviews/{id}/remove with optional `note`.
- Student notifications (in-app only): GET /api/v1/student/notifications returns `unread` and
  the latest 50 `items` (id, order_id, kind, title, body, created_at, read), newest first;
  POST /student/notifications/read marks all read. Kinds: PAYMENT_CONFIRMED,
  ORDER_PARTLY_COLLECTED, ORDER_COLLECTED, ORDER_CANCELLED, ORDER_CANCELLED_BY_CANTEEN,
  CANCELLATION_REVIEW, EXTRA_PAYMENT_REFUND, REFUND_COMPLETED, REFUND_FAILED. Each is written in
  the same transaction as the change it reports.
- Sales report: admin GET /api/v1/staff/reports/sales?start=YYYY-MM-DD&end=YYYY-MM-DD&group=
  day|week|month (India time, at most 366 days). Returns `periods` (orders, gross_paise,
  refunds_paise, net_paise, other_refunds_paise), `totals` and item-wise `items`. Gross is money
  Razorpay captured for orders; refunds are completed refunds of cancelled orders on their
  completion day; other_refunds are duplicate or wrong-amount payments returned (never sales).
- Merchant metadata: admin GET /api/v1/staff/merchant (key id, mode, active, webhook path; never
  secrets). Accounts are added by the owner CLI, not through the API.
- Canteen settings: admin GET/PATCH /api/v1/staff/canteen. PATCH accepts `operating` (master
  switch) and/or `hours` (replaces all windows): `[{weekday 0=Mon..6, opens "HH:MM",
  closes "HH:MM"|"24:00"}]` in India time, one window per weekday. With no hours configured
  only the switch applies; once any exist, a weekday without a window is closed. The public
  institute canteen listing includes `accepting_orders`.
- Staff identity: POST /api/v1/auth/staff/login, /auth/refresh, /auth/logout.
- Staff: GET /api/v1/staff/me, /staff/sessions and POST /staff/sessions/{id}/revoke.
- Admin menu: GET/POST /api/v1/staff/menu, PATCH /staff/menu/{id},
  POST /staff/menu/{id}/variants, PATCH /staff/variants/{id}.
- Stations: GET /api/v1/staff/stations; admin POST and PATCH /staff/stations/{id}.
- Queue: GET /api/v1/staff/orders and /staff/events?after={event_id}.
- Pickup: POST /api/v1/staff/pickup/lookup with six-digit code, no mutation.
- Handover: POST /api/v1/staff/orders/{order_id}/lines/{line_id}/confirm with
  quantity, expected_fulfilled, request_id (UUID). Retry exactly the same request after
  a network failure; a changed body with that key conflicts. Refresh stale line counts.
- Exceptions: admin GET /api/v1/staff/exceptions and POST
  /staff/exceptions/{order_id}/contact. Contact recording does not authorize a refund.

Cookie-authenticated staff writes require the configured web Origin. Native-app bearer-token
writes may omit Origin, but a supplied nonmatching Origin is denied. Staff cookies are HttpOnly
and SameSite Strict, Secure outside local mode. Never send a role/canteen/station claim from
the UI to authorize an action; the server resolves them from the persisted session and account.

There is intentionally no payment-success or simulator endpoint: only Razorpay-verified captures
activate orders. Unpaid orders never reach a station queue. Tests use a fake Razorpay API, which
is not merchant evidence. Student cancellation currently exists as a tested domain
service, not a public endpoint until paid-order lifecycle APIs are implemented.

SSE uses committed queue events as refetch hints and checks session validity every two
seconds. Clients must retain periodic queue refetch because sequence allocation and commit
order can differ across transactions. Reconnect cursors and event IDs suppress duplicate
UI notifications. Data mutation never depends on event delivery.
