---
status: resolved
trigger: "Coin-to-bill transaction shows that the amount does not meet the required amount when dispensing, but still attempts physical dispensing and prints a claim resolution ticket."
created: 2026-07-29
updated: 2026-07-29
---

## Symptoms

- expected: Reject the transaction before physical dispensing if the inserted amount is insufficient; otherwise dispense the selected bill amount and complete normally.
- actual: At dispense time, the UI says the amount does not meet the required amount, hardware still attempts to dispense, and a claim resolution ticket is printed.
- errors: UI amount-validation error; no backend or hardware error log supplied.
- timeline: Reproducible in the current build; first occurrence and prior working state unknown.
- reproduction: Start a coin-to-bill transaction, insert coins, proceed to the dispense stage, and observe the UI error, hardware attempt, and claim ticket.

## Current Focus

- hypothesis: The warning screen loses the backend partial-dispense state during navigation and therefore renders its unrelated generic amount-mismatch fallback.
- test: Trace state ownership across ProcessingScreen and WarningScreen, then trace backend dispense reconciliation and claim-ticket generation.
- expecting: Processing receives a partial-dispense result, but WarningScreen mounts with null hook-local backend state after the physical command has already executed.
- next_action: Share diagnosis; obtain the affected claim code or serial log to identify the exact hardware failure.
- reasoning_checkpoint:
- tdd_checkpoint:

## Evidence

- timestamp: 2026-07-29
  finding: Coin-to-bill cannot reach confirmation until backend inserted_amount is at least total_due (target_amount + fee).
  location: backend/app/services/transaction_orchestrator.py:117,308-310,322-326
- timestamp: 2026-07-29
  finding: Confirmation deliberately calculates actual_dispense from inserted_amount - fee, transitions to DISPENSING, and executes the physical plan.
  location: backend/app/services/transaction_orchestrator.py:335-363
- timestamp: 2026-07-29
  finding: A controller-reported count below the requested count is classified as partial dispense; the shortfall generates a claim code and is printed.
  location: backend/app/services/dispense_orchestrator.py:96-118,150-183; backend/app/services/transaction_orchestrator.py:377-394
- timestamp: 2026-07-29
  finding: useBackendTransaction stores backendState in hook-local useState. ProcessingScreen and WarningScreen call the hook independently, so navigation discards the response state.
  location: frontend/src/hooks/useBackendTransaction.js:15-21,119-141; frontend/src/pages/money-converter/ProcessingScreen.jsx:33-52; frontend/src/pages/money-converter/WarningScreen.jsx:11-25
- timestamp: 2026-07-29
  finding: With null backendState, WarningScreen renders "The total amount you inserted does not match the selected transaction" even when navigation was caused by a physical partial dispense.
  location: frontend/src/pages/money-converter/WarningScreen.jsx:46-47,135-156
- timestamp: 2026-07-29
  finding: Available local database files contain no coin-to-bill transaction matching the reported kiosk run, so the exact hardware error cannot be identified from retained runtime data.
  location: backend/coinnect.db; backend/coinnect_live_smoke.db

## Eliminated

- hypothesis: The insufficient-input validation runs after the physical dispense command.
  reason: Backend requires WAITING_FOR_CONFIRMATION, reached only after inserted_amount >= total_due, before confirm can execute.
- hypothesis: The claim ticket is caused directly by the UI amount warning.
  reason: The ticket is generated only from a positive physical dispense shortfall; the warning text is a frontend fallback rendered after error state is lost.

## Resolution

- root_cause: Two events are being conflated. The backend legitimately starts dispensing after input validation succeeds, then hardware reports a partial/failed bill dispense and the backend prints a claim ticket. During ProcessingScreen-to-WarningScreen navigation, the real backend error is lost because backendState is local to each useBackendTransaction hook instance. WarningScreen therefore shows its generic amount-mismatch copy, falsely describing the failure as insufficient input.
- fix: Diagnose only; no production code changed. Persist/synchronize backend transaction state across screens (or fetch by transaction ID on WarningScreen) and display the saved error/shortfall. Separately diagnose the dispenser using the affected claim code or serial log.
- verification: Static control-flow trace across frontend, backend orchestration, firmware response handling, and available runtime records.
- files_changed: .planning/debug/coin-to-bill-dispense-mismatch.md
