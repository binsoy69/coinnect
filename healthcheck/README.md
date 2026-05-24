# Coinnect Health Check

Separate maintenance diagnostics app for checking Coinnect hardware while the
main kiosk backend is stopped.

## Backend

Run from `healthcheck/backend` with the existing backend package on
`PYTHONPATH`:

```bash
cd healthcheck/backend
cp .env.example .env
python -m uvicorn healthcheck_api.main:app --reload --port 8010
```

Use real hardware by omitting the mock environment variables and ensuring the
main Coinnect backend is stopped.

The coin/security diagnostics include `COIN_STATUS`, active-HIGH coin acceptor
enable checks on Mega #2 `D24`, and sorter servo movement checks on `D7` for
`CENTER=81`, `LEFT=45`, and `RIGHT=120`. Run the enable and sorter checks only
after confirming the sorter linkage and acceptor enable wiring are safe.

The Paperang P1 printer check prints a small sample receipt. Before using it on
the Raspberry Pi, install the Paperang dependencies, clone
`tinyprinter/python-paperang` into `vendor/python-paperang`, and set
`PAPERANG_MAC_ADDRESS` in `healthcheck/backend/.env` when the printer MAC is
known.

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
