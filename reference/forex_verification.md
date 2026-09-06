# Forex correctness and recovery

## Deployment

Deploy frontend and backend together with customer transactions stopped. SQLite startup creates additive `forex_*` tables and takes a WAL-aware `.pre-forex.backup` first. Existing records and settled history are preserved. Version 1 sessions retain the quote, revision, deadline, currency legs, and idempotency key. Each leg owns a durable `InventoryHold`.

Production forex defaults to disabled. Set `FOREX_ENABLED=true` only after the hardware checklist below is completed. Test/development environments permit mock verification. No firmware update is required by this change.

Admin Claims exposes a legacy forex audit with raw evidence and proposed review actions. It does not guess corrected balances. Legacy scalar settlement is rejected; old nonterminal records block new forex pending separately reviewed accounting correction. The migration never rewrites settled history.

## Policies and interfaces

- Supported selections: USD 10/50 and EUR 5/10, against PHP in either direction.
- Backend quotes expire after 60 seconds before start. `POST /forex/transaction` requires `{quote_id, idempotency_key}` from a reviewed `GET /forex/quote/{service}?amount=...`. The old amount-start contract is intentionally rejected. Successful starts lock the stored quote despite subsequent rate/fee changes.
- Principal and PHP fee use Decimal ROUND_HALF_UP separately. Fees are finite, 0 <= fee < 100, with at most two decimal places. Database fees override environment defaults after initialization.
- Rates refresh hourly with a 24-hour TTL. Incomplete/invalid responses preserve the last good complete cache. New starts require connectivity and valid rates.
- Output stock is held at start. Exact PHP change is held before retaining an overpaying bill; unavailable change rejects that bill without credit.
- A prepared intake precedes storage. Storage inventory and customer credit commit atomically. Uncertain retention creates a provisional input claim and blocks further forex intake.
- `FOREX_EXCHANGE` and `FOREX_CHANGE` are separate payout executions. Exchange is first; failed exchange stops payout. Reservations are consumed once.
- Incomplete exchange owes remaining destination output, unpaid PHP change, and the full PHP fee refund. Change-only failure owes PHP change alone. Pre-payout failure/timeout refunds retained input in its input currency.
- One ticket contains independently settled currency items. Ambiguous outcomes and dependent fee refunds remain provisional until physical reconciliation. Resolution records operator and notes.
- Server inactivity is 180 seconds; warning at 150. Only successful cash acceptance or explicit Continue resets the persisted deadline. Polls and rejected bills do not extend it. Continue and Confirm recheck expiry under the session lock, even before the watchdog runs. Cancellation is disabled after accepted cash.
- Recovery reconciles journals but never automatically restarts motion. Repeated recovery must not duplicate credit, stock restoration, claims, or payouts. Recovery also releases unused holds left behind after a terminal-state commit. Printer failures do not undo settlement or retain machine ownership.

Snapshots include `revision`, `quote`, UTC `deadline`, `payout_legs`, and `claim.items`. Legacy `dispensed_amount` for version 1 means exchange output only. Never add different currencies. `POST /forex/transaction/{id}/continue` extends eligible waiting states. `/forex/rates` includes availability, validity, enablement, and fetched time.

Admin endpoints: `/admin/forex-audit`, `/admin/forex-intakes`, intake reconciliation, and `/admin/forex-claims/{ticket}/items/{item}/resolve`. Existing physical-operation reconciliation recomputes the whole forex ticket across both legs.

## Audit coverage

| Issue | Regression or acceptance coverage |
|---|---|
| 1 Mixed currency totals | `test_php_change_claim_is_php_and_no_fee_refund`, four-flow tests |
| 2 Wrong restart claim/completed-payout gap | Completed hardware/unfinalized source and terminal hold-cleanup recovery tests |
| 3 Waiting states omitted | Parameterized restart/refund tests |
| 4 Retention accounting gap | Provisional intake reconciliation and browser cancellation tests |
| 5 Fault after cash | Intake fault preserves earlier accepted cash test |
| 6 Concurrent quote corruption | Concurrent start/idempotency test |
| 7 Leaked ownership | Startup and printer failure tests |
| 8 Inconsistent quotes | Decimal/fee tests and authoritative frontend snapshot tests |
| 9 Inventory options | Backend exact-stock availability and hardware checklist |
| 10 Refresh drops ID | Frontend refresh/reference test |
| 11 Missing/duplicate events | Stale-snapshot, duplicate-event, claim-event tests |
| 12 Late change check | Change rejected before retention test |
| 13 Timeouts | Poll/Continue/deadline tests and parameterized recovery states |
| 14 Tamper | Tamper claim test and physical acceptance |
| 15 Reload recovery | Reload and lost-start-response frontend tests |
| 16 Invalid amounts | Parameterized rejection tests |
| 17 Invalid/nonpersistent fees | Fee validation, locked quote, and service restart tests |
| 18 Receipt currencies | Receipt tests and physical print checklist |
| 19 Cache availability | Complete-cache, malformed refresh, enablement tests |
| 20 Labels | Backend quote presentation and visual acceptance below |
| 21 Keyboard simulation | Development flag and active backend reference required; no local credit method |
| 22 Lint | Full frontend ESLint run |

## Commands

Backend: `.\.venv\Scripts\python.exe -m pytest -q --disable-warnings --tb=short --show-capture=no`

Frontend: `npm test -- --maxWorkers=2`, `npm run lint`, `npm run build`.

Tests use isolated databases and simulated controllers, never installed kiosk balances.

## Hardware acceptance: pending

Record date, operator, and outcome for every check before enabling production forex:

- [ ] USD 10/50 and EUR 5/10 authentication, storage routing, and dispense mapping.
- [ ] All four directions: quote, fee, actual payout, and receipt agree; PHP change is separate.
- [ ] Overpayment without exact change ejects without customer/inventory credit.
- [ ] Tamper during intake/payout stops motion and preserves obligations.
- [ ] Controlled power interruptions around retention and every payout boundary; no repeated motion after boot.
- [ ] Browser reload/disconnect restores the same transaction and accepted amount.
- [ ] Warning at 150s, Continue, timeout at 180s, cancellation disabled after cash.
- [ ] Partial exchange and change-only failures create correct itemized claims and fee treatment.
- [ ] Paperang receipt/ticket currency, amounts, reference, provisional status, and bitmap readability.
- [ ] Admin physical inspection clears ambiguity and each claim item settles independently.

Physical hardware and live-printer acceptance have not been performed by automated tests.
