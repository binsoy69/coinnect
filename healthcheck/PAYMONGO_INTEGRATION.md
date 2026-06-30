# PayMongo Integration Guide

This guide configures Coinnect PayMongo testing on Windows:

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
reverse proxy and use its public origin:

```text
https://healthcheck.example.com
```

For temporary sandbox testing, an HTTPS tunnel may be used. Point the tunnel
at the backend port, not the Vite frontend port:

```text
public HTTPS URL -> http://localhost:8010
```

Set only the origin in `HEALTHCHECK_PUBLIC_BASE_URL`; do not append `/api/v1`:

```env
HEALTHCHECK_PUBLIC_BASE_URL=https://healthcheck.example.com
```

Coinnect derives these URLs:

```text
Payment webhook:
https://healthcheck.example.com/api/v1/ewallet-sandbox/callbacks/payment

Transfer callback:
https://healthcheck.example.com/api/v1/ewallet-sandbox/callbacks/transfer
```

Restart the healthcheck backend after changing the URL. After login, the
PayMongo Sandbox panel displays both derived URLs.

### Manual Cloudflare Quick Tunnel on Windows

A Cloudflare Quick Tunnel provides a temporary public HTTPS URL without
requiring a domain or Cloudflare account. It is suitable for local testing,
not production. The URL changes whenever the tunnel is recreated.

Install `cloudflared`:

```powershell
winget install --id Cloudflare.cloudflared --exact `
  --accept-source-agreements `
  --accept-package-agreements
```

Close and reopen PowerShell, then verify:

```powershell
cloudflared --version
```

If the command is not added to `PATH`, use the common MSI installation path:

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" --version
```

Start the healthcheck backend in the first PowerShell window:

```powershell
cd D:\projects\coinnect\healthcheck\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn healthcheck_api.main:app `
  --host 127.0.0.1 `
  --port 8010
```

Start the tunnel in a second PowerShell window:

```powershell
cloudflared tunnel `
  --url http://127.0.0.1:8010 `
  --no-autoupdate
```

If `cloudflared` is not on `PATH`:

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel `
  --url http://127.0.0.1:8010 `
  --no-autoupdate
```

Cloudflare prints a generated URL similar to:

```text
https://random-words.trycloudflare.com
```

Keep both PowerShell windows open. Copy only the generated origin into
`healthcheck/backend/.env`:

```env
HEALTHCHECK_PUBLIC_BASE_URL=https://random-words.trycloudflare.com
```

Restart the healthcheck backend after editing `.env`. Register this complete
payment webhook in PayMongo Test Mode:

```text
https://random-words.trycloudflare.com/api/v1/ewallet-sandbox/callbacks/payment
```

The healthcheck creates this transfer callback automatically:

```text
https://random-words.trycloudflare.com/api/v1/ewallet-sandbox/callbacks/transfer
```

Do not register the transfer callback as another dashboard webhook.

Quick Tunnels expose the selected local service while they are running. Use
this direct `8010` setup only for temporary sandbox diagnostics. Stop the
tunnel with `Ctrl+C` after testing.

Official Cloudflare references:

- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)
- [Download cloudflared](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/)

## 3. Create the cash-out payment webhook

Cash-out uses a dynamic QR Ph Payment Intent. Coinnect waits for a signed
`payment.paid` event, retrieves the Payment Intent from PayMongo, and verifies
the amount, PHP currency, transaction metadata, paid status, and QR Ph source.

Create the webhook in the PayMongo Dashboard:

1. Log in to the [PayMongo Dashboard](https://dashboard.paymongo.com/).
2. Switch the account to **Test Mode**. Test-mode webhooks only receive events
   created with test API keys.
3. Open **Developer Tools > Webhooks**.
4. Select **Create Webhook** or **Add Endpoint**.
5. Enter the payment webhook URL shown in the Coinnect healthcheck panel:

   ```text
   https://healthcheck.example.com/api/v1/ewallet-sandbox/callbacks/payment
   ```

6. Subscribe to:

   ```text
   payment.paid
   ```

7. Create or save the webhook.
8. Copy the endpoint's webhook secret into:

   ```env
   PAYMONGO_WEBHOOK_SECRET=your_test_webhook_secret
   ```

9. Restart the healthcheck backend.

Do not use the transfer callback URL when creating this dashboard webhook.
Cash-in transfers receive their callback URL directly in the batch-transfer
request.

Official references:

- [Create a webhook in the dashboard](https://docs.paymongo.com/docs/developer-tools-dashboard-module-create-a-webhook)
- [Creating a webhook endpoint](https://docs.paymongo.com/docs/creating-a-webhook-endpoint)
- [Webhook key concepts](https://docs.paymongo.com/docs/developer-tools-webhooks-key-concepts)

## 4. Configure cash-in Money Movement

Cash-in creates an InstaPay batch transfer to the entered GCash or Maya test
account. The source account values must match an account attached to the
PayMongo wallet.

Retrieve the wallet details with the test secret key:

```bash
curl https://api.paymongo.com/v2/wallets \
  -u sk_test_REPLACE_ME:
```

Copy the source account fields into the healthcheck environment:

```env
PAYMONGO_SOURCE_ACCOUNT_NUMBER=0000000001
PAYMONGO_SOURCE_ACCOUNT_NAME=Coinnect
PAYMONGO_SOURCE_ACCOUNT_BIC=PAEYPHM2XXX
```

The exact values must come from the PayMongo account. Do not assume the example
number or BIC is valid for the configured wallet.

Each cash-in request sends this derived callback:

```text
https://healthcheck.example.com/api/v1/ewallet-sandbox/callbacks/transfer
```

When PayMongo calls it, Coinnect retrieves the batch transfer and verifies the
stored batch ID, transfer ID, and transaction reference before marking the
test verified.

If the wallet or Money Movement capability is unavailable, contact PayMongo to
enable the required test capability. Cash-out QR Ph may work even when
cash-in transfers are unavailable.

## 5. Complete environment configuration

Copy the example file:

```bash
cd healthcheck/backend
cp .env.example .env
```

Configure:

```env
PAYMONGO_API_URL=https://api.paymongo.com
PAYMONGO_SANDBOX=true
PAYMONGO_SECRET_KEY=sk_test_REPLACE_ME
PAYMONGO_PUBLIC_KEY=pk_test_REPLACE_ME
PAYMONGO_WEBHOOK_SECRET=REPLACE_WITH_ENDPOINT_SECRET

PAYMONGO_SOURCE_ACCOUNT_NUMBER=REPLACE_ME
PAYMONGO_SOURCE_ACCOUNT_NAME=Coinnect
PAYMONGO_SOURCE_ACCOUNT_BIC=REPLACE_ME

HEALTHCHECK_PUBLIC_BASE_URL=https://healthcheck.example.com
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
python -m uvicorn healthcheck_api.main:app --host 0.0.0.0 --port 8010
```

Start the frontend:

```bash
cd healthcheck/frontend
npm run dev
```

After logging in:

1. Open the **PayMongo Sandbox** panel.
2. Confirm it reports configured/ready and displays the expected public URLs.
3. Run **GCash Cash Out** or **Maya Cash Out**.
4. Open the returned sandbox payment URL or scan the QR code.
5. Complete the test payment and wait for `Verified`.
6. Run a cash-in test using approved PayMongo sandbox recipient details.
7. Wait for the batch transfer callback and `Verified`.

To verify that the payment callback is publicly reachable without forging a
PayMongo signature:

```bash
curl -i -X POST \
  https://healthcheck.example.com/api/v1/ewallet-sandbox/callbacks/payment \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected result:

```text
HTTP/1.1 401 Unauthorized
```

A `401` is expected because the manual request has no valid
`Paymongo-Signature`. It confirms that the public route reaches Coinnect. A
timeout, DNS error, TLS error, or proxy-generated `404` means the public
routing is not configured correctly.

## 7. Troubleshooting

### Panel says `Not configured`

Use the missing-settings list shown in the panel. Restart the backend after
editing `.env`.

### Webhook never completes cash-out

- Confirm the webhook was created in **Test Mode**.
- Confirm it subscribes to `payment.paid`.
- Confirm the URL exactly matches the payment callback shown in the panel.
- Confirm `PAYMONGO_WEBHOOK_SECRET` belongs to that endpoint.
- Check the PayMongo webhook delivery history and retry failed deliveries.
- Confirm the public endpoint returns a `2xx` response for genuine PayMongo
  requests.

PayMongo treats HTTP `200` through `209` as successful webhook delivery and
retries failed deliveries automatically.

### Payment callback returns `401`

The signature is missing, stale, malformed, or signed with a different webhook
secret. Do not disable signature verification. Update the configured secret to
match the test-mode endpoint.

### Cash-in remains pending

- Confirm Money Movement is enabled.
- Confirm the source account fields match the PayMongo wallet.
- Confirm the transfer request contains the public transfer callback URL.
- Check the batch transfer status and callback delivery in PayMongo.
- Confirm the destination test account name and number are valid.

### Cash-in fails immediately

Typical causes include insufficient wallet balance, invalid destination account
details, or unavailable receiving institutions. Review the sanitized error in
the healthcheck panel and the full transaction in PayMongo.

## 8. Live-mode support

The healthcheck integration supports both sandbox keys (`sk_test_`/`pk_test_`) and live keys (`sk_live_`/`pk_live_`).

> [!WARNING]
> Running diagnostics using live credentials (`PAYMONGO_SANDBOX=false`) **will result in real financial transactions**.
> - Sandbox cash-out will create a live QR Ph Payment Intent, which will deduct real money from the customer's e-wallet upon payment.
> - Sandbox cash-in will execute real batch transfers (InstaPay) out of your live PayMongo source wallet to the destination account.
> - Because the healthcheck does not interface with physical cash handling hardware for e-wallet diagnostics, **no physical cash is accepted or dispensed**. Use the smallest possible amounts when testing live connections.

### Testing live keys on Windows with mock hardware

Use the actual backend—not the healthcheck—when only the live PayMongo account
has Wallet/Money Movement access. Live cash-in creates a real transfer from the
PayMongo Wallet, and live cash-out creates a real payment. Mock hardware
prevents GPIO, Arduino, camera, and dispenser activity; it does not mock
PayMongo.

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

Never place live credentials in the frontend or commit `backend/.env`.

#### Start the actual backend

In the first PowerShell window:

```powershell
cd D:\projects\coinnect\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app `
  --host 127.0.0.1 `
  --port 8000
```

Verify it locally:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

#### Start the callback-only proxy

Do not point a public Quick Tunnel directly at port `8000`. The actual backend
contains unauthenticated kiosk and hardware-control routes. Instead, run the
included allowlist proxy, which exposes only:

```text
/api/v1/ewallet/webhook
/api/v1/ewallet/transfer-callback
```

In the second PowerShell window:

```powershell
cd D:\projects\coinnect
backend\.venv\Scripts\python.exe scripts\paymongo_callback_proxy.py
```

The proxy listens on `http://127.0.0.1:8020`.

#### Start the live callback tunnel

In the third PowerShell window:

```powershell
cloudflared tunnel `
  --url http://127.0.0.1:8020 `
  --no-autoupdate
```

Copy the generated `https://random-words.trycloudflare.com` origin. Set the
actual backend transfer callback:

```env
PAYMONGO_TRANSFER_CALLBACK_URL=https://random-words.trycloudflare.com/api/v1/ewallet/transfer-callback
```

Restart the actual backend so it reloads `.env`.

In PayMongo Dashboard, switch to **Live Mode**, create a webhook endpoint with:

```text
https://random-words.trycloudflare.com/api/v1/ewallet/webhook
```

Subscribe it to `payment.paid`, copy its endpoint secret into
`PAYMONGO_WEBHOOK_SECRET`, and restart the backend again.

#### Verify the public route allowlist

An unsigned payment webhook must reach Coinnect and return `401`:

```powershell
try {
  Invoke-WebRequest `
    -Method Post `
    -Uri "https://random-words.trycloudflare.com/api/v1/ewallet/webhook" `
    -ContentType "application/json" `
    -Body "{}"
} catch {
  $_.Exception.Response.StatusCode.value__
}
```

Expected:

```text
401
```

A non-callback route must be blocked by the proxy:

```powershell
try {
  Invoke-WebRequest `
    -Uri "https://random-words.trycloudflare.com/api/v1/health"
} catch {
  $_.Exception.Response.StatusCode.value__
}
```

Expected:

```text
404
```

Keep all three PowerShell windows open while testing. Stop the tunnel, proxy,
and backend with `Ctrl+C`.

Every new Quick Tunnel has a different URL. Whenever it changes:

1. Update `PAYMONGO_TRANSFER_CALLBACK_URL` in `backend/.env`.
2. Update or recreate the PayMongo live webhook endpoint.
3. Copy the new webhook secret into `PAYMONGO_WEBHOOK_SECRET` if PayMongo
   issues a new secret.
4. Restart the actual backend.

For live smoke tests, use an account you control and the smallest supported
amount. PayMongo fees may apply, and mock cash insertion does not fund a real
cash-in transfer.

For Raspberry Pi or long-running production deployment, replace the Quick
Tunnel with a named Cloudflare Tunnel and stable hostname. Quick Tunnels have
no uptime guarantee.
