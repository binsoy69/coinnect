# Coinnect Backend

Python backend for the Coinnect Kiosk.

## Tech Stack

- **Python 3.11+**
- **FastAPI**: REST API for Frontend communication
- **PySerial**: Serial communication with Arduino controllers
- **Ultralytics YOLO**: Bill authentication
- **PyTest**: Testing framework

## Project Structure

- **`app/api/`**: **Web Endpoints**. Contains FastAPI routers (e.g., `/transaction`, `/status`). This is where the Frontend talks to the Backend.
- **`app/core/`**: **App Plumbing**. Configuration (env vars), logging setup, and error handling.
- **`app/drivers/`**: **Hardware Layer**. Low-level code that talks to devices (Serial protocols for Arduino, Camera drivers). This isolates the hardware details from the rest of the app.
- **`app/services/`**: Business logic including hardware transactions, PayMongo QR/disbursement integration, and exchange rates.

## PayMongo sandbox setup

Configure the PayMongo test keys, webhook secret, transfer callback URL,
Wallet source account, and `EWALLET_FEE_TIERS` in `.env`.

- Register `/api/v1/ewallet/webhook` in PayMongo for payment events.
- Set `PAYMONGO_TRANSFER_CALLBACK_URL` to the public
  `/api/v1/ewallet/transfer-callback` endpoint.

Cash-in requires PayMongo Wallet/Money Movement access. Cash-out uses QR Ph
Payment Intents. Live promotion also requires activated live capabilities, a
funded Wallet, live keys, and HTTPS production callbacks. No custom customer
mobile application is required or included.

For production Raspberry Pi Cloudflare Tunnel setup and callback-only public exposure, see the root-level [`PAYMONGO_TUNNEL_SETUP.md`](../PAYMONGO_TUNNEL_SETUP.md). For manual Windows sandbox setups and healthcheck integration testing, see [`../healthcheck/PAYMONGO_INTEGRATION.md`](../healthcheck/PAYMONGO_INTEGRATION.md).

- **`app/ml/`**: **Machine Learning**. Code related to loading and running the YOLO models for bill authentication.
- **`tests/`**: **Automated Tests**. Unit and Integration tests to ensure code quality.
