# Coinnect Health Check

Separate maintenance diagnostics app for checking Coinnect hardware while the
main kiosk backend is stopped.

## Backend

Run from `healthcheck/backend` with the existing backend package on
`PYTHONPATH`:

```bash
cd healthcheck/backend
PYTHONPATH=../../backend HEALTHCHECK_PIN=123456 USE_MOCK_SERIAL=true USE_MOCK_HARDWARE=true uvicorn healthcheck_api.main:app --reload --port 8010
```

Use real hardware by omitting the mock environment variables and ensuring the
main Coinnect backend is stopped.

## Frontend

```bash
cd healthcheck/frontend
npm install
npm run dev
```

The frontend expects the diagnostics API at `http://localhost:8010/api/v1` by
default. Override with `VITE_HEALTHCHECK_API_BASE`.
