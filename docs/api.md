# API implementation status

Run `uvicorn app.main:create_app --factory` from services/api. OpenAPI is served at
`/openapi.json`; `/docs` provides the interactive contract. `/health` explicitly returns
`release_ready: false`; `/ready` checks the database only.

- Public: GET /api/v1/canteens and /canteens/{id}/menu.
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

All writes require the configured web Origin. Cookies are HttpOnly and SameSite Strict,
Secure outside local mode. Never send a role/canteen/station claim from the UI to authorize
an action; the server resolves them from the persisted session and account.

There is intentionally no unauthenticated order insertion, payment-success or simulator
endpoint. Paid orders in tests are fixtures, not merchant evidence. Student cancellation
currently exists as a tested domain service, not a public endpoint without Google auth.

SSE uses committed queue events as refetch hints and checks session validity every two
seconds. Clients must retain periodic queue refetch because sequence allocation and commit
order can differ across transactions. Reconnect cursors and event IDs suppress duplicate
UI notifications. Data mutation never depends on event delivery.
