# Multi-counter workflow — operational and engineering contract

## Actors
- Student Android application: one paid canteen order, one six-digit code, station progress visible.
- Canteen admin: independent account for COE and IOIT; manages all station queues, menu-to-station mappings, refund requests and reports, and may verify/confirm item handover.
- Station operator: unique station username and secret, persistent revocable device session; only assigned queue, pickup lookup scoped to their station, and authorized fulfillment actions.

## Physical process
Current canteen operates a main billing counter plus separate snack, juice and meal counters. Customers may pay physically at a station or main counter outside this app. Student-app payments go once to the corresponding canteen merchant gateway. The app does not replace existing physical POS.

## Happy path
Student orders juice + sandwich + thali in a single COE checkout → back end validates and verifies one payment → generates one 6-digit code → fans out three fulfillment groups assigned by menu item to JUICE, SNACKS, MEALS. Each station sees only its group; main admin sees all groups. Student can present the same code at juice, snacks or main counter. Code LOOKUP never completes anything. Staff confirm the specific items/quantities handed over at that station. State updates synchronously across devices. Code remains valid for the remaining items. Once every paid order line is collected, atomically mark parent COLLECTED and deactivate code.

## Data model
Add `canteen_stations`, `station_accounts`/account memberships, `station_device_sessions`, `order_fulfillment_lines` (or equivalent lines referencing immutable order lines and snapshotted station ID, quantity ordered/fulfilled), and `fulfillment_events`. Each menu item has assigned_station_id, independent of UI category. Support configurable station labels and account provisioning/revocation. Ensure quantity cannot be confirmed beyond ordered quantity, payment is verified, and no cross-canteen station access. Preserve original order line details, financial ledger, and event audit.

## Concurrent correctness
Use PostgreSQL transaction with row locks or guarded atomic updates per fulfillment line. Two counters verifying same code concurrently must not hand out the same units twice. A generic `complete order` command must not complete other stations' items. Student and admin get total and per-station status; station operator receives only authorized fields. Server is authoritative even when a device is stale or offline.

## Cancellation nuance
The baseline five-minute student cancellation rule applies to uncollected orders, including orders currently preparing. Early collection within five minutes creates a conflict: do not auto-refund already handed-over goods. Implement an explicit customer-visible exception resolution path for partial collection, with audited authorized adjustment/refund; make this an acceptance-test gate, not an undocumented policy assumption. After full collection, student cannot cancel. For an entirely uncollected eligible order, cancel parent and remove all station work.

## Acceptance tests
1. COE and IOIT accounts never leak orders.
2. Three-station single payment creates exactly three scoped queues and only one code.
3. Juice counter cannot mark snacks collected.
4. Main admin can complete chosen handed-over items but not automatically whole order.
5. Same code works on remaining stations after first collection, including hours later.
6. Duplicate same-item simultaneous confirmation results in one valid collection.
7. All lines collected atomically consume code; replay rejected.
8. Eligible pre-handover cancellation removes outstanding groups immediately.
9. Partial fulfillment and cancellation cause explicit exception state, not silent refund.
10. Long-lived sessions survive restart but revoke on lost device; privileged admin changes require re-authentication.
11. Live updates recover after disconnect without duplicate notifications/actions.
12. Dashboard remains usable on phone/tablet and during peak rush.
