# Product Decisions — Three-Round Finalization

**Status:** Approved 14 October 2026; amended 18 October 2026. Overrides earlier drafts wherever they disagree. The product owner authorizes continuous phase-by-phase implementation and direct pushes to `main`, subject to safeguards below.

## Baseline, already confirmed

- Student: **native Android APK**; canteen: **desktop-first responsive web**, usable on phones/tablets.
- Students authenticate with **any Google account**; canteens have provisioned email/password credentials; initial provisioning by product owner, eventual super-admin later.
- Institute selection comes **first**; remember last selected institute, but allow changing. Switching institute never hides or destroys all-account orders/history.
- Independent COE and IOIT canteen identities, menus, operating hours, staff access, active orders, ledger/reports, and **separate payment merchant accounts**. More institutes/canteens configurable.
- UPI payments through a **real payment gateway** in production, verified server-side; development uses sandbox. Canteens receive payments into their respective gateway-approved merchant accounts, not an unverified free-form UPI address.
- Cart contains items from one canteen only. Student can maintain **multiple active orders**, each with its own unique six-digit pickup code.
- After **server-verified successful payment**, cancellation allowed strictly within five minutes, even if prep started; cancelled orders immediately disappear from active queue. Code **does not expire automatically**, even after several hours or closing; becomes unusable only on cancellation or successful collection.
- Staff enter code → preview → hand over → confirm relevant items; mark whole order COLLECTED only after all order items are fulfilled; no student confirmation.
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

## Policy distinctions and production blockers

- **Order cancellation vs staff exception:** student self-cancellation expires at five minutes. Staff cancellation/after-closing resolution is a distinct audited exceptional workflow; scope and refund handling must be defined and controlled, not offered as unlimited student self-cancellation.
- **Refund eligibility:** canceled order is eligible; actual gateway refund needs provider proof. Additional stock/closing exception requests may need explicit authorized staff policy. Never invent a refund outcome.
- **Review threshold:** recommend default 3 distinct authenticated reporters, configurable, with anti-abuse checks; exact threshold is a *provisional engineering default*, not explicitly selected by owner.
- **Merchant registration, KYC and gateway fees:** external prerequisites to real production acceptance. Cannot be assumed available even if implementation works.
- **Official asset permissions and actual canteen participation:** verify before public use; development mock assets must be clearly identified.
- **Security exceptions:** direct-to-main and shared login are owner's accepted MVP tradeoffs; CI/test gates, audit trails and safe secrets handling remain mandatory.


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
