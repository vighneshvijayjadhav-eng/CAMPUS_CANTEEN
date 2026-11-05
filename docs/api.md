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
  snapshots, remaining quantity per station and `pickup_code` (null until payment exists).
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

There is intentionally no payment-success or simulator endpoint. Checkout only creates an unpaid
order, which never reaches a station queue. Paid orders in tests are fixtures, not merchant
evidence. Student cancellation currently exists as a tested domain
service, not a public endpoint until paid-order lifecycle APIs are implemented.

SSE uses committed queue events as refetch hints and checks session validity every two
seconds. Clients must retain periodic queue refetch because sequence allocation and commit
order can differ across transactions. Reconnect cursors and event IDs suppress duplicate
UI notifications. Data mutation never depends on event delivery.
