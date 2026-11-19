# Demo environment (free hosting)

A shareable demo of the whole system: staff dashboard on **Vercel**, API on **Render** (free
web service, Docker), database on **Neon** (free PostgreSQL), payments in **Razorpay test
mode**, and the student Android app as an APK. Everything here is test/demo data; no real money
moves.

| Part | Where | Address (default names) |
|---|---|---|
| Staff dashboard | Vercel | `https://aissms-canteen.vercel.app` |
| API | Render (free) | `https://aissms-canteen-api.onrender.com` |
| Database | Neon (free) | from the Neon dashboard |
| Student app | APK shared by link | built from `apps/student-android` |

Free-plan limits (check each pricing page when signing up): the Render API sleeps after about
15 minutes without traffic, so the first request after a pause takes up to a minute; Render's
free plan has no permanent disk, so **review photos disappear when the API restarts or
redeploys** (orders, reviews and everything else live in the database and stay).

## One-time setup (about 30 minutes)

### 1. Database: Neon
1. Sign up at neon.tech (GitHub sign-in works) and create a project, region **Asia Pacific
   (Singapore)**.
2. Copy the connection string (`postgresql://...?sslmode=require`). Keep it private.

### 2. API: Render
1. Sign up at render.com with GitHub and allow access to the `CAMPUS_CANTEEN` repository.
2. **New → Blueprint**, choose the repository. Render reads `render.yaml` and proposes the
   `aissms-canteen-api` web service on the free plan.
3. Fill in the secret values it asks for:
   - `DATABASE_URL`: the Neon connection string.
   - `DEMO_STAFF_PASSWORD`: a password of 14+ characters for all demo staff logins.
   - `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET`: your Razorpay **test** values.
4. Deploy. On start the container applies migrations, loads the menu and creates the demo
   data (see "What the demo contains"). The log ends with `Demo ready.` and the webhook path.
5. If Render gives the service a different address than
   `https://aissms-canteen-api.onrender.com`, tell Claude: the dashboard config and APK must
   use the real address.
6. Open `https://<api-address>/health`; it should show `{"status":"ok",...}`.

### 3. Dashboard: Vercel
1. In Vercel: **Add New → Project**, import the repository, set **Root Directory** to
   `apps/canteen-web`. Vercel picks up `vercel.json` (Vite build, `/api` forwarded to Render).
2. Name the project `aissms-canteen` so the address is `https://aissms-canteen.vercel.app`. If
   that name is taken, set Render's `WEB_ORIGIN` to the address Vercel gives and redeploy the API
   (staff sign-in only works from that exact address).
3. Open the address and sign in as `coe-admin` with the demo password.

### 4. Razorpay test webhooks (optional, recommended)
In the Razorpay Dashboard (Test Mode) → Webhooks → Add: URL
`https://<api-address>/api/v1/payments/razorpay/webhooks/<id>` (the id is printed in the Render
log line "webhook path", and shown on the dashboard's Settings page), secret = your
`RAZORPAY_WEBHOOK_SECRET`, events `payment.captured`, `payment.failed`, `order.paid`,
`refund.created`, `refund.processed`, `refund.failed`. Without webhooks the API still confirms
payments and refunds itself every 3 minutes.

### 5. Student app
Install `CampusCanteen-demo.apk` (shared by link) on each Android demo phone: open the file and
allow "install unknown apps" when asked. Sign in with any Google account. The APK is built on
the owner's PC with its debug key, whose SHA-1 is registered in Google Cloud, so sign-in works on
any phone. If the API address changes, the APK must be rebuilt:
`./gradlew assembleDebug -PapiBaseUrl=https://<api-address>`.

## What the demo contains
- Both institutes and canteens approved and open (no opening hours set, so always open).
- Menu from `data/AISSMS_Canteen_Menu.xlsx` (demo edition: owner-corrected prices, unclear and
  duplicate items removed). **Club Sandwich** (COE) and **Paneer Pulao** (IOIT) are marked
  unavailable to show that state.
- Three counters per canteen: **Snacks**, **Beverages**, **Meals**, with every item mapped.
- Staff logins (same demo password): `coe-admin`, `coe-snacks`, `coe-beverages`, `coe-meals`,
  `ioit-admin`, `ioit-snacks`, `ioit-beverages`, `ioit-meals`.
- Online payment (Razorpay test mode) for **COE**. IOIT shows "online payment isn't set up"
  because one Razorpay account can belong to one canteen; a second Razorpay test account would
  enable IOIT.
- Two weeks of demo order history with reviews from four demo students (names end in "(demo)",
  payments marked "Demo history (not real payments)"), so Sales, Reviews and ratings have data.

## Demo script (about 15 minutes)

**Student (phone)**
1. Sign in with Google → choose the institute (COE).
2. Open COE Canteen: categories, star ratings, an unavailable item, Jumbo/Small sizes on juices.
3. Tap "Reviews" on an item to see demo reviews.
4. Add items from two counters (e.g. Masala Dosa and Limbu Soda) → cart → **Pay**.
5. In Razorpay test checkout choose **Netbanking** → any bank → **Success** (cards/UPI may be
   disabled on the test account).
6. The order screen shows the **six-digit pickup code**, items per counter, and the 5-minute
   cancel countdown. The **Alerts** tab shows "Payment confirmed".

**Counter staff (laptop/tablet, dashboard)**
7. Sign in as `coe-meals`: the paid order appears (with sound if enabled) showing only the
   Meals items. Enter the student's code → **look up only**, nothing is collected yet.
8. Confirm the Masala Dosa handed over. The student's app shows "Partly collected" and the
   remaining counter.
9. Sign in as `coe-beverages` (another browser/profile) and confirm the drink. The order becomes
   **Collected**, the code stops working, the student gets "Order collected".

**Student again**
10. Rate the collected item with a photo → it appears on the menu.
11. Place another order and **cancel within 5 minutes** → refund. In test mode the refund may
    wait for Razorpay balance; the dashboard Refunds page shows "Retrying automatically".

**Canteen admin (`coe-admin`)**
12. **Menu**: change a price or mark an item unavailable; the phone shows it on refresh.
13. **Stations**: rename or add a counter and move an item to it.
14. **Sales**: day/week/month totals and item-wise sales (includes demo history).
15. **Refunds**, **Reviews** (restore/remove reported reviews), **Settings** (pause ordering,
    opening hours, Razorpay account details), **Devices** (sign out a lost tablet).

## Resetting the demo
Delete and recreate the Neon database (or its branch) and redeploy the Render service; the
start-up steps rebuild everything. To stop creating demo data, set `DEMO_MODE=0` on Render.

## Not for real students
The demo uses Razorpay test mode, demo staff passwords and sample data. A real launch needs the
items in `docs/PRODUCTION_READINESS.md` (merchant accounts, approvals, hosting with persistent
photo storage, backups, privacy policy approval).
