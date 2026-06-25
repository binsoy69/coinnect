# Coinnect Health Check

Separate maintenance diagnostics app for checking Coinnect hardware while the
main kiosk backend is stopped.

## Backend

Run from `healthcheck/backend` with the existing backend package on
`PYTHONPATH`:

```bash
cd healthcheck/backend
cp .env.example .env
pip install -r requirements.txt
python -m uvicorn healthcheck_api.main:app --reload --port 8010
```

Use real hardware by omitting the mock environment variables and ensuring the
main Coinnect backend is stopped.

If actuator checks fail with `UNKNOWN_CMD`, first check the serial status panel
or run the controller version checks. The bill port must report controller
`BILL`, and the coin/security port must report `COIN_SECURITY`. If those are
reversed, swap `SERIAL_PORT_BILL` and `SERIAL_PORT_COIN` or use stable udev
aliases such as `/dev/coinnect_bill` and `/dev/coinnect_coin`.

The coin/security diagnostics include `COIN_STATUS`, active-HIGH coin acceptor
enable checks on Mega #2 `D24`, and sorter servo movement checks on `D7` for
`CENTER=81`, `LEFT=45`, and `RIGHT=120`. Run the enable and sorter checks only
after confirming the sorter linkage and acceptor enable wiring are safe.

The Paperang P1 printer check prints a small sample receipt. Before using it on
the Raspberry Pi, install the Paperang dependencies, clone
`tinyprinter/python-paperang` into `vendor/python-paperang`, and set
`PAPERANG_MAC_ADDRESS` in `healthcheck/backend/.env` when the printer MAC is
known. The `pip install -r requirements.txt` step installs the Python Bluetooth
module needed by the vendored Paperang driver into the active virtualenv; the
healthcheck backend will still fail with `No module named 'bluetooth'` if that
command was skipped or run outside the virtualenv.

## E-Wallet Sandbox Diagnostics

The healthcheck dashboard includes a guided PayMongo sandbox panel for GCash
and Maya cash-in/cash-out integration checks. These checks use the real
PayMongo sandbox API but do not call GPIO, Arduino, inventory, bill acceptance,
or cash dispensing code.

For the complete account, API-key, public HTTPS, webhook creation, Money
Movement, verification, and troubleshooting procedure, see
[`PAYMONGO_INTEGRATION.md`](PAYMONGO_INTEGRATION.md).

Configure these values in `healthcheck/backend/.env`:

```env
PAYMONGO_SANDBOX=true
PAYMONGO_SECRET_KEY=sk_test_...
PAYMONGO_PUBLIC_KEY=pk_test_...
PAYMONGO_WEBHOOK_SECRET=...
PAYMONGO_SOURCE_ACCOUNT_NUMBER=...
PAYMONGO_SOURCE_ACCOUNT_NAME=Coinnect
PAYMONGO_SOURCE_ACCOUNT_BIC=PAEYPHM2XXX
HEALTHCHECK_PUBLIC_BASE_URL=https://public-healthcheck.example.com
HEALTHCHECK_EWALLET_DB_URL=sqlite+aiosqlite:///./healthcheck_ewallet.db
```

`HEALTHCHECK_PUBLIC_BASE_URL` must be an externally reachable HTTPS origin.
Register the payment callback shown in the dashboard as the PayMongo payment
webhook in **Test Mode**, subscribed to `payment.paid`, then copy that
endpoint's secret into `PAYMONGO_WEBHOOK_SECRET`. Cash-in batch transfers
receive the derived transfer callback URL in each request and do not require a
second dashboard webhook.

Cash-out tests complete only after a signed `payment.paid` webhook is received
and the Payment Intent is retrieved and verified. Cash-in tests complete only
after the transfer callback triggers retrieval and reconciliation of the batch
transfer. Pending sessions time out after ten minutes. Cancelling in the
healthcheck stops local tracking; it does not cancel the PayMongo resource.

Sandbox session state is stored separately from the kiosk database. The
healthcheck retains the newest 100 completed sessions and never prunes pending
sessions.

## Bill ML and Live Bill Diagnostics

The healthcheck backend uses `healthcheck/backend/.env` for model paths and
live bill-flow settings. Copy `healthcheck/backend/.env.example` to `.env`, then
set the model locations before running real ML diagnostics:

```env
CAMERA_DEVICE=0
YOLO_AUTH_MODEL_PATH=../../backend/models/auth.pt
YOLO_DENOM_MODEL_PATH=../../backend/models/denom.pt
YOLO_AUTH_MODEL_PATH_USD=../../backend/models/auth_usd.pt
YOLO_DENOM_MODEL_PATH_USD=../../backend/models/denom_usd.pt
YOLO_AUTH_MODEL_PATH_EUR=../../backend/models/auth_eur.pt
YOLO_DENOM_MODEL_PATH_EUR=../../backend/models/denom_eur.pt
YOLO_CONFIDENCE_THRESHOLD=0.7
```

Relative model paths are resolved from the directory where `uvicorn` is started.
The recommended command above starts the app from `healthcheck/backend`, so
`../../backend/models/auth.pt` points to the shared backend model directory.
Absolute paths also work.

The diagnostics UI exposes three bill ML sections:

- `Bill ML Models`: `bill_ml_models_php`, `bill_ml_models_usd`, and
  `bill_ml_models_eur` load each configured auth/denomination model pair and
  verify expected class labels. Auth models must expose `genuine` and `fake`.
  Denomination models must expose the configured currency denominations.
- `Bill Image Recognition`: `bill_image_auth_*` turns on the UV LED, captures
  one camera frame, runs the selected auth model, and turns UV off.
  `bill_image_denom_*` turns on the white LED, captures one camera frame, runs
  the selected denomination model, and turns white off. Place a bill in camera
  view before running these tests.
- `Bill Acceptor Full Flow`: `bill_acceptor_flow_php`,
  `bill_acceptor_flow_usd`, and `bill_acceptor_flow_eur` wait for the entry IR,
  run the conveyor for `BILL_PULL_DURATION`, authenticate under UV, reject fake
  bills, identify genuine bills under white light, sort, store, and increment
  inventory.

The full-flow tests move hardware and store accepted genuine bills. Confirm the
bill path, sorter, storage path, and serial controller status before running
them on a real kiosk. These timings and speeds are configurable in
`healthcheck/backend/.env`:

```env
BILL_PULL_SPEED=60
BILL_EJECT_SPEED=80
BILL_STORE_SPEED=70
LED_STABILIZATION_DELAY=0.2
BILL_ACCEPTANCE_TIMEOUT=10
BILL_PULL_DURATION=1.5
BILL_STORE_DURATION=2.0
BILL_EJECT_DURATION=1.5
STORAGE_SLOT_CAPACITY=100
```

## Frontend

```bash
cd healthcheck/frontend
cp .env.example .env
npm install
npm run dev
```

The frontend expects the diagnostics API at `http://localhost:8010/api/v1` by
default. Override with `VITE_HEALTHCHECK_API_BASE`.

For remote browser access on the same LAN, start the backend with
`--host 0.0.0.0`, set the frontend API base to the Raspberry Pi address, and
open the frontend by IP or `.local` hostname:

```bash
cd healthcheck/frontend
echo "VITE_HEALTHCHECK_API_BASE=http://192.168.1.20:8010/api/v1" > .env
npm run dev
```

Replace `192.168.1.20` with the Raspberry Pi address, then open
`http://192.168.1.20:5174`. The backend allows private LAN
origins and `.local` hostnames on the healthcheck frontend ports (`5174` for dev
and `4174` for preview). For a custom host or port, set
`HEALTHCHECK_CORS_ORIGINS` or `HEALTHCHECK_CORS_ORIGIN_REGEX` in
`healthcheck/backend/.env`.
