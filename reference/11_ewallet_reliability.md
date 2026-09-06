# E-wallet reliability and coordinated rollout

## Customer contract

The entered amount is the total paid, including the displayed fee. Cash-in credits
`total - fee` to the wallet; cash-out pays `total - fee` in cash. Both flows request
the amount and obtain an authoritative five-minute quote before continuing.
Cash-in collects recipient details after this check. Proceed rechecks the quote;
changed fees, stock, or intake options require another confirmation.

Customer cancellation stops after confirmed cash intake or verified QR payment.
The backend controls cancellation and navigation. Cash-in submits automatically
once fully funded. Change is coins only, at most PHP 20, and follows verified
wallet success. A bill requiring unsupported change is returned before storage.
Unavoidable excess above PHP 20 becomes a claim for the entire excess, without
automatic partial change. Normal cash-out and operator settlement have no PHP 20 cap.

Healthy partial cash-in sessions expire after 120 seconds without accepted cash
or an explicit Continue action. The last 30 seconds display a warning. The policy
version must have been acknowledged before intake. Expiry closes and reconciles
intake before recording `ABANDONED_RETAINED`; this is separate from fees and claims.
Disconnect, tamper, restart, hardware uncertainty, and unavailable payment service
preserve a customer obligation instead. Fully funded cash cannot be abandoned.
The UI sends presence heartbeats; these do not extend the inactivity deadline.

An unpaid QR lasts five minutes, including its final 30-second warning. Unknown
cancellation displays “Checking payment.” Closing the customer session prevents
any subsequent unattended payout: a later verified payment becomes a claim.
Cash-in's twenty-minute transfer wait starts at the first durable submission and
cannot be extended. Handoff produces a provisional claim/reference; late wallet
success updates the obligation and never dispenses change to another customer.

## Persistence and accounting

- SQLite uses WAL and FULL synchronous commits. Migration is additive and
  repeatable. Before upgrading an existing wallet schema, SQLite's backup API
  creates a timestamped `.pre-ewallet.backup` beside the database, including
  committed WAL contents. Backup failure stops migration.
- `ewallet_transactions.version` supplies optimistic concurrency checking;
  explicit state transitions and serialized orchestration reject stale mutations.
  Run exactly one backend worker because the hardware and kiosk owner are local.
- `ewallet_intakes` records bill preparation before movement. Confirmed storage,
  inventory adjustment, and cash credit commit together. `ewallet_coin_sessions`
  deduplicates cumulative controller totals before acknowledgment.
- `inventory_holds` reduces available stock without reducing physical balances.
  The durable dispense execution consumes a hold and reserves physical inventory
  in the same database transaction. Other withdrawals cannot spend held stock.
- The exact-change solver considers bounded stock, minimizes pieces, and breaks
  ties toward larger denominations. Bill intake also considers remaining storage
  slots. Coin intake is conservative: all possible coin values must have a safe
  continuation, with sufficient configured tube capacity and supported change.
- Cash payout and returned change have separate accounting fields and execution
  sources (`EWALLET` and `EWALLET_CHANGE`). A failed wallet credit owes all accepted
  cash. An incomplete cash-out owes total paid minus confirmed cash delivered,
  including the fee. Successful wallet credit earns the fee; unpaid excess alone
  remains due if change fails.
- Legacy transactions never acquire an abandonment acknowledgment. Legacy failed
  or cancelled cash-in records containing stored cash are routed to reconciliation.
  Historical totals and resolved claims are preserved.

Payment creation checkpoints and stable idempotency keys are persisted before
external work. Timeouts remain unknown outcomes. Scheduled reconciliation runs
independently of signed callbacks, and inbox workers reclaim expired leases.
Transfer verification checks amount, currency, reference, identifiers, recipient
number and provider; QR verification checks the Payment Intent and paid QR Ph source.
After 23 hours, unknown transfer submissions use reference lookup rather than
another POST, avoiding the provider's approximate 24-hour idempotency retention
boundary. See [PayMongo money movement guidance](https://docs.paymongo.com/docs/money-movement-best-practices).

## Local deployment and firmware

1. Close customer service and reconcile existing controller journals before
   upgrading. Keep an independent backup of the database and deployed release.
2. Build and manually install the matching coin/security firmware on **Mega or
   Uno**. Pin assignments remain unchanged. The new intake journal reserves the
   last 128 EEPROM bytes; do not upgrade over unresolved old journal entries.
3. Deploy backend and frontend together. Use one backend process bound to
   `127.0.0.1`. Serve the UI on the same Raspberry Pi and configure its exact origin
   in `CORS_ORIGINS`. Set frontend API/WebSocket URLs to the local service.
4. Set real payment credentials, signature secret, funding account, fee tiers,
   and calibrated `COIN_STORAGE_CAPACITIES` for `PHP_1`, `PHP_5`, `PHP_10`, `PHP_20`.
   Empty capacities disable production coin intake. Do not guess tube limits.
   Disable keyboard simulation in the production frontend build.
5. A reverse proxy/tunnel may expose **only** `/api/v1/ewallet/webhook`; do not
   publish the customer API, admin routes, or WebSocket endpoint. Disable broad
   forwarded-client trust. Remote customer requests and untrusted origins are
   rejected independently of webhook signature verification.
6. Startup reconciles physical operations before payment work. Money operations
   remain blocked on inconsistent inventory, incomplete diagnostics, missing
   hardware, or unsupported coin firmware. Inspect and resolve recovery records
   before returning the kiosk to service.

Managed coin commands: `COIN_CAPABILITIES`, `COIN_SESSION_START`,
`COIN_SESSION_STOP`, `COIN_SESSION_STATUS`, `COIN_SESSION_ACK`, and the
operator-only `COIN_SESSION_RECONCILE` recovery command. Session IDs are shared
with the converter service. Bounded sessions close after one identified coin,
preserve pulse trains already started, and wait for the sorter to settle.
Alternating EEPROM records preserve session identity/counts. Interrupted intake
boots as uncertain; reset or raw enable cannot silently discard that state.

## API and operator recovery

Bootstrap `POST /api/v1/ewallet/session`; subsequent wallet requests send the
opaque token in `X-Kiosk-Session`. Quotes use `POST /ewallet/quotes`; transaction
creation requires its quote ID and a stable customer request key. `GET /ewallet/resume`
restores the latest session transaction. Heartbeat and Continue are distinct POST
operations beneath `/ewallet/transactions/{id}`. The browser stores only opaque
session/transaction references. Wallet WebSocket events require `AUTH_EWALLET`
with a valid session token and are filtered to that session.

The admin claims page merges legacy and unified obligations, shows retained cash
separately, and provides physical-intake/dispense inspection forms. A provisional
claim cannot be settled normally. Confirm physical counts and notes, reconcile
gateway status, and then settle a verified outstanding obligation. A gateway
transfer whose identifiers were never recovered may require inspection by its
transaction reference in PayMongo. Do not create a replacement transfer.
After physical reconciliation, verify and record actual inventory before clearing
the kiosk's inventory inconsistency. Printer failure does not erase a claim;
the UI and database retain its reference. Provisional tickets say awaiting verification.

## Validation

From `backend`: `python -B -m pytest -p no:cacheprovider -q`.
From `frontend`: `npm test`, `npm run lint`, `npm run build`.
Firmware: `arduino-cli compile --fqbn arduino:avr:uno firmware/uno_coin_security`
and `arduino-cli compile --fqbn arduino:avr:mega firmware/mega_coin_security`.

Regression coverage includes cash conservation, duplicate/concurrent credits,
PHP 1/19/20 change and oversized rejection, exact-stock planning, durable holds,
manual intake reconciliation, abandonment versus faults, session isolation,
inbox leases, lost transfer responses, immutable terminal states, migration backup,
and customer screens that cannot report cancellation or claims as success.

Validation on 2026-09-06: the full backend suite passed 603 tests. The final
request-identity and fee-accounting adjustments passed a further 55 focused
wallet, claims, and dispense tests, including the added recipient-retry regression.
All 18 frontend tests passed; changed-file ESLint and the frontend production
build passed. Mega and Uno coin/security builds passed. Full-project ESLint still
reports seven existing errors and three warnings in unchanged App, virtual
keyboard, and forex files. Vite reports its existing bundle-size warning.

Before production acceptance, run sandbox payment and real-hardware scenarios:
oversized bills, simultaneous bill/coin attempts, extra coins after gate closure,
pulse draining, serial disconnect, jam, tamper, partial dispense, and power loss
at each durable/physical boundary. Verify that late payment results never cause
unattended output. Check Uno memory headroom under sustained serial traffic and
EEPROM endurance against expected transaction volume. Compilation and mock tests
do not establish these physical guarantees.
