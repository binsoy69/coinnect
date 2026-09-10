# PayMongo Cloudflare Tunnel Setup Guide (Raspberry Pi)

This guide describes how to configure and deploy a secure, persistent Cloudflare Named Tunnel on the Raspberry Pi to receive PayMongo e-wallet webhook callbacks in production.

---

## Architecture Overview

For security reasons, **do not point a public Cloudflare tunnel directly at the main kiosk API (port `8000`)**. The main kiosk API contains unauthenticated hardware control endpoints (bill dispensers, coin sorters, security overrides). 

Instead, we use a callback-only proxy script ([paymongo_callback_proxy.py](scripts/paymongo_callback_proxy.py)) running on port `8020` that forwards only POST requests destined for the `/api/v1/ewallet/webhook` route. The backend verifies the signature against the original request body.

```
                           +------------------------+
                           |   PayMongo Dashboard   |
                           +-----------+------------+
                                       |
                                       | HTTPS Webhook POST
                                       v
                           +-----------+------------+
                           |    Cloudflare Edge     |
                           +-----------+------------+
                                       |
                                       | Secure Tunnel Connection
                                       v
 +-------------------------------------+-------------------------------------+
 | Raspberry Pi 4/5                                                          |
 |                                                                           |
 |   +----------------------+               +----------------------------+   |
 |   |  Cloudflare Daemon   |               |   PayMongo Callback Proxy  |   |
 |   |    (cloudflared)     | ------------> | (paymongo_callback_proxy.py|   |
 |   +----------------------+  localhost    +-------------+--------------+   |
 |                             port 8020                  |                  |
 |                                                        | HTTP Forward     |
 |                                                        | (localhost)      |
 |                                                        v                  |
 |                                          +-------------+--------------+   |
 |                                          |    Coinnect Kiosk Backend  |   |
 |                                          |           (main.py)        |   |
 |                                          +----------------------------+   |
 |                                                      port 8000            |
 +---------------------------------------------------------------------------+
```

---

## Prerequisites

1. Your Raspberry Pi must be fully set up and configured using the [setup_rpi.sh](scripts/setup_rpi.sh) script.
2. The main kiosk service (`coinnect.service`) should be configured, though it does not need to be running yet.
3. You must have a custom domain managed under your Cloudflare account (e.g., `yourdomain.com`).
4. Confirm live QR Ph acceptance and Wallet/Transfers access in your PayMongo account for this kiosk use case. Cash-out uses QR Ph Payment Intents; cash-in uses an activated, funded PayMongo Wallet to transfer to GCash/Maya. Copy the provisioned source account number, name, and BIC; do not substitute a customer's wallet number. See [PayMongo transfer setup](https://docs.paymongo.com/docs/money-movement-moving-money-with-api).
5. Complete the [hardware and recovery acceptance scenarios](reference/11_ewallet_reliability.md#validation) before opening customer service. Keep the kiosk closed while switching credentials and rebuilding the UI.

These commands assume user `pi` and checkout `/home/pi/coinnect`. Adjust both systemd units if your installation differs. Use a persistent production hostname rather than a temporary `trycloudflare.com` address.

---

## Step 1: Install Cloudflare Tunnel Daemon on Raspberry Pi

SSH into your Raspberry Pi and add the official Cloudflare package repository:

```bash
# 1. Install the current signing key and add the stable Debian repository
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflare.list

# 2. Update package lists and install cloudflared
sudo apt update && sudo apt install -y cloudflared
```

This replaces the `cloudflare.list` created by earlier versions of this guide.
The `.gpg` URL is only the signing key, not an APT repository. Cloudflare recommends
the `cloudflared any main` repository for Debian-based distributions, including
Raspberry Pi OS Trixie. See [official package instructions](https://pkg.cloudflare.com/index.html).

Verify the installation succeeded by checking the version:
```bash
cloudflared --version
```

---

## Step 2: Create a Tunnel in the Cloudflare Dashboard

1. Log in to the [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/).
2. Navigate to **Networks > Tunnels** and click **Create a Tunnel**.
3. Select **cloudflared** as the connector type and click **Next**.
4. Name your tunnel (e.g., `coinnect-kiosk-rpi`) and click **Save tunnel**.
5. The dashboard will show you the installation commands for various environments. Under **Debian (arm64)** or **Debian (amd64)**, copy **only the token string** at the very end of the command (e.g., the long string of letters and numbers after `service install`).

---

## Step 3: Run the Cloudflare Tunnel Service on RPi

Back on your Raspberry Pi terminal, register the tunnel as a systemd service using the token you copied:

```bash
# Install and start the cloudflared daemon service
sudo cloudflared service install YOUR_TUNNEL_TOKEN
```

Verify that the service is running and active:
```bash
sudo systemctl status cloudflared
```

---

## Step 4: Install the Callback Proxy Service

To automate running the callback proxy on boot, install the provided systemd service unit:

```bash
# 1. Copy the proxy service file template to systemd
sudo cp systemd/coinnect-proxy.service /etc/systemd/system/

# 2. Reload systemd daemon
sudo systemctl daemon-reload

# 3. Enable the service to start automatically at boot
sudo systemctl enable coinnect-proxy.service

# 4. Start the service immediately
sudo systemctl start coinnect-proxy.service
```

Verify that the proxy service has started successfully and is listening on port `8020`:
```bash
sudo systemctl status coinnect-proxy.service
sudo journalctl -u coinnect-proxy.service -n 20 --no-pager
```

---

## Step 5: Configure Public Hostname Routing

In the Cloudflare Zero Trust Dashboard under your created tunnel configuration:

1. Click **Configure** on your tunnel.
2. Select the **Public Hostname** tab and click **Add a public hostname**.
3. Configure the hostname routing as follows:
   * **Subdomain**: e.g., `kiosk` (or leave blank if using the root domain)
   * **Domain**: select your registered domain (e.g., `yourdomain.com`)
   * **Path**: leave empty
   * **Type**: `HTTP`
   * **URL**: `localhost:8020`
4. Click **Save hostname**.

Traffic sent to `https://kiosk.yourdomain.com` will now route securely to port `8020` on your Raspberry Pi.

---

## Step 6: Configure PayMongo Webhooks

With the public URL active, register it inside your PayMongo developer account:

1. Log in to the [PayMongo Dashboard](https://dashboard.paymongo.com/).
2. Switch to **Live Mode** (or test mode if performing a dry run).
3. Navigate to **Developers > Webhooks** and click **Register Webhook**.
4. Enter the public endpoint URL:
   ```text
   https://kiosk.yourdomain.com/api/v1/ewallet/webhook
   ```
5. Select the required webhook subscription events:
   * `payment.paid` (critical for cash-out notifications)
   * `transfer.outward.successful`
   * `transfer.outward.failed`
6. Save the endpoint and copy its signing secret privately into the backend configuration. Use the secret belonging to this live endpoint, not the API secret key. See [PayMongo webhook setup and signatures](https://docs.paymongo.com/docs/developer-tools-webhook-setup-management).

---

## Step 7: Update Environment Variables

Edit the production configuration file on your Raspberry Pi:

```bash
nano /home/pi/coinnect/backend/.env
```

Set or update the following variables:

```env
ENVIRONMENT=production
HOST=127.0.0.1
ENABLE_DOCS=false
USE_MOCK_SERIAL=false
USE_MOCK_HARDWARE=false
BLOCK_DISPENSING_ON_INVENTORY_INCONSISTENCY=true
PAYMONGO_API_URL=https://api.paymongo.com
PAYMONGO_SANDBOX=false
PAYMONGO_SECRET_KEY=<live secret API key>
PAYMONGO_PUBLIC_KEY=<live public API key>
PAYMONGO_WEBHOOK_SECRET=<signing secret for the live webhook>
PAYMONGO_SOURCE_ACCOUNT_NUMBER=<provisioned PayMongo Wallet source account number>
PAYMONGO_SOURCE_ACCOUNT_NAME=<provisioned source account name>
PAYMONGO_SOURCE_ACCOUNT_BIC=<provisioned source account BIC>
```

Replace placeholders privately; never commit credentials. Remove the obsolete
`PAYMONGO_TRANSFER_CALLBACK_URL` entry: the current backend receives all three
registered events at `/api/v1/ewallet/webhook` and has no transfer-callback route.
`PAYMONGO_SANDBOX` selects the webhook signature mode; the API keys determine
whether requests move real money. Do not combine live keys with mock hardware.

Set `CORS_ORIGINS` to the exact local frontend origin. Keep the database on
persistent storage and retain its existing contents and recovery records. Review
`EWALLET_FEE_TIERS`; the current defaults charge PHP 15 through PHP 500 and PHP 25
above that. Enter measured `COIN_STORAGE_CAPACITIES` for `PHP_1`, `PHP_5`, `PHP_10`,
and `PHP_20`; empty limits keep real coin intake disabled. Configure and test the
Paperang printer if printed receipts and claim tickets are required.

Build the frontend on the Pi (these variables are embedded at build time):

```bash
cd /home/pi/coinnect/frontend
npm ci
VITE_API_BASE=http://localhost:8000/api/v1 VITE_WS_URL=ws://localhost:8000/api/v1/ws VITE_ENABLE_KEYBOARD_SIM=false npm run build
```

Serve `frontend/dist` using the kiosk's local static server. Run exactly one
backend worker. Check `systemctl cat coinnect.service`: it must bind locally and
must not trust forwarded client addresses from the public tunnel. The supplied
unit runs `python -m uvicorn app.main:app`; if configuring uvicorn yourself, use
`--host 127.0.0.1 --workers 1 --no-proxy-headers`.

Save the backend `.env` and restrict access with `chmod 600 /home/pi/coinnect/backend/.env`.

Restart the main kiosk backend to apply the environment changes:
```bash
cd /home/pi/coinnect
sudo cp systemd/coinnect.service /etc/systemd/system/coinnect.service
sudo systemctl daemon-reload
sudo systemctl restart coinnect.service
```

---

## Verification & Troubleshooting

### Verify Public Route Isolation

Replace the example hostname below. These requests do not create a payment:

```bash
curl -i https://kiosk.yourdomain.com/api/v1/status
curl -i -X POST https://kiosk.yourdomain.com/api/v1/ewallet/session
curl -i -X POST https://kiosk.yourdomain.com/api/v1/ewallet/webhook -H 'Content-Type: application/json' --data '{}'
```

Expect `404` for the first two requests and `401` for the unsigned webhook.
An unsigned `401` verifies reachability and rejection only; verify signed event
delivery separately in PayMongo. Keep host time synchronized because signatures
have a five-minute tolerance. A browser GET to the webhook should return `404`.

After sandbox and physical acceptance pass, supervise a small live cash-out and
cash-in to each enabled recipient provider. Check the wallet credit/cash delivered,
fee, database terminal state, and receipt against PayMongo's verified result.
Confirm late and duplicate events cannot dispense twice. Resolve pending payments
and claims before customer service; never repeat an uncertain transfer manually.

### Check Proxy Port Binding
Run the following to verify that Python is listening on `127.0.0.1:8020`:
```bash
sudo ss -tulpn | grep 8020
```

### View Live Callback Logs
When PayMongo fires a webhook event, check both the proxy logs and main kiosk backend logs to trace the forwarding behavior:

```bash
# Watch callback proxy traffic forwarding logs
sudo journalctl -u coinnect-proxy.service -f

# Watch main kiosk backend transaction processing logs
sudo journalctl -u coinnect.service -f
```

If the proxy returns a `502` error, verify that the main kiosk backend service (`coinnect.service`) is actually running and listening on port `8000`.
