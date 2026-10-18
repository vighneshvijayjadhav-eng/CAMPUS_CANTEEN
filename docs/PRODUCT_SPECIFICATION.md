# AISSMS Campus Canteen — Product Specification

**Version:** 3.0 — includes 18 October multi-station update  
**Status:** Confirmed requirements + explicitly tagged implementation recommendations and open decisions  
**Product:** Student Android application (APK) and multi-canteen web management dashboard  
**Source of truth:** The discussions with the product owner and the two images in `../design-references/`.

## 1. Product vision and scope

Build a campus-specific prepaid ordering and counter-pickup application for students visiting AISSMS canteens, including COE and IOIT (actual participating institutions/canteens must be verified before launch). Students sign in with **any Google account**, choose a canteen, order items from its current menu, pay via a **real supported UPI gateway**, receive a one-time pickup code and collect at the counter. Canteen staff manage food availability, prepare orders, look up paid orders by code and confirm physical handover. The student app also provides campus-wide food discovery, verified ratings, review photos and receipts. Each canteen has separated administration, menu, transactions, hours and refund views.

This is **not** a delivery or table-booking product. Prioritize low-friction operation for staff dealing with many simultaneous orders.

## 2. Confirmed decisions

| Domain | Confirmed behavior |
|---|---|
| Student platform | Native Android APK |
| Canteen platform | Responsive web/desktop dashboard |
| Login | Students: Google Sign-In with any Google account; canteens: provisioned admin email/password |
| Multi-canteen | Separate canteen menus, admins, orders, hours, sales and refunds |
| Payment | Actual India-compatible UPI payment gateway in production; sandbox while developing |
| Orders | Single canteen per checkout; no delivery |
| Cancellation | Student may cancel **within five minutes after verified successful payment**, even if preparation has started |
| Cancellation effect | Cancelled orders immediately leave the active preparation queue and their pickup credentials cannot be redeemed |
| Refund | Eligible cancelled orders enter a canteen-operated refund workflow; both sides see accurate refund status |
| Code lifetime | Pickup code remains usable until **collected** or **cancelled**; not invalidated by passing five minutes or three hours |
| Collection | Staff enters code, inspects retrieved paid order, hands over items and presses **Complete Order**; no student confirmation |
| History | Student can see complete order/payment receipts; canteen sees necessary reconciliation records |
| Availability | Staff can preconfigure availability roughly one hour before usual service; can temporarily turn items off without deleting them |
| Reviews | Verified purchasers can post stars, text and photos; review photos shown in menu item detail/gallery |
| Budget | Free-first development; small production spend only if college funds it |
| Visual direction | Match supplied AISSMS mockups, with authentic permitted campus images and a restrained blue/white/navy visual system |

## 3. Roles and access

- **Student:** browse publicly eligible canteen/menu information, manage own cart/orders, pay, cancel own eligible orders, show own pickup code, view own history/refunds, write and edit own eligible reviews.
- **Canteen staff/admin:** access assigned canteen only; menu availability and management (permissions as configured), order list and lookup, completion, refund actions, reports.
- **Platform administrator (recommended, not yet confirmed):** invite/provision canteen operators, create canteen/institute records, view system-health/audit data, moderate review abuse. Must not be exposed as public registration.

Security is enforced on the backend; hiding UI elements is not sufficient authorization.

## 4. Student navigation and screen inventory

**Primary navigation:** Home | Orders | History | Profile. Support contextual back navigation and deep linking to an active order.

| ID | Screen | Main elements | Primary transitions |
|---|---|---|---|
| S01 | Student sign-in | AISSMS logo, permitted campus photo, short tagline, Continue with Google, privacy links | Google auth → Home |
| S02 | Home / discovery | Greeting, canteen search, COE/IOIT/nearby filters where applicable, canteen cards with open/closed, Top 5 campus food carousel | Canteen → S03; top item → S04 |
| S03 | Canteen menu | Canteen name, hours, search, All/Snacks/Meals/Beverages, image, price, rating, add/quantity, out-of-stock disabled state, cart CTA | Item → S04; cart → S05 |
| S04 | Food detail | Official menu photo(s), student review photos, description, ₹price, rating breakdown, reviews list CTA, add to cart | Reviews → S12; cart |
| S05 | Cart | Selected canteen, order items, +/- quantities, subtotal/total, unavailable-item warning | Checkout → S06 |
| S06 | Checkout/payment | Server-authoritative total, supported UPI gateway UI, success/failure/pending handling | Verified paid → S07 |
| S07 | Active order/code | Order ID, canteen, item summary, dominant six-digit code, paid label, server-based cancellation countdown and CTA | Cancel confirmation; redemption → History |
| S08 | Orders | All paid uncollected active orders (including their codes), status, details | Active card → S07 |
| S09 | Order history | Collected, cancelled, refunded/failed statuses, filters and receipt links | Receipt → S10 |
| S10 | Receipt | Canteen, transaction reference, timestamp, items and paid price snapshots, payment and collection/refund status | Return to history |
| S11 | Profile | Google avatar/name/email, privacy/help, sign out, my reviews link | My reviews → S15 |
| S12 | Reviews list | Verified review cards, image thumbnails, star filters, report action (recommended) | Eligible student → S13 |
| S13 | Write/edit review | Product, 1–5 stars, optional text, optional image selection/upload, policy note | Submit → S14 |
| S14 | Review submitted | Confirmation, view review/menu actions | S15 or S03 |
| S15 | My reviews | Review history, edit own review, view product | Edit → S13 |

**Prototype note:** Provided mockup labels contain some mismatches (e.g. one history image labeled Profile, and one receipt/active-order mismatch). Implement based on semantic screen purpose rather than inaccurate labels.

### Student interaction rules

1. Canteen discovery reflects configured data. Do not pretend all mockup canteens are officially participating before verification.
2. One active **cart** for one canteen; selecting another while cart has items prompts switch/clear confirmation.
3. Price, taxes, fees (if any), hours and availability are revalidated on the server at checkout. Never rely on on-device totals.
4. Checkout cannot proceed for a closed/unavailable canteen, subject to a clearly defined policy for preorders (not approved for V1).
5. After backend-verified payment: create/activate the order once, issue the code, and show the five-minute cancellation countdown.
6. The countdown expires only the right to cancel; it **does not** expire paid orders or codes.
7. The student may have multiple active orders; each has a distinct reference and safe pickup-credential lookup scope.
8. Cancel action includes confirmation; upon successful cancellation, code stops working and the order leaves staff's active queue.
9. Payment and refund states should be shown accurately, including `PENDING`, `FAILED`, `PROCESSING` and reconciliation-needed cases.
10. Receipts remain available after collection and refunds; do not expose a reusable code on old receipts.

## 5. Canteen web navigation and screens

**Primary sidebar:** Orders | Menu | Refunds | Sales | Settings; logout. Use desktop-first, usable on tablets.

| ID | Screen | Main elements | Primary transitions |
|---|---|---|---|
| C01 | Admin login | Provisioned email/password, errors, reset mechanism | Login → C02 |
| C02 | Dashboard/orders | Today totals, pickup input prominently displayed, active paid orders list and details, live updates | Code → C03; order drilldown |
| C03 | Pickup verification | Code lookup, correct canteen and paid/uncollected checks, item breakdown, total, Complete Order button | Confirmation → collected |
| C04 | Menu management | Search, category, item photos, availability toggles, Edit, Add, archive | Add/edit → C05 |
| C05 | Add/edit menu item | Image, title, description, price, category, availability; shared form | Save → C04 |
| C06 | Refunds | Eligible cancellations, amount, transaction, provider-refund status, retry/escalation | Trigger authorized refund; verify status |
| C07 | Sales & reconciliation | Transactions, collected/paid/cancelled/refunded counts, gross/refunds/net distinctions, date range, optional export | Transaction detail |
| C08 | Settings | Profile, hours, canteen identity, images, user permissions according to roles | Save configuration |

### Operational rules

- Canteen opening hours must be configurable; **12:30 PM is an approximate example**, not hardcoded universal policy.
- Pre-opening availability edits are supported. Manual stock toggle is enough for V1; no full quantitative inventory necessary.
- Active queue shows verified paid/uncollected orders and excludes cancelled orders immediately (event/push with polling fallback).
- Canteen staff should be able to see multiple paid orders; a single code lookup must never accidentally fetch another canteen's order.
- Invalid/incorrect/consumed/cancelled code messages must not leak private order information to unauthorized parties.
- Canteen sales view is an operational summary; actual payment gateway transaction records are the financial source of truth.

## 6. Payment, order and refund lifecycles

### Payment processing

`DRAFT_CART → CHECKOUT_CREATED → PAYMENT_PENDING → PAID_ACTIVE` only after **server-side verified** payment. Also handle `PAYMENT_FAILED`, `PAYMENT_EXPIRED`, delayed success and duplicates. The payment app returning success on the client is not definitive proof. Webhook signature validation and provider API reconciliation are required.

### Order state machine

```text
PAYMENT_PENDING
   ├─ payment unsuccessful → PAYMENT_FAILED
   └─ verified paid → PAID_ACTIVE
                       ├─ student cancels within 5 minutes → CANCELLED
                       │                                      └─ REFUND_PENDING
                       │                                          └─ REFUND_PROCESSING
                       │                                              ├─ REFUNDED
                       │                                              └─ REFUND_FAILED / RECONCILIATION_REQUIRED
                       └─ staff confirms counter handover → COLLECTED
```

Refund states should preferably be **separate from order-fulfillment states**, not modeled as mutually exclusive single statuses. Order stays CANCELLED while refund goes from pending to refunded.

### Cancellation boundary and concurrency

- `cancel_until = payment_verified_at + 5 minutes` using the server timestamp; specify an inclusive/exclusive boundary (recommend `now < cancel_until`).
- Enforce cutoff **atomically on server**, not just by disabling the button.
- Pickup completion and cancellation contend for the same order state; exactly one may win. Lock/compare-and-swap the transition.
- A cancelled order cannot be collected, including if a staff verification page was opened before cancellation.
- Never mark `REFUNDED` based solely on an admin click. Await verified provider refund outcome; some refunds are asynchronous.

### Pickup code

- Six decimal digits as shown in the mockup; generate cryptographically securely.
- Scope and uniqueness among currently redeemable codes must prevent ambiguity (e.g. unique active codes within canteen or lookup namespace).
- Store credential safely (e.g. keyed digest/hash with limited-scope lookup), avoid logging it, impose throttling and audit abuse.
- No time-based invalidation after 5 minutes or 3 hours; only cancellation or successful collection makes it invalid.
- Preserve immutable order and payment records after pickup while deactivating the redemption credential.
- Use staff's explicit **Complete Order** operation to perform atomic redemption.

## 7. Reviews and Top 5

- Only an authenticated buyer who has **collected** the food item can review it (proposed eligibility rule from previous agreement).
- One review per purchased item **per collected order line** (recommended anti-duplication model); editing is allowed for own review.
- Stars 1–5 required; text and photo(s) optional. The user requested support for all three modalities.
- Review photos appear in item gallery/detail and reviews—not as unapproved replacement for an official food image.
- Uploaded photos require file-type/size limits, moderation/reporting, access controls and privacy considerations.
- Top 5 is campus-wide across eligible items; use a documented weighted/Bayesian score and deterministic tie-breakers to avoid rankings driven by one review.
- Decide treatment of newly introduced/unreviewed items; do not fabricate star values.

## 8. Empty, error and edge-case designs

Design reusable states for: network offline, canteen closed, empty cart, menu item disabled mid-checkout, price changed, payment pending/failed/success not yet confirmed, duplicated payment callback, active order recovery after app restart, multiple orders, expired cancellation window, invalid/consumed/cancelled pickup code, competing pickup/cancellation, refund pending/failed/completed, empty reviews, blocked photo uploads, and no sales records.

Accessibility: touch targets, readable typography, sufficient contrast, descriptive images, keyboard-accessible canteen dashboard, loading and confirmation states.

## 9. Nonfunctional and engineering requirements

- Consistent shared API consumed by Android and web.
- Backend-enforced roles, payment and business rules, multi-tenant isolation and immutable transaction audit trail.
- Fast pickup lookup with rate limiting and server-side idempotency.
- Time stored as UTC, displayed in Asia/Kolkata for campus users.
- Avoid financial data mismatch: store line-item price snapshots, tax/fee breakdown and provider references.
- Secure Google auth, hashed admin passwords (Argon2id recommended), audited admin operations.
- Secure media uploads and controls against review abuse.
- Development on free/local tooling; production hosting budget subject to college approval and gateway/KYC onboarding.

## 10. MVP versus later enhancements

**Committed V1:** native Android sign-in, campus/canteen discovery, menus/cart, live verified UPI payment, five-minute cancellation, code-based handover, canteen administration, refunds, order/transaction history, reviews with image uploads, Top 5, core reporting.

**Not committed / later:** delivery, table reservations, multi-canteen combined checkout, AI recommendations, advanced quantitative inventory, push notifications, loyalty, promo engine, nutrition analytics, dynamic prep ETAs, deep ERP integration, auto-expiring pickup codes.

## 11. Open decisions (do not silently invent policies)

1. Exact participating institutes/canteens, approved names, images, branding usage and operating schedules.
2. Payment provider/merchant ownership, KYC, settlement routing for separate canteens, refund permissions, fees and launch approvals.
3. Whether preorders before opening are allowed; default recommendation: not in V1.
4. How to handle paid, uncollected orders when canteen closes (code persists; escalation/operational recovery is needed).
5. Cancellation and refund exceptions for gateway errors, delayed webhooks and partial failures.
6. Tax treatment, transaction fees, convenience fees (if any), and receipt fields.
7. Refund administration: whether canteen operators can actually initiate refunds or require authorized finance role.
8. Photo upload counts, retention, moderation, user reporting and privacy notice.
9. How to handle canteen workers sharing one account vs per-staff identities (recommended per staff).
10. Help/support channels and response procedures.

## 12. Acceptance examples

- Google account outside institutional domain signs in successfully.
- A student selects COE, adds items, pays through sandbox, and sees an active six-digit code.
- At 4m59s after verified payment, cancellation succeeds; at 5m00s it fails under the chosen boundary rule.
- Student arriving two hours later can still redeem an active code.
- Verifying a code does **not** consume it; **Complete Order** does.
- Reusing an already consumed code is rejected.
- A cancelled order vanishes promptly from active queue and its code is rejected.
- IOIT admin cannot access COE orders, menu or reports.
- An unpurchased item cannot be reviewed; a collected item may receive stars/text/photos.
- Menu item becomes unavailable and cannot be newly purchased, while historic receipts remain unchanged.


---

## Finalized product-owner decisions (Rounds 1–3, 14 Oct 2026)

**This section and `DECISIONS.md` supersede any earlier tentative or conflicting statements in this document.**



- Student: **native Android APK**; canteen: **desktop-first responsive web**, usable on phones/tablets.
- Students authenticate with **any Google account**; canteens have provisioned email/password credentials; initial provisioning by product owner, eventual super-admin later.
- Institute selection comes **first**; remember last selected institute, but allow changing. Switching institute never hides or destroys all-account orders/history.
- Independent COE and IOIT canteen identities, menus, operating hours, staff access, active orders, ledger/reports, and **separate payment merchant accounts**. More institutes/canteens configurable.
- UPI payments through a **real payment gateway** in production, verified server-side; development uses sandbox. Canteens receive payments into their respective gateway-approved merchant accounts, not an unverified free-form UPI address.
- Cart contains items from one canteen only. Student can maintain **multiple active orders**, each with its own unique six-digit pickup code.
- After **server-verified successful payment**, cancellation allowed strictly within five minutes, even if prep started; cancelled orders immediately disappear from active queue. Code **does not expire automatically**, even after several hours or closing; becomes unusable only on cancellation or successful collection.
- Staff enter code → preview relevant items → confirm only items actually handed over; individual station fulfillment syncs, and order becomes COLLECTED only when every item is fulfilled. No student confirmation.
- Refund status visible both sides; canteen admin initiates eligible refunds, actual REFUNDED status only after verified gateway confirmation.
- Item availability is manually controlled (including preopening); unavailable items remain visible but nonorderable; closed canteens are browseable but ordering disabled.
- Collected-order purchasers can rate 1–5 stars with text/photos; menu cards show rating/count, item detail shows full reviews/gallery; review invitation from history, no automatic popup.
- In-app notifications only, no push. Pickup display is **large six digits only**, no QR. English only. In-app receipts only: no PDF/share requirement.
- UI follows supplied mockups and permitted authentic AISSMS imagery (not generic food-delivery styling).

## Round 1 — Canteen operations

1. **Provisioning:** owner manually sets up separate COE and IOIT canteen admin accounts; super-admin management is a later feature.
2. **Closing:** uncollected orders are handled manually. Staff contacts the student and either retains the order for later collection or initiates eligible cancellation/refund; never silently expire the code at close.
3. **Unavailable after payment:** staff contact student **manually** (phone or counter). Student can consent to a replacement; otherwise staff follow authorized cancellation/refund flow. Keep an audit entry; no in-app replacement approval required in MVP. If replacement changes charge, use an authorized payment/refund adjustment, not silent price editing.
4. **Discovery:** choose institute, then browse participating canteens.
5. **Concurrent orders:** multiple active orders allowed, distinct code each.
6. **Reviews:** initially publish immediately; reporting is available.
7. **Refund:** each canteen admin may initiate refunds for their canteen only.
8. **Settlement:** separate merchant accounts for COE and IOIT. Admin may request/update payment configuration subject to secure backend validation, provider approval, auditing and safe activation. Display/edit nonsensitive merchant metadata in UI; never display plaintext secret keys. Merchant account changes must not redirect earlier orders/refunds.

## Round 2 — Student experience

1. Remember institute choice and allow switching.
2. In-app notifications only; include payment, cancellation, refund and order-related events. No OS push alerts.
3. Payment failed/pending views and **safe retries**; reconcile existing attempts before retrying and avoid duplicate charge/fulfillment.
4. Pickup code: six large decimal digits only, no QR or copy control required.
5. Cards: rating and count; detailed stars/text/review photos on item detail.
6. Review option in history only after collection.
7. Closed canteens can be browsed; ordering disabled.
8. Post-payment stock problems handled by staff calling/talking to student, not in-app approval.
9. English-only UI.
10. In-app order receipt/history, no PDF or share UI.

## Round 3 — Staff, administration and delivery

1. **One shared canteen admin login per canteen** initially (COE and IOIT independent). Because shared credentials weaken accountability, still audit actions with session/device/time; make future individual staff identities possible without database redesign; rate-limit and support secure password rotation.
2. Canteen admin can **request and update** merchant configuration within own canteen. Sensitive updates require re-authentication, validation, audit, staged activation, and provider-approved account ownership; never permit arbitrary unverified redirect of live funds.
3. Web dashboard desktop-first, functional on mobile/tablet.
4. **Live order updates plus short optional sound**, with mute control and browser gesture/autoplay fallback; polling fallback when realtime connection fails.
5. At closing, staff contact student, retain order or manually resolve cancellation/refund; do not auto-expire pickup code.
6. Sales: daily/weekly/monthly reporting, date filters, item-wise sales, gross/refunds/net and reconcilable transaction exports only if implemented later (export not mandatory).
7. Reviews publish immediately; after a configurable count of **distinct valid abuse reports**, review is **temporarily hidden** until manual moderation. Prevent repeat/brigade reports and provide restoration/rejection and audit trail. This replaces the Round 1 simple report-only action.
8. Product owner manages development OAuth/gateway setup; authorized college/canteens own production configuration and credentials before live launch.
9. **Commit and push completed phases directly to `main`** in `https://github.com/vighneshvijayjadhav-eng/CAMPUS_CANTEEN.git`. No feature-branch/PR requirement. Pull latest before edits, keep commits atomic, run tests, and push only verified state; report SHA. Never force push or overwrite others; if protection/conflict blocks push, report and stop that push rather than bypass restrictions.
10. **Continue through all development phases autonomously**, reporting each phase and testing as you go. Do not seek routine phase approvals. Stop and ask only for unavailable credentials, required external authorization, irreversible/destructive operations, real-money actions, or product decisions that cannot be safely deferred. Do not mistake continuous coding permission for permission to activate real payments or deploy publicly.



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
