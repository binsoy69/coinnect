# PayMongo Cloudflare Tunnel Setup Guide (Raspberry Pi)

This guide describes how to configure and deploy a secure, persistent Cloudflare Named Tunnel on the Raspberry Pi to receive PayMongo e-wallet webhook callbacks in production.

---

## Architecture Overview

For security reasons, **do not point a public Cloudflare tunnel directly at the main kiosk API (port `8000`)**. The main kiosk API contains unauthenticated hardware control endpoints (bill dispensers, coin sorters, security overrides). 

Instead, we use a callback-only proxy script ([paymongo_callback_proxy.py](file:///d:/projects/coinnect/scripts/paymongo_callback_proxy.py)) running on port `8020` that selectively validates and forwards only POST requests destined for the `/api/v1/ewallet/webhook` route.

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

1. Your Raspberry Pi must be fully set up and configured using the [setup_rpi.sh](file:///d:/projects/coinnect/scripts/setup_rpi.sh) script.
2. The main kiosk service (`coinnect.service`) should be configured, though it does not need to be running yet.
3. You must have a custom domain managed under your Cloudflare account (e.g., `yourdomain.com`).

---

## Step 1: Install Cloudflare Tunnel Daemon on Raspberry Pi

SSH into your Raspberry Pi and add the official Cloudflare package repository:

```bash
# 1. Add Cloudflare package repository
curl -L https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflare-main.gpg $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare.list

# 2. Update package lists and install cloudflared
sudo apt update && sudo apt install -y cloudflared
```

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
6. Click **Register**. PayMongo will generate a **Webhook Secret** (starts with `whsec_...`).

---

## Step 7: Update Environment Variables

Edit the production configuration file on your Raspberry Pi:

```bash
nano /home/pi/coinnect/backend/.env
```

Set or update the following variables:

```env
# PayMongo Webhook Configuration
PAYMONGO_WEBHOOK_SECRET=whsec_your_actual_live_secret
PAYMONGO_TRANSFER_CALLBACK_URL=https://kiosk.yourdomain.com/api/v1/ewallet/transfer-callback
```

Save the file and exit (`Ctrl+X`, then `Y`, then `Enter`).

Restart the main kiosk backend to apply the environment changes:
```bash
sudo systemctl restart coinnect.service
```

---

## Verification & Troubleshooting

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
