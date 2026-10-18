# MASTER CODEX PROMPT — AISSMS CAMPUS CANTEEN (PRODUCTION BUILD, 18 OCT 2026)

Repository: https://github.com/vighneshvijayjadhav-eng/CAMPUS_CANTEEN.git

You are the principal engineer leading an end-to-end, production-oriented implementation, not a demo prototype. Work only in the official existing repository and preserve useful existing code. Read in full before changing code: root `AGENTS.md`, `docs/DECISIONS.md`, `docs/PRODUCT_SPECIFICATION.md`, `docs/APPLICATION_ARCHITECTURE.md`, `docs/MULTI_COUNTER_WORKFLOW.md`, `docs/MENU_SEED_GUIDE.md`, `docs/PRODUCTION_READINESS.md`, both `design-references/*.jpg`, and `data/AISSMS_Canteen_Menu.xlsx`. The 18 Oct revision overrides older one-tap whole-order collection wording. Use latest images as primary UI targets, not generic templates.

## Build target
Student native Android Kotlin/Jetpack Compose application plus COE and IOIT canteen responsive React/TypeScript web dashboards, served by a FastAPI modular monolith with PostgreSQL. Preserve all approved student flows: any-Google login; institute selection remembered and switchable; browsing/menu/card ratings; one-canteen cart; real UPI gateway adapter; server-verified payments; five-minute post-payment student cancellation (except handed-over goods conflict); per-order six-digit pickup code with **no time expiry**; in-app order status/history/receipts; ratings, reviews and user photos; no QR or push notification. Include menu management, refunds, report filters, moderation/report threshold, merchant configuration requests, and role-based access.

## NEW NON-NEGOTIABLE MULTI-COUNTER REQUIREMENTS
- Separate COE vs IOIT tenants; each has central admin and configurable counter/station logins (Snacks/Juice/Meals initially, not hard-coded).
- Sessions should stay signed in across device restarts using secure rotating persisted sessions, with server-side revocation, never non-expiring admin tokens. Unique staff username and password per station, same login page.
- Map every menu item to a preparation station independently of food category. Admin can add/disable/rename stations and reassign menu items.
- Each paid order has **ONE payment and ONE six-digit code**; split its order lines into station queues. Each station views its own lines and may confirm only items it actually handed over. Main admin views and may selectively confirm all stations' lines. Physical verbal coordination remains manual.
- Code entry does lookup/preview only; no automatic redemption. A partially collected order retains its code; show remaining items/stations to student. Mark parent COLLECTED and invalidate code only when **every item/quantity** is handed over. Use concurrency-safe atomic DB updates, audit actor/device/time, prevent double redemption.
- Preserve five-minute cancellation for uncollected orders; when any item was already handed over, never blindly refund and cancel whole order. Build explicit exception/manual resolution workflow and document remaining policy approval.
- Real-time per-station orders and admin-wide updates with optional notification sound, reconnection fallback; no unnecessary walk-in POS/cash billing.

## Menu data
Use `data/AISSMS_Canteen_Menu.xlsx` as authoritative initial COE/IOIT menu, with `data/menu_seed_draft.json` as developer aid. Preserve categories and COE Jumbo/Small variants; verify unknown prices, disable any unverified item, keep source tracing, prevent repeat seed overwriting staff edits. Menu CRUD in admin is default; **do not build Excel upload**. Map every item to the station during onboarding; no guessing.

## Engineering and release discipline
Keep backend modules cohesive and independently testable; enforce tenant and station authorization at each endpoint; verified webhook and idempotent payment/refund operations; immutable price snapshots; audit logs; migrations; device-session revocation; secure media upload; deterministic review ranking; safe monitoring, backup/restore and clear deployment docs. Test Google tokens, payment replay, pickup races, partial collection, cancellation conflicts, incorrect pricing, station isolation and device loss. No unverified claims of passing tests.

## Execute NOW
1. Clone/open official repository and inspect its actual state; reconcile these files with existing changes (do not delete user work).
2. Initialize or update complete monorepo and `docs/implementation-progress.md`. Produce a concise architecture/status recap **but do not wait for routine approval**.
3. Build through all scoped phases sequentially with automated tests after each; distinguish real integrations from sandbox/test doubles. Build signed-release-capable Android tooling and deployment/staging docs. Maintain source of truth docs.
4. Commit & push **each completed, validated phase directly to `main`** as requested. Pull/reconcile before pushes; never force-push or bypass branch protections. Log commit SHA, tests run and blockers.
5. Continue automatically through phases within the available session. Do not pretend you can work in the background if execution stops. Stop only for truly missing external access or authorization and clearly report them; continue other implementable work where safe.
6. **No permission is given for live charges, merchant payout changes, public launch, paid hosting purchases, institution-branded production claims or destructive migrations.** These require separate explicit approval and appropriate merchant/campus ownership checks.

Deliver actual working code and tests, not just more planning documents. Start at once.
