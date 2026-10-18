# AGENTS.md — AISSMS Campus Canteen

> Root-level implementation instructions for Codex and other coding agents. Read this document, `docs/PRODUCT_SPECIFICATION.md`, `docs/APPLICATION_ARCHITECTURE.md` and both images in `design-references/` **before** modifying application code.

## Mission

Build a genuinely campus-specific **AISSMS Campus Canteen** platform with **native Kotlin/Compose Android student app**, **responsive canteen administration web dashboard**, and a secure modular backend. Support multiple separately managed canteens; verify real UPI payments; enable safe pickup-code redemption, refunds and reviews with photos. Use the supplied image mockups as primary visual targets; never introduce a generic food-delivery template.

## Source of truth and instruction precedence

1. Explicit confirmed product-owner instructions and approved decisions in `docs/decisions.md` (when created).
2. `docs/PRODUCT_SPECIFICATION.md` — product scope, screens, confirmed user flows, edge cases.
3. `docs/APPLICATION_ARCHITECTURE.md` — proposed engineering approach, subject to approval.
4. `docs/DECISIONS.md` — final owner-approved Round 1–3 choices (overrides earlier draft material).
5. `design-references/*.jpg` — visual hierarchy and appearance; correct obvious draft text/label inconsistencies rather than copy bugs.
6. This file — collaboration, code quality, security, testing and delivery rules.

When references conflict, **ask** rather than silently choosing a new payment, refund or cancellation policy. Proposed technology choices and recommendations are not product-owner approvals.

## Non-negotiable business invariants

1. A student can sign in with **any valid Google account**; college email is not mandatory.
2. Staff accounts are provisioned, not publicly self-registered; administrative passwords are salted and hashed, never reversibly encrypted.
3. Canteens have their own operating hours, menus, staff permissions, active orders, transaction views and refunds. Enforce this isolation in server authorization and database queries.
4. Single canteen per checkout/cart. Server recalculates total from authoritative menu prices and validates availability.
5. A paid/active order and pickup credential are created **only after server-verified payment**. Payment-provider client redirects cannot assert success by themselves.
6. Student cancellation is permitted strictly within **five minutes of verified successful payment**, decided by server clock and transactional state, even if food preparation has begun.
7. A successful cancellation immediately invalidates pickup redemption and removes the order from active preparation lists; eligible refunds are processed via provider-verifiable workflow.
8. The six-digit pickup code **does not time out** after 5 minutes, 1 hour, 2 hours or 3 hours. It is active until order is collected or cancelled (unless a new owner-approved exceptional policy is added).
9. Code lookup alone never completes an order. Staff reviews the retrieved order, hands over items, and presses **Complete Order**. Completion invalidates code atomically. No extra confirmation by student.
10. Store order/payment records and receipts after collection, but no usable historical pickup credential.
11. Canteens manually toggle item availability, including pre-opening preparation. Unavailable items remain visible but cannot be ordered.
12. Only verified **collected-item purchasers** can review. Support stars, text and review photos shown on item detail/gallery. Protect photo privacy and enforce content/file rules.
13. Refund status is visible to student and canteen, and only becomes `REFUNDED` after provider-confirmed outcome.
14. Actual UPI integration is mandatory for a production launch; use an explicit sandbox during development, never present a mock payment as real.
15. Development should have **no compulsory paid services**; do not activate production expenses or real charges without explicit approval.

## Screens

**Android:** Sign-in; Home/Top 5; Canteen Menu; Item Details; Cart; Checkout; Active Order/Code; Orders; History; Receipt; Profile; Reviews List; Write/Edit Review; Review Submitted; My Reviews.

**Canteen web:** Admin Login; Dashboard/Orders; Pickup Verification; Menu; Add/Edit Item; Refunds; Sales/Reconciliation; Settings.

Build shared dialog and state components (loading/empty/error, confirmation, closed/unavailable items, pending/failed payment, invalid/consumed pickup code, refund processing) rather than disconnected pages.

## Architecture rules

- Prefer **modular monolith**, not microservices for MVP.
- Starting stack recommendation: Kotlin + Jetpack Compose (Android), React + TypeScript + Vite (canteen web), FastAPI + PostgreSQL (API + data). Obtain product-owner approval for material deviations and major infrastructure decisions.
- Separate modules: identity, institutes/canteens, menu, cart, orders, payments, pickup, refunds, reviews, media, reporting.
- UI components **must not** own business/payment state logic. Backend is single source of truth.
- Centralize shared design tokens, API contracts, validation and error models. Expose a versioned OpenAPI specification.
- No hardcoded campus/menu entries inside UI components. Seed example data is clearly labeled sample data until institute/canteen information is verified.
- Use migrations and constraints; financial values in integer minor units and timestamp instants in UTC.
- Keep provider-specific gateway/storage code behind adapters. Use dependency inversion where it reduces coupling.
- Restrict unnecessary dependencies; avoid monolithic files and duplicate domain logic.
- Preserve existing user work and repository changes; inspect before editing.

## Critical security requirements

- Validate Google ID tokens on the backend with correct audience/issuer; protect user endpoints.
- Staff: Argon2id passwords, secure sessions and role/canteen membership checks.
- Verify signed payment webhooks, amount, currency and idempotency; treat webhook data as untrusted until validated.
- Atomic order transitions for cancel vs complete; double completion and replay safe.
- Six-digit code brute-force protection, active-code namespace uniqueness, no sensitive logging, per-user/staff/API throttling.
- Secure image uploads with MIME/content verification, upload limits and malware/content moderation strategy.
- No credentials, production keys, PII dumps or private user photos committed to Git.
- Keep audit events for payment, pickup and refunds.
- Enforce HTTPS, appropriate CORS/CSRF protections and safe error messages in deployed services.

## Working procedure for Codex

**On initial invocation:**
1. Inspect working tree, README, reference images and specification docs.
2. Summarize existing files and any gaps; never overwrite a user's changes casually.
3. Present architecture recommendation, repo layout, database diagram and a phase-by-phase plan.
4. List unanswered blocking decisions: merchant/gateway ownership, settlement, refunds authorization, assets, closing-time uncollected-order policy.
5. Request approval before substantial application development. Do not write the whole stack in one unchecked pass.

**For every implementation phase:**
1. Make a scoped plan with acceptance criteria.
2. Build the smallest useful vertical slice and tests.
3. Run formatting/lint/typecheck/tests relevant to changes.
4. Report exactly what was tested and any failures; don't falsely claim tests passed.
5. Update docs and `docs/decisions.md` for approved choices.
6. Record known TODOs and environment requirements.
7. Stop and ask when spending money, production payment activation, destructive database migrations or major business-policy changes are necessary.

## Test matrix (minimum)

- Google login and staff authorization; tenant isolation of COE vs IOIT.
- Menu item out of stock during cart/checkout and changing prices.
- Server-authoritative totals and immutable receipt snapshots.
- Gateway pending/failed/late/duplicated callback and duplicate order creation.
- Cancellation success at 4:59 and rejection at 5:00 (exact policy boundary documented).
- Code valid after 3+ hours if neither cancelled nor collected.
- Code lookup does not redeem; completion redeems once only.
- Two staff simultaneously attempting the same code; cancellation racing with code completion.
- Cancelled order disappears from queue; code can no longer redeem.
- Refund pending, succeeded, failed, replayed and reconciliation-required.
- Review eligibility by collected order line; stars/text/photo upload and editing.
- Invalid photo formats, excessive file sizes, unauthorized accesses.
- Sales/report calculations and order audit trails.

## UI and accessibility

- Follow mockup's AISSMS crest/logo treatment, blue/white/navy accents, clean typography and campus photography **where permissions allow**. Never mislabel generic campus images as verified AISSMS locations.
- Android is touch-friendly, readable and responsive to screen sizes; canteen dashboard optimized for rapid code entry and table scanning.
- Include network/loading/error/empty states, button disabled/loading, focus and keyboard navigation on admin web.
- Review photos belong in item galleries and review cards; retain canteen-controlled official product thumbnails.

## Project documents and maintenance

Maintain `README.md`, `docs/api.md`, `docs/database.md`, `docs/decisions.md`, `docs/deployment.md`, and this `AGENTS.md`. Update spec/architecture when product owner approves a change. Never convert an optional suggestion into a committed feature without approval.

## Definition of done

A feature is complete only when UI, backend validation, permissions, error states, persistent data, tests, and concise documentation all agree. Payment/pickup/refund flows require concurrency and recovery tests. Real-world launch requires merchant/KYC approval, participant authorization, image rights, privacy notice, production secrets, monitoring and backups.


---

## Final controlling decisions and autonomous delivery (14 Oct 2026)

**Read `docs/DECISIONS.md` as authoritative; it supersedes incompatible old statements in this document.** Core stack is now approved. Separate COE/IOIT canteen accounts and merchant accounts; institute-first browsing and remembered selection; shared admin account per canteen initially; independent sales and refunds.

### Explicit UX/scope limitations

- Android native APK, canteen dashboard desktop-first responsive.
- In-app notifications only; no push. Large six-digit pickup code only; no QR. In-app receipt only; no PDF/share. English only.
- Display ratings on menu cards, text/stars/photos in item details, review entry from collected order history; publish reviews immediately, temporarily hide after configurable distinct validated abuse reports.
- Browse closed canteens without ordering. Multiple active orders allowed, unique code per order.
- Staff contact customers manually for stock failures and uncollected-at-close cases. Distinguish tightly controlled staff exception resolution from time-limited student cancellation.
- Live web order updates plus optional short audible cue and mute. Reports: daily/weekly/monthly, date filters and item-wise sales.

### Merchant configuration and shared account safeguards

- Each canteen has a separate gateway-approved merchant account. Canteen admin can request/edit account **configuration** via authenticated settings, with re-authentication for sensitive changes, server validation, audit log and provider verification prior to activation. Do not permit raw arbitrary UPI IDs to re-route gateway funds or expose provider secrets in UI. Existing payments/refunds remain attached to original merchant account.
- Shared login is intentionally accepted for MVP; implement audit/session identifiers, secure provisioning, password hashing, credential rotation and future support for individual staff identities.

### GitHub and autonomous development mandate

- Work exclusively in `https://github.com/vighneshvijayjadhav-eng/CAMPUS_CANTEEN.git`; inspect branch and latest remote before modifying.
- Owner **explicitly authorizes pushes directly to `main`** upon completion and verification of each phase. Do not mandate feature branches or PRs. Stage carefully, commit coherent changes, run tests/CI as available, sync with remote safely and push; **never force push**. Report commit SHA, results and any incomplete tests.
- Owner **explicitly authorizes uninterrupted progression through phases 1–8**. Give progress reports at phase boundaries, but do not stop for routine approval. If credentials or production permissions are missing, use local sandbox adapters, mark blocked integrations clearly, continue independent modules.
- Never use fake production payment confirmations. Do not activate a real gateway, change live payout settings, deploy publicly, spend funds or make destructive irreversible changes without explicit external approval.
- Tests, required credential/merchant approvals, schema safety, tenant isolation and secure secret handling are non-negotiable.


---

# AUTHORITATIVE REVISION — 18 OCT 2026: MULTI-COUNTER PRODUCTION MODEL

This section overrides any older wording that suggests one pickup confirmation completes the entire multi-station order, that there are only two canteen logins, or that pickup tokens expire after a duration. Read `docs/MULTI_COUNTER_WORKFLOW.md` and `docs/MENU_SEED_GUIDE.md`.

- **Objective: a production-grade build**, not a simulated demo. Complete end-to-end implementation, test suites, staging/deployment runbooks and production readiness gates. Never represent sandbox credentials as a live system. Public production rollout and real-money collection require merchant onboarding, institutional/canteen approval, and explicit operational authorization.
- **One canteen, multiple stations.** COE and IOIT remain isolated canteen tenants. Within each canteen create configurable stations (e.g., snacks, juice, meals). Counter identity and food category are distinct. Each menu item/variant must resolve to a station for fulfillment; missing assignments block ordering until mapped. Staff may change mappings via dashboard.
- **One order, one payment, one six-digit code.** Student checks out once per canteen. Persist station-specific fulfillment lines/groupings under a parent order. Fan out its paid order lines to station queues. Same six-digit code can be entered at any authorized counter.
- **Station authorization.** Separate provisioned logins for main admin and each station, using the same sign-in screen; device sessions persist across restarts and can be revoked/rotated. Do not implement literal lifetime unrevocable credentials or publicly shared admin passwords. Station operators view their assigned queue and can complete only their own uncollected lines. Main admin can view/verify all and confirm specific items actually handed over (not merely previewed). Staff can coordinate physical handover verbally as today.
- **Partial pickup.** Code lookup is read-only. Confirmation records specific eligible lines/quantities as handed over, with actor/device/time audit. Never silently mark another station's items complete. Order status becomes COLLECTED only when **all** paid, non-cancelled items are fulfilled; until then display PARTIALLY_COLLECTED and pending stations/items in student app and admin UI. Invalidate code only after full collection or a qualifying whole-order cancellation; prevent replay/double-collection under simultaneous devices.
- **Cancellation:** preserve owner five-minute post-payment cancellation window; once any line has been handed over, whole-order cancellation and refund must not automatically proceed because goods cannot be recalled. Present an exception state for authorized staff resolution and applicable partial refund. Define and test policy explicitly before implementing that edge; do not silently refund an already handed-over item. Within window, cancellation removes unfulfilled station work atomically.
- **Counter notifications:** station dashboards receive scoped real-time paid order/cancel updates, with optional sound after browser user interaction. Main admin sees all. Dashboard requires reconnect/poll fallback and duplicate-event protection.
- **Menu source:** `data/AISSMS_Canteen_Menu.xlsx` is the authoritative initial **IOIT and COE** seed source. `data/menu_seed_draft.json` is a convenience transcription only. IOIT and COE are separate seed targets. COE price/size variations must be preserved; unknown entries flagged for staff verification, never silently estimated. All items initially non-orderable until prices, station assignments, and operating status are confirmed. Continue using dashboard CRUD; **no Excel import UI** requested. Seed script must be idempotent and never overwrite canteen edits on re-run.
- **Deferred:** walk-in cash/UPI POS/billing, ERP, receipt printers. Existing over-the-counter payments continue outside app; do not record offline walk-in payments as gateway-verified app payments.
- **GitHub:** use only `https://github.com/vighneshvijayjadhav-eng/CAMPUS_CANTEEN.git`, commit/push verified phases directly to `main` as requested; avoid force pushes, reconcile remote changes, never store secrets. Continue coding across phases without routine approval requests; report real tests and blocked external dependencies.
