# PayMongo Integration Guide

This guide configures Coinnect PayMongo testing on Windows and Raspberry Pi:

- The healthcheck backend uses PayMongo test keys and never accepts or
  dispenses physical cash.
- The actual backend can run with mock hardware and live PayMongo keys when a
  test wallet is unavailable. Live mode moves real money even though the
  hardware is mocked.

## 1. PayMongo account requirements

The PayMongo account must provide:

- Test public and secret API keys.
- QR Ph payment acceptance for cash-out testing.
- Money Movement access and a test wallet/source account for cash-in testing.
- An externally reachable HTTPS URL for the healthcheck backend.

PayMongo test keys use these prefixes:

- Public: `pk_test_`
- Secret: `sk_test_`

Find them in the PayMongo Dashboard under **Developers** or **API Keys**. Never
put the secret key in the frontend configuration or commit it to Git.

Official references:

- [PayMongo API keys](https://docs.paymongo.com/docs/account-settings-api-keys)
- [QR Ph API](https://docs.paymongo.com/docs/payment-acceptance-qr-ph-api)
- [Move money with the API](https://docs.paymongo.com/docs/money-movement-moving-money-with-api)

## 2. Expose the healthcheck backend over HTTPS

PayMongo must be able to send requests from the internet to the healthcheck
backend. A private address such as `localhost`, `192.168.x.x`, or a `.local`
hostname is not sufficient.

For deployed environments, place the healthcheck backend behind an HTTPS
reverse proxy or Cloudflare Tunnel and use its public origin:

```text
https://healthcheck.example.com
```

Point the tunnel at the backend port, not the Vite frontend port:

```text
public HTTPS URL -> http://localhost:8010
```

Set only the origin in `HEALTHCHECK_PUBLIC_BASE_URL` in `.env`; do not append `/api/v1`:

```env
HEALTHCHECK_PUBLIC_BASE_URL=https://healthcheck.example.com
```

Coinnect derives the main webhook URL from this origin:

```text
Webhook Endpoint:
https://healthcheck.example.com/api/v1/ewallet-sandbox/callbacks/payment
```

Restart the healthcheck backend after changing the URL. After login, the
PayMongo Sandbox panel displays the derived URL.

---

### Option A: Persistent Cloudflare Named Tunnel (Recommended for stable uptime)

A Cloudflare Named Tunnel routes traffic securely through a custom domain that you own (e.g., `healthcheck.yourdomain.com`). It is stable, survives machine restarts, and does not change URLs.

#### 1. Setup on Cloudflare Dashboard
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. Navigate to **Zero Trust > Networks > Tunnels** and click **Create a Tunnel**.
3. Select **cloudflared**, name your tunnel (e.g., `coinnect-kiosk`), and click **Save tunnel**.
4. Copy the installation command containing your tunnel token.

#### 2. Installing on Windows
Run PowerShell as Administrator:
```powershell
# Install cloudflared via winget
winget install --id Cloudflare.cloudflared --exact --accept-source-agreements --accept-package-agreements

# Close and reopen PowerShell, then install the tunnel as a service:
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" service install YOUR_TUNNEL_TOKEN
```
Verify the service is running:
```powershell
Get-Service -Name "cloudflared"
```

#### 3. Installing on Raspberry Pi (Debian/Linux)
SSH into your Raspberry Pi and run:
```bash
# Add Cloudflare package repository
curl -L https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflare-main.gpg $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare.list

# Install cloudflared
sudo apt update && sudo apt install -y cloudflared

# Install and start as a systemd daemon service
sudo cloudflared service install YOUR_TUNNEL_TOKEN
```
Verify the status:
```bash
sudo systemctl status cloudflared
```

#### 4. Configure Public Hostname
In the Cloudflare Zero Trust Tunnel Dashboard:
1. Click **Configure** on your tunnel.
2. Select the **Public Hostname** tab and click **Add a public hostname**.
3. Fill in:
   - **Subdomain / Domain**: e.g., `healthcheck` / `yourdomain.com`
   - **Service Type**: `HTTP`
   - **URL**: `localhost:8010` (for healthcheck backend) or `localhost:8020` (for production callback proxy)
4. Save the configuration. Set `HEALTHCHECK_PUBLIC_BASE_URL=https://healthcheck.yourdomain.com` in `.env` and restart the backend.

---

### Option B: Temporary Cloudflare Quick Tunnel (Local Testing Only)

A Cloudflare Quick Tunnel provides a temporary public HTTPS URL without requiring a domain or Cloudflare account. The URL changes whenever the tunnel is recreated.

Start the healthcheck backend in the first PowerShell window:
```powershell
cd D:\projects\coinnect\healthcheck\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn healthcheck_api.main:app --host 127.0.0.1 --port 8010
```

Start the quick tunnel in a second PowerShell window:
```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8010 --no-autoupdate
```

Copy the generated `https://random-words.trycloudflare.com` origin into `healthcheck/backend/.env`:
```env
HEALTHCHECK_PUBLIC_BASE_URL=https://random-words.trycloudflare.com
```
Restart the healthcheck backend after editing `.env`.

---

## 3. Create the webhook in PayMongo Dashboard

Coinnect uses a unified signed webhook endpoint to process both payment acceptance (cash-out) and money transfers (cash-in).

Create the webhook endpoint in the PayMongo Dashboard:

1. Log in to the [PayMongo Dashboard](https://dashboard.paymongo.com/).
2. Switch the account to **Test Mode** (or Live Mode for production).
3. Open **Developer Tools > Webhooks** and select **Create Webhook** or **Add Endpoint**.
4. Enter the webhook URL shown in the Coinnect healthcheck panel:
   - **Healthcheck**: `https://<domain>/api/v1/ewallet-sandbox/callbacks/payment`
   - **Production Kiosk**: `https://<domain>/api/v1/ewallet/webhook`
5. Subscribe to **exactly these three events**:
   - `payment.paid`
   - `transfer.outward.successful`
   - `transfer.outward.failed`
6. Save the webhook.
7. Copy the endpoint's webhook secret into your `.env` configuration:
   ```env
   PAYMONGO_WEBHOOK_SECRET=your_webhook_secret
   ```
8. Restart the backend service.

Official references:
- [Create a webhook in the dashboard](https://docs.paymongo.com/docs/developer-tools-dashboard-module-create-a-webhook)
- [Creating a webhook endpoint](https://docs.paymongo.com/docs/creating-a-webhook-endpoint)

## 4. Configure cash-in Money Movement

Cash-in creates an InstaPay batch transfer to the entered GCash or Maya test account. The source account values must match an account attached to the PayMongo wallet.

Retrieve the wallet details with your secret key:
```bash
curl https://api.paymongo.com/v2/wallets -u sk_test_REPLACE_ME:
```

Copy the source account fields into the environment:
```env
PAYMONGO_SOURCE_ACCOUNT_NUMBER=0000000001
PAYMONGO_SOURCE_ACCOUNT_NAME=Coinnect
PAYMONGO_SOURCE_ACCOUNT_BIC=PAEYPHM2XXX
```

Cash-in transfers no longer rely on any request-specific callback URLs. They are verified and completed asynchronously when PayMongo delivers the signed dashboard webhook events (`transfer.outward.successful` or `transfer.outward.failed`).

## 5. Complete environment configuration

Copy the example file:
```bash
cd healthcheck/backend
cp .env.example .env
```

Configure your `.env`:
```env
PAYMONGO_API_URL=https://api.paymongo.com
PAYMONGO_SANDBOX=true
PAYMONGO_SECRET_KEY=sk_test_REPLACE_ME
PAYMONGO_PUBLIC_KEY=pk_test_REPLACE_ME
PAYMONGO_WEBHOOK_SECRET=REPLACE_WITH_ENDPOINT_SECRET

PAYMONGO_SOURCE_ACCOUNT_NUMBER=REPLACE_ME
PAYMONGO_SOURCE_ACCOUNT_NAME=Coinnect
PAYMONGO_SOURCE_ACCOUNT_BIC=REPLACE_ME

HEALTHCHECK_PUBLIC_BASE_URL=https://healthcheck.yourdomain.com
HEALTHCHECK_EWALLET_DB_URL=sqlite+aiosqlite:///./healthcheck_ewallet.db
HEALTHCHECK_EWALLET_TIMEOUT_SECONDS=600
HEALTHCHECK_EWALLET_RETENTION_LIMIT=100
```

The healthcheck rejects session creation unless:
- `PAYMONGO_SANDBOX` matches the key prefixes (`true` for `sk_test_`/`pk_test_`, and `false` for `sk_live_`/`pk_live_`)
- A webhook secret is configured
- Source account fields are configured
- `HEALTHCHECK_PUBLIC_BASE_URL` uses HTTPS

## 6. Start and verify the integration

Start the backend:
```bash
cd healthcheck/backend
python -m uvicorn healthcheck_api:main:app --host 0.0.0.0 --port 8010
```

Start the frontend:
```bash
cd healthcheck/frontend
npm run dev
```

After logging in:
1. Open the **PayMongo Sandbox** panel.
2. Confirm it reports configured/ready and displays the expected public URL.
3. Run **GCash Cash Out** or **Maya Cash Out** tests, scan the QR code, pay, and wait for `Verified`.
4. Run a cash-in test, wait for the batch transfer webhook event to deliver, and check if it resolves to `Verified`.

Verify public route signature check:
```bash
curl -i -X POST https://healthcheck.yourdomain.com/api/v1/ewallet-sandbox/callbacks/payment -H "Content-Type: application/json" -d '{}'
```
Expected result: `HTTP/1.1 401 Unauthorized`

---

## 7. Live-mode support

The healthcheck integration supports both sandbox keys (`sk_test_`/`pk_test_`) and live keys (`sk_live_`/`pk_live_`).

> [!WARNING]
> Running diagnostics using live credentials (`PAYMONGO_SANDBOX=false`) **will result in real financial transactions**.
> Use the smallest possible amounts when testing live connections. No physical cash is accepted or dispensed.

### Testing live keys with mock hardware on Kiosk backend

Configure `backend/.env`:
```env
HOST=127.0.0.1
PORT=8000
ENVIRONMENT=staging
ENABLE_DOCS=true

USE_MOCK_SERIAL=true
USE_MOCK_HARDWARE=true
SERIAL_PORT_BILL=MOCK_BILL
SERIAL_PORT_COIN=MOCK_COIN

DB_URL=sqlite+aiosqlite:///./coinnect_live_smoke.db

PAYMONGO_API_URL=https://api.paymongo.com
PAYMONGO_SANDBOX=false
PAYMONGO_SECRET_KEY=sk_live_REPLACE_ME
PAYMONGO_PUBLIC_KEY=pk_live_REPLACE_ME
PAYMONGO_WEBHOOK_SECRET=REPLACE_AFTER_CREATING_THE_WEBHOOK

PAYMONGO_SOURCE_ACCOUNT_NUMBER=REPLACE_WITH_LIVE_WALLET_ACCOUNT
PAYMONGO_SOURCE_ACCOUNT_NAME=Coinnect
PAYMONGO_SOURCE_ACCOUNT_BIC=REPLACE_WITH_LIVE_WALLET_BIC
```

#### Start the actual backend
```powershell
cd D:\projects\coinnect\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

#### Start the callback-only proxy
Do not point a public Cloudflare domain/tunnel directly at port `8000` because the kiosk API contains unauthenticated hardware controls. Run the included allowlist proxy instead, which exposes only the webhook route:

```powershell
cd D:\projects\coinnect
backend\.venv\Scripts\python.exe scripts\paymongo_callback_proxy.py
```
The proxy listens on `http://127.0.0.1:8020` and only allows POST requests to `/api/v1/ewallet/webhook`.

#### Start the live callback tunnel
Map your Cloudflare named tunnel or quick tunnel to port `8020` (e.g. `https://kiosk.yourdomain.com`).

In PayMongo Dashboard, switch to **Live Mode**, create a webhook endpoint with:
```text
https://kiosk.yourdomain.com/api/v1/ewallet/webhook
```
Subscribe it to:
- `payment.paid`
- `transfer.outward.successful`
- `transfer.outward.failed`

Copy the new webhook secret into `PAYMONGO_WEBHOOK_SECRET` in `backend/.env`, restart the backend, and verify the webhook endpoint.
