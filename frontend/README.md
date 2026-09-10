# Frontend checks

Run `npm test -- --maxWorkers=2`, `npm run lint`, and `npm run build` from this directory.

## Cash insertion countdown

Converter, e-wallet cash-in (bills and coins), and forex insertion screens share
`DeadlineCountdown`. It renders a shrinking orange bar and seconds beneath the
cash counts. Backend snapshots supply `server_time` (UTC),
`inactivity_timeout_seconds` (the full configured window), and either
`expires_at` (converter) or `deadline` (e-wallet/forex).

Elapsed time uses a monotonic browser clock anchored to server time. New
acknowledged deadlines update the display; ordinary rerenders, rejected bills,
and switching intake medium do not reset it. Missing timing metadata displays
“Checking session…”. Expiry waits for backend transaction status and does not
trigger financial actions. Deploy the backend metadata additions with the UI.

For kiosk smoke testing, open each insertion flow and check the bar and seconds
below the amounts, accepted-cash deadline updates, Continue, sorting/rejection
overlays, and expiry. Repeat e-wallet cash-in for both GCash and Maya, switching
between bills and coins. Physical acceptance and timeout recovery require the
connected kiosk hardware.
