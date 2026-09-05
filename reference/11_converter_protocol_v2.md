# Money converter implementation and deployment

This contract applies to the Mega bill controller and **Uno coin/security** controller. It does not change pins, servo positions, supported input amounts, or configured service fees. Sudden power loss is outside this change's acceptance criteria. Physical bill authentication and dispensing sensors still need hardware validation.

## Customer flow

1. Fetch `GET /api/v1/transaction/options?type=bill-to-coin`. Show every supported input amount; disable infeasible amounts with the returned reason. Keep choices disabled while availability is unknown.
2. Create a proposal using `POST /api/v1/transaction/quote`, for example `{"type":"bill-to-coin","amount":100,"requested_counts":{"PHP_20":4}}`.
3. Render the returned exact items using **denom, denom_type, count, value**. Show `substitution_notice` prominently when `is_substitution` is true. Proceed means approval of these exact items.
4. Start using `POST /api/v1/transaction/` with `{"quote_id":"..."}`. Starts without an approved quote are rejected. Quotes expire after 120 seconds before acceptance. A stock or fee change returns 409 `QUOTE_CHANGED` and, when feasible, a replacement quote that must be displayed again.
5. Apply absolute transaction snapshots from HTTP and `CONVERTER_SNAPSHOT`; never increment UI credit from `BILL_STORED` or `COIN_INSERTED`. Match transaction ID and ignore older revisions. The provider retains the ID in session storage and polls every two seconds, including after reconnect.
6. Confirm using `POST /api/v1/transaction/{id}/confirm`. Revalidate the approved items immediately before dispensing. A different available breakdown returns 409 `PAYOUT_REAPPROVAL_REQUIRED`; it does not dispense automatically. Accept only this transaction's pending quote through `/approve-quote`, or request `/claim`. An unrelated quote cannot change the financial terms.
7. Only a persisted `COMPLETE` snapshot shows success. A low-level dispense event is not proof that the whole transaction completed.

Payout selection uses bounded dynamic programming. In order, it minimizes missing requested value, missing requested units, and total pieces, then prefers larger denominations. Generated items obey the same command limits as selected items: 20 bills or 50 coins per denomination. Bill-to-bill remains bills only; bill-to-coin remains coins only; coin-to-bill returns excess with coins.

## Inactivity and obligations

- Defaults: warning at 60 seconds; expiry at 90 seconds. The UI uses server timestamps, including on the summary screen. Continue explicitly calls `/activity`. Polls, rendering, reconnects, and empty bill polls do not extend deadlines.
- Bill entry and accepted money count as activity. Hardware-operation timeouts are separate and cannot be extended with `/activity`.
- No-cash expiry cancels. A cancelled transaction cannot accept more money.
- A failed or abandoned transaction owes `max(0, accepted_cash - confirmed_cash_delivered)`. This returns the fee too. A claim records an obligation; it does not dispense an immediate refund.
- Uncertain retention, coin counts, or delivery produce a provisional claim and block further converter starts until reconciliation. Retained-cash accounting retries never repeat physical motion.

## Firmware protocol 2

Both controllers must answer `CAPABILITIES` with `{"status":"OK","converter_protocol":2}`. Startup diagnostics and hardware-mode converter starts check this contract. Deploy backend, frontend, and firmware together; firmware uploads remain manual.

The Uno session commands are:

| Command | Request fields besides cmd/id | Result |
| --- | --- | --- |
| COIN_SESSION_START | sid, grace_ms, timeout_ms, quiet_ms | OK, sid, session_state |
| COIN_SESSION_STOP | sid | Inhibit intake; preserve and drain an in-flight train |
| COIN_SESSION_STATUS | denom (1, 5, 10, or 20) | OK, sid, session_state, denom, cumulative count |
| COIN_SESSION_ACK | sid | Technician acknowledgment after durable reconciliation; no cash motion |

The Raspberry Pi persists the session owner before START. IDs are monotonic unsigned 32-bit integers, never wrapped. Repeated START for the active ID preserves its counters. STOP is idempotent. Normal closure requires the minimum grace and a quiet, resolved pulse train. A drain deadline or invalid pulse train yields UNCERTAIN, never a false CLOSED. The Pi reads all four compact status responses and validates the ID and closure before final accounting. One DB commit advances the cursor, credit, and inventory together.

Environment configuration on the Pi: `COIN_SESSION_GRACE_MS=500`, `COIN_SESSION_TIMEOUT_MS=3000`, `COIN_SESSION_QUIET_MS=150`; these are sent at START. The Uno validates bounds. Its command document stays at six fields plus fixed string space to preserve SRAM.

Both controllers implement priority `EMERGENCY_STOP` and authenticated-backend recovery uses `EMERGENCY_CLEAR`. Stop preserves operation evidence, latches against new payout motion, and invalidates bill-sorter homing. The Pi cancels intake and stops GPIO and serial controllers concurrently. Serial frame writes cannot interleave; an untagged response cannot complete either waiter when a normal and a priority command are pending.

## Technician reconciliation

Use an authenticated administrator session (`Authorization: Bearer ...`). Inspect and count actual cash before submitting a resolution.

- `GET /api/v1/admin/converter-reconciliation` lists unresolved bills and coin sessions.
- `POST /api/v1/admin/converter-reconciliation/bills/{operation_id}` accepts `{"retained":true,"notes":"Physical inspection result"}`. For an UNKNOWN bill, also supply its PHP `denomination`. Use `retained:false` only when the bill was returned. Repeating the same resolution does not credit it twice.
- `POST /api/v1/admin/converter-reconciliation/coins/{sid}` accepts `{"counts":{"1":0,"5":1,"10":10,"20":0},"notes":"Physical count"}`. Counts are cumulative for that session and cannot remove already credited cash. All four are required.
- Reconcile payout operations through the existing physical-operation admin endpoint. Claim amounts are recomputed from accepted cash less confirmed delivery, including the fee.
- `POST /api/v1/admin/tamper-recovery` rejects unresolved physical, intake, and coin operations. It clears controller stop latches, homes the bill sorter, and re-arms security. Any failure leaves lockdown active. Customer controls cannot clear tamper.

## Validation and release checklist

Backend: from `backend`, run `.venv/Scripts/python.exe -m pytest tests/unit tests/integration -q` (Windows), or the equivalent virtualenv Python command on the Pi.

Frontend: from `frontend`, run `npm test`, `npm run build`, and `npm run lint`.

Firmware: Arduino AVR core, ArduinoJson **6.21.6**, AccelStepper, Servo, MFRC522, and PinChangeInterrupt. Run:

```text
arduino-cli compile --fqbn arduino:avr:mega firmware/mega_bill
arduino-cli compile --fqbn arduino:avr:uno firmware/uno_coin_security
```

Before enabling customer cash, manually verify: each denomination's pulse count; STOP halfway through a train; final counts after a lost event; repeated STOP/START; rejected malformed trains; tamper during positioning, storage, and each dispenser; no resumed motion after stop; home/re-arm failures stay blocked; partial payout plus fee refund; printed provisional and final claims; reconnect/reload on intake, summary, and reapproval; and the 60+30-second inactivity flow. Do not infer physical payout accuracy from mock tests or a successful compile.
