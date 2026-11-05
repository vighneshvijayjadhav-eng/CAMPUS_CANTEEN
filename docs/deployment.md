# Local setup and release gates

This repository is not ready for live student payments or public rollout.

## Local backend

Install Python 3.13+ (current lock tested with 3.14), uv, Node 24 and Docker Desktop with
a functioning Linux engine, or a separately managed local PostgreSQL 18 instance.

From repository root:

```powershell
Copy-Item .env.example .env
# Edit the local file: generate independent random password/key, never use placeholders.
# Add GOOGLE_OAUTH_CLIENT_ID only after an Android OAuth client is provisioned.
docker compose --env-file .env -f infra/compose.yml up -d db
uv sync --project services/api --locked
Set-Location services/api
# Set DATABASE_URL and PICKUP_HMAC_KEY in this shell, or a local services/api/.env.
uv run alembic upgrade head
uv run python -m app.modules.menu.seed ../../data/AISSMS_Canteen_Menu.xlsx --compare-draft ../../data/menu_seed_draft.json
uv run python -m app.modules.identity.provision coe coe-admin
uv run python -m app.modules.identity.provision ioit ioit-admin
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Seed/provisioning commands read DATABASE_URL from the shell. The API also reads a local
.env in its working directory. Generate the HMAC secret with Python `secrets.token_urlsafe(48)`.
Do not put production keys, student records or passwords in Git or command arguments.

## Local web

```powershell
Set-Location apps/canteen-web
npm ci
npm run dev
```

Open http://localhost:5173, matching WEB_ORIGIN exactly. Provision an admin first, create
stations in the dashboard, then provision each station account with its UUID:
`uv run python -m app.modules.identity.provision coe juice-operator --station STATION_UUID`.
No station names or menu mappings are guessed by the seed. A station being disabled does
not delete its old fulfillment lines; the admin can handle those items.

## Verification

From services/api: `uv run ruff check app tests migrations`,
`uv run ruff format --check app tests migrations`, `uv run pytest -q`.
On restricted Windows hosts use a writable `--basetemp` directory within the workspace.
Set TEST_DATABASE_URL to a disposable PostgreSQL test database for race tests. Tests create
and remove only their own random schemas, never use production credentials. CI runs these
tests and checks the migration and idempotent workbook seed against PostgreSQL 18.
From apps/canteen-web: `npm test` and `npm run build`.

## Production gates (not yet passed)

Use docs/PRODUCTION_READINESS.md as controlling checklist. Required work includes Google
and gateway sandbox end-to-end verification, approved exception/refund policy, native APK,
HTTPS reverse proxy, configured trusted Origin, rate-limit proxy/IP policy, encrypted
credential issuance and secret rotation, security/load/accessibility testing and operational
ownership. No public deployment is authorized by the local commands above. Without a configured
Google OAuth client ID, student login correctly returns GOOGLE_AUTH_NOT_CONFIGURED rather than
trusting an unverified ID token.

Before staging data exists, define retention, backup RPO/RTO and ownership. A restoration
drill must restore a pg_dump archive into a separate disposable PostgreSQL database and
verify migrations, order totals and fulfillment counts before any production go-live.
Do not test restore over a live database. No restore drill has been performed yet.

## Student Android app (local build)

Requires JDK 17+ and the Android SDK (platform 35, build-tools 34). Keep the Gradle cache on a
drive with several GB free: the default `%USERPROFILE%\.gradle` is fine, but do not point
`GRADLE_USER_HOME` at a small drive.

```bash
cd apps/student-android
echo "sdk.dir=C:/Users/<you>/AppData/Local/Android/Sdk" > local.properties   # forward slashes
./gradlew assembleDebug                      # APK: app/build/outputs/apk/debug/app-debug.apk
./gradlew assembleDebug -PapiBaseUrl=http://192.168.x.x:8000   # physical device on LAN
```

The emulator default `API_BASE_URL` is `http://10.0.2.2:8000` (host machine's port 8000).

## Razorpay test-mode setup (per canteen)

1. In the Razorpay Dashboard (Test Mode) for the canteen's merchant account, create API keys.
2. Put them in server configuration only, keyed by key id:
   `RAZORPAY_CREDENTIALS={"rzp_test_xxx": {"key_secret": "...", "webhook_secret": "..."}}`
   (choose the webhook secret yourself; it is entered again in step 4).
3. Register and activate the account:

```bash
uv run python -m app.modules.payments.admin add-merchant coe rzp_test_xxx "COE Canteen" --activate
```

4. In Dashboard > Webhooks add `https://<api-host>/api/v1/payments/razorpay/webhooks/<id printed
   above>` with the same secret and events `payment.captured`, `payment.failed`, `order.paid`,
   `refund.created`, `refund.processed`, `refund.failed`.
   Razorpay needs a public HTTPS URL; for local tests use a tunnel you control.
5. Schedule reconciliation every few minutes. It recovers missed payment webhooks, sends queued
   refunds (duplicate/wrong-amount payments, refunds that hit a Razorpay outage) and polls
   pending refunds:

```bash
uv run python -m app.modules.payments.admin reconcile
```

Live keys (`rzp_live_`) are refused unless `ENVIRONMENT=production` and `ALLOW_LIVE_PAYMENTS=true`,
which require the college/canteen approvals listed in PRODUCTION_READINESS.md.
