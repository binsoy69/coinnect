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
