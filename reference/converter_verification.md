# Converter implementation verification

Verified locally on 2026-09-05. This work corrects and completes the existing, uncommitted converter implementation. Firmware was compiled, not uploaded. Physical bench validation remains a release requirement.

## Changes

| Area | Implemented behavior | Main files |
| --- | --- | --- |
| Quotes and planning | Quote-required API starts; exact bounded payout planning; stale fee/stock revalidation; pending proposals bound to transaction and original financial terms | `backend/app/api/transaction.py`, `backend/app/services/converter_payout_planner.py`, `backend/app/services/transaction_orchestrator.py` |
| Payout and claims | Claim/confirmation concurrency guards; accepted cash minus confirmed delivery, including fee refund; no automatic payout substitution | `backend/app/services/transaction_orchestrator.py`, `backend/app/services/dispense_orchestrator.py`, `backend/app/api/admin.py` |
| Bill accounting | Persist before retention; atomic credit and inventory; retries without repeated motion; uncertain retention and authenticated, idempotent reconciliation | `backend/app/services/bill_acceptor.py`, `backend/app/services/inventory_service.py`, `backend/app/models/db_models.py`, `backend/app/api/admin.py` |
| Coin accounting | Durable session ownership before enable; cumulative counters; atomic cursor/credit/inventory; final drain reconciliation; no legacy or foreign-session credit | `backend/app/services/transaction_orchestrator.py`, `backend/app/services/event_dispatcher.py`, `backend/app/drivers/coin_security_controller.py`, `firmware/uno_coin_security/uno_coin_security.ino` |
| Tamper and recovery | Concurrent GPIO/controller stop; cancellable intake; latched motion inhibition; preserved partial-delivery ambiguity; failed recovery stays locked | `backend/app/drivers/serial_manager.py`, `backend/app/services/bill_acceptor.py`, `backend/app/services/event_dispatcher.py`, both production firmware files |
| UI and inactivity | Correct quote item fields; provider-owned absolute snapshots; ID/revision filtering; reconnect polling and session restoration; server deadlines; safe terminal routing | `frontend/src/context/TransactionContext.jsx`, `frontend/src/hooks/useBackendTransaction.js`, `frontend/src/pages/money-converter/`, `frontend/src/App.jsx` |
| Compatibility and deployment | Protocol 2 capability checks; compact Uno responses; Pi-supplied drain thresholds; original forex timeout preserved | `backend/app/services/startup_check.py`, `backend/app/core/config.py`, `backend/app/services/transaction_state_machine.py`, serial drivers and firmware |

## Verification results

- Backend unit and integration suite: **573 passed**. Command: `.venv/Scripts/python.exe -m pytest tests/unit tests/integration -q --disable-warnings --tb=short` from `backend`.
- Frontend: **12 passed across 5 test files**. Command: `npm test -- --reporter=dot` from `frontend`.
- Frontend production build: **passed** (`npm run build`). Existing bundle-size and outdated Browserslist-data warnings remain.
- ESLint for the converter provider, API hook, converter pages, and changed transaction components: **passed without errors or warnings**.
- Full-project ESLint still reports pre-existing errors in the application startup effect, virtual keyboard, bill-acceptance hook, and forex components. These are outside the converter remediation scope.
- Mega firmware: **compiled** for `arduino:avr:mega`, 24,656 bytes flash, 1,252 bytes static RAM, 6,940 bytes remaining RAM.
- Uno firmware: **compiled** for `arduino:avr:uno`, 26,552 bytes flash, 1,437 bytes static RAM, 611 bytes remaining RAM. The earlier low-memory compiler warning is resolved. This is static memory reporting, not a runtime stack measurement.
- `git diff --check`: **passed**. Git still emits repository line-ending conversion notices.

Regression cases include unrelated quote swapping, quote-only start, claim during payout, duplicate concurrent coin counts, atomic rollback when inventory credit fails, full fee refunds, repeated reconciliation, untagged serial responses with two pending commands, accounting failure after physical retention, and frontend quote schema compatibility. Existing forex, e-wallet, hardware-driver, inventory, and transaction tests are included in the backend suite.

The backend suite emits existing datetime deprecation warnings. A frontend recovery test emits an asynchronous React `act` warning; the assertions pass.

## Deployment and remaining verification

Use [the protocol and release guide](11_converter_protocol_v2.md) for API contracts, technician reconciliation, compile commands, and the physical bench checklist. Deploy backend, frontend, and both production firmware images together. The legacy Mega coin/security firmware is not the production target for this change.

Before accepting customer money, manually verify pulse-train timing and sorter routing, actual dispenser counts, tamper during every physical phase, recovery after interrupted motion, printed claims, and the complete 60+30-second inactivity flow. No physical payout, manual firmware upload, or printer test was performed in this workspace. Sudden power-loss testing is excluded as requested.
