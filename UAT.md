# Coinnect Manual User Acceptance Testing (UAT)

> **Purpose:** production acceptance of the normal customer journey using the
> installed kiosk hardware and authorised live payment accounts. This guide is
> not a substitute for the automated test suite, safety checks, or the deferred
> resilience tests at the end of this document.

## 1. Rules, roles, and evidence

### 1.1 Live-money safety rules

- Obtain written approval from the service owner before the run. Record the
  approved maximum total exposure and stop when it is reached.
- Use only nominated, verified GCash/Maya test accounts and a dedicated QR Ph
  payer. Do not record wallet PINs, OTPs, complete account numbers, or QR images
  in this file or a defect report.
- Use the smallest viable amount for each case. Use a larger value only where
  needed to exercise a denomination, configured fee, or payout combination.
- Two people are required: the **operator** drives the kiosk and counts cash;
  the **witness** independently records evidence and confirms every cash/wallet
  movement. The administrator performs inventory and claim review.
- Stop testing immediately for an unexpected retained bill/coin, incorrect
  payout, open claim, active tamper/lockdown, or unexplained inventory difference.
  Preserve the transaction ID and escalate; do not start another customer flow.

### 1.2 Required evidence for every test

Record the following in the execution log before marking a test PASS:

| Field | Required record |
| --- | --- |
| Test ID and outcome | PASS, FAIL, BLOCKED, or NOT RUN |
| People and time | Operator, witness, administrator, date/time, software/firmware version |
| Transaction | Kiosk transaction ID, service/flow, quoted amount, displayed fee, net amount |
| Cash | Input denominations/counts; independent output denominations/counts; before/after inventory totals |
| Online payment | Provider, masked test account, PayMongo/payment reference, wallet proof of debit or credit |
| Customer artifacts | Receipt retained/photographed, visible result screen, and any claim reference |
| Reconciliation | Admin-record result, claim status, discrepancy (must be PHP 0 / none), witness sign-off |

**Pass condition:** the intended normal flow reaches `COMPLETE`/success, the
customer receives or is credited exactly the locked/displayed net amount, the
receipt is readable and agrees with the transaction, and physical inventory,
wallet evidence, and durable transaction/admin records agree. A printed receipt
failure, a warning/claim screen, or any non-zero unexplained difference is a FAIL.

### 1.3 Required preflight (once per UAT run)

1. Record kiosk hostname, application release/commit, backend/frontend version,
   bill-controller firmware version, coin/security-controller firmware version,
   and current fee configuration.
2. Confirm the kiosk is in customer mode, no security lockdown/tamper condition
   is active, both controllers are connected/homed, bill acceptor/camera/lighting
   are ready, and Paperang has paper, battery, Bluetooth connection, and a legible
   self-test print.
3. Count and record all usable starting stock: PHP bills `20/50/100/200/500/1000`,
   coins `1/5/10/20`, USD bills `10/50`, and EUR bills `5/10`. Confirm the admin
   inventory matches the witnessed physical count before enabling transactions.
4. Confirm live network connectivity, current valid forex rates, enabled forex
   services, PayMongo production credentials/webhook health, and the nominated
   wallet/QR Ph accounts' starting balances.
5. Check admin claims and reconciliation queues. They must be empty, with no
   unresolved physical operation or pending claim from an earlier run.
6. Prepare clean, authentic test notes/coins. The witness selects the next input
   and expected output independently from the operator.

## 2. Coverage and denomination matrix

Run every row below. A row may be repeated to complete the denomination matrix;
do not use a disabled or infeasible payout option merely to satisfy coverage.

| ID | Customer transaction | Minimum normal-flow acceptance |
| --- | --- | --- |
| MC-01 | Bill to bill | PHP bill accepted, stored, and exchanged for the approved bill-only payout |
| MC-02 | Bill to coin | PHP bill accepted, stored, and exchanged for the approved coin-only payout |
| MC-03 | Coin to bill | PHP coins accepted, final count closes, and approved bills plus any quoted coin excess are delivered |
| EW-01 | GCash cash-in | Cash is retained, verified GCash recipient receives the displayed net credit |
| EW-02 | GCash cash-out | QR Ph payment is verified and the displayed net cash is dispensed |
| EW-03 | Maya cash-in | Cash is retained, verified Maya recipient receives the displayed net credit |
| EW-04 | Maya cash-out | QR Ph payment is verified and the displayed net cash is dispensed |
| FX-01 | USD to PHP | USD 10/50 is authenticated/stored; PHP output and any PHP change match locked quote |
| FX-02 | PHP to USD | PHP is authenticated/stored; USD 10/50 output and any PHP change match locked quote |
| FX-03 | EUR to PHP | EUR 5/10 is authenticated/stored; PHP output and any PHP change match locked quote |
| FX-04 | PHP to EUR | PHP is authenticated/stored; EUR 5/10 output and any PHP change match locked quote |

### Denomination completion record

Mark a denomination only when it was physically accepted or dispensed correctly
in a passing row. Use the Test ID and transaction ID as evidence.

| Currency | Denomination | Accepted: test / transaction | Dispensed: test / transaction |
| --- | ---: | --- | --- |
| PHP bill | 20 |  |  |
| PHP bill | 50 |  |  |
| PHP bill | 100 |  |  |
| PHP bill | 200 |  |  |
| PHP bill | 500 |  |  |
| PHP bill | 1000 |  |  |
| PHP coin | 1 |  |  |
| PHP coin | 5 |  |  |
| PHP coin | 10 |  |  |
| PHP coin | 20 |  |  |
| USD bill | 10 |  |  |
| USD bill | 50 |  |  |
| EUR bill | 5 |  |  |
| EUR bill | 10 |  |  |

## 3. Reusable normal-flow checklist

Use this checklist for each test row, plus the flow-specific steps in section 4.

1. Start from the idle home screen. Confirm the correct service tile is enabled
   and the other customer session is not resumable.
2. Select the service and review every displayed instruction, currency, amount,
   fee, net customer amount, exchange rate (forex), and disclosure. Confirm the
   selected service matches the test ID before proceeding.
3. The witness records the quote/confirmation screen and independently calculates
   the expected net output or wallet credit from the displayed terms. For forex,
   record the locked rate, fee percentage/amount, source amount, destination
   amount, quote ID, and quote expiry.
4. Insert or pay only the recorded test amount. Observe physical routing/storage
   during cash intake; do not open the machine or interfere with the mechanism.
5. During output, independently count each note/coin as it leaves the kiosk.
   Verify the supplied denominations are permitted by the approved payout plan.
6. Wait for the terminal customer screen. It must state success, not an error,
   warning, pending payment, cancellation, or claim. Record transaction ID.
7. Collect the receipt. Verify its identifier, service, currencies, gross amount,
   fee, net amount, rate where applicable, date/time, and completion wording;
   retain it in the evidence packet.
8. In the administrator interface, find the transaction and verify its final
   state, amount fields, inventory deltas, payment reference where applicable,
   and no claim/physical reconciliation entry. Repeat the physical count for all
   affected storage/dispensers and record the before/after difference.

## 4. Flow-specific test procedures

### 4.1 How to prepare an exact test case

Each numbered row below has an action and a separate observable expected result.
Execute rows in order; record the failing step number if any expectation is not met.
These are physical, normal-flow acceptance tests, not keyboard-simulation tests.

Before funding a transaction, fill in this case worksheet. Amounts depend on the
installed fee configuration, live quote, and stock; do not copy mock rates or assume
a fixed fee. Start with PHP 100 for converter/e-wallet cases if available; otherwise
record the smallest enabled, feasible amount within the approved exposure.
For forex use the specific foreign denomination in the relevant procedure.

| Case input / expected value | Record before cash/payment commitment |
| --- | --- |
| Test ID and variant | Include provider, direction, and intake medium |
| Selected amount | Exact value and currency; for e-wallet this is the total paid, not net credit |
| Quote | ID, expiry, locked rate and rate direction when applicable |
| Expected total due / fee / net payout | Exact numeric amounts, each with currency |
| Physical input plan | Each denomination and count, in insertion order |
| Expected physical output plan | Each denomination/count from the approved quote; list change separately |
| Recipient / payer | Approved masked account and starting balance |
| Starting inventory | Physical and admin counts for every affected denomination |

If the quote cannot be funded with the prepared notes/coins, revise the worksheet
before starting intake. Mark BLOCKED if no feasible approved case exists.
Do not guess unavailable values or mark an unexecuted step PASS.
Record quote IDs and durable states from backend/admin evidence if the customer
screen does not expose them. If the required evidence is unavailable, record the
verification as BLOCKED; do not assume an admin screen exists for every field.

### 4.2 Shared completion checks (required for every flow)

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| C1 | Before leaving the terminal screen, record the transaction reference, result wording, amounts and any message. | Durable state is COMPLETE; no pending, warning, assistance, claim, or print-failure message. |
| C2 | Collect the Paperang receipt and compare its service, reference, date/time, gross, fee, net and applicable currency/rate fields with the worksheet and durable record. | One readable completion receipt agrees with the completed transaction. Missing/failed printing fails receipt acceptance even if money movement succeeded. |
| C3 | Administrator retrieves the transaction, payment evidence where applicable, claims and reconciliation records. | Exactly one completed transaction; correct payment reference where applicable; no unresolved claim or physical obligation. |
| C4 | With customer intake stopped and authorised maintenance access, operator and witness recount affected storage and dispensers; compare denomination by denomination. | Ending physical stock = starting stock + accepted units - dispensed units. Admin stock agrees; unexplained difference is zero for each currency. |
| C5 | Use the terminal screen's home/finish action; for e-wallet tap **Finish**. Start a new transaction only after reconciliation. | Idle home screen returns. Previous amount, recipient and transaction are not reused in a new session. |

### MC-01 — Bill to Bill

**Setup:** Record a feasible PHP amount, configured fee, exact input mix and approved bill payout. Prepare PHP notes totalling the quote's total due.

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| 1 | From idle, tap **Start Transaction → Money Converter → Bill to Bill**. | The reminder for Bill to Bill appears; the selected service is correct. |
| 2 | Read the reminder and tap **Proceed**. | Amount options load; unavailable options remain disabled with a reason. |
| 3 | Tap the worksheet's enabled amount, then **Proceed**. | **Select Dispense Breakdown** opens with target amount and fee. |
| 4 | Use **+ / -** beside the permitted denominations to enter the worksheet counts, then tap **Proceed**. | Allocated values update correctly; confirmation shows the authoritative bill-only payout. Record the actual approved plan and any substitution notice. |
| 5 | At confirmation, compare total due, fee, payout and denomination counts against the worksheet; tap **Proceed** once. | A transaction starts and the bill insertion screen opens. No payout occurs yet. |
| 6 | Insert each prepared PHP note in the illustrated orientation. Wait for authentication/sorting and the counter update before the next note. | Each authentic note is accepted once and stored in its PHP denomination slot; counters and running total match the inserted notes. |
| 7 | Wait for intake completion and automatic navigation to the transaction summary. Do not add cash after the required total is reached. | Summary appears when the backend allows confirmation; accepted amount and approved payout agree with the quote. |
| 8 | Compare summary with the worksheet, then tap **Proceed** once. | Processing starts and the authorised payout is dispensed. |
| 9 | Count every dispensed bill with the witness. | Only the approved bills are delivered; count × denomination totals equal the quoted payout. Exact-funded input minus payout equals the fee. |
| 10 | Wait for success and perform C1–C5. | Success, receipt and inventory all agree. Bill storage increases by the accepted notes; bill dispensers decrease by the payout counts. |

### MC-02 — Bill to Coin

**Setup:** Record a feasible PHP amount, configured fee, exact input mix and approved coin payout. Prepare PHP notes totalling the quote's total due.

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| 1 | From idle, tap **Start Transaction → Money Converter → Bill to Coin**. | The reminder for Bill to Coin appears; the selected service is correct. |
| 2 | Read the reminder and tap **Proceed**. | Amount options load; unavailable options remain disabled with a reason. |
| 3 | Tap the worksheet's enabled amount, then **Proceed**. | **Select Dispense Breakdown** opens with target amount and fee. |
| 4 | Use **+ / -** beside the permitted denominations to enter the worksheet counts, then tap **Proceed**. | Allocated values update correctly; confirmation shows the authoritative coin-only payout. Record the actual approved plan and any substitution notice. |
| 5 | At confirmation, compare total due, fee, payout and denomination counts against the worksheet; tap **Proceed** once. | A transaction starts and the bill insertion screen opens. No payout occurs yet. |
| 6 | Insert each prepared PHP note in the illustrated orientation. Wait for authentication/sorting and the counter update before the next note. | Each authentic note is accepted once and stored in its PHP denomination slot; counters and running total match the inserted notes. |
| 7 | Wait for intake completion and automatic navigation to the transaction summary. Do not add cash after the required total is reached. | Summary appears when the backend allows confirmation; accepted amount and approved payout agree with the quote. |
| 8 | Compare summary with the worksheet, then tap **Proceed** once. | Processing starts and the authorised payout is dispensed. |
| 9 | Count every dispensed coin with the witness. | Only the approved coins are delivered; count × denomination totals equal the quoted payout. Exact-funded input minus payout equals the fee. |
| 10 | Wait for success and perform C1–C5. | Success, receipt and inventory all agree. Bill storage increases by the accepted notes; coin tubes decrease by the payout counts. |

### MC-03 — Coin to Bill

**Setup:** Record a feasible PHP amount, configured fee, exact input mix and approved bill payout. Prepare PHP 1/5/10/20 coins totalling the quote's total due; select the bill amount requested by the screen.

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| 1 | From idle, tap **Start Transaction → Money Converter → Coin to Bill**. | The reminder for Coin to Bill appears; the selected service is correct. |
| 2 | Read the reminder and tap **Proceed**. | Amount options load; unavailable options remain disabled with a reason. |
| 3 | Tap the worksheet's enabled amount, then **Proceed**. | Confirmation opens directly with the generated bill payout quote; there is no dispense-breakdown screen. |
| 4 | At confirmation, compare total due, fee, payout and denomination counts against the worksheet; tap **Proceed** once. | A transaction starts and the coin insertion screen opens. No payout occurs yet. |
| 5 | Insert the prepared coins one at a time, waiting for each count update. Stop at the recorded total due. | Each accepted coin increments its count and total exactly once. Final accepted value equals the input plan. |
| 6 | Wait for intake completion and automatic navigation to the transaction summary. Do not add cash after the required total is reached. | Coin intake closes and its final count is reconciled before confirmation becomes available. Summary shows bill payout and any quoted coin excess separately. |
| 7 | Compare summary with the worksheet, then tap **Proceed** once. | Processing starts and the authorised payout is dispensed. |
| 8 | Count every dispensed bill and any separate coin excess with the witness. | Bills match the approved plan; any coin excess matches its separate recorded amount. Accepted PHP minus all returned PHP equals the recorded fee. |
| 9 | Wait for success and perform C1–C5. | Success, receipt and inventory all agree. Coin stock increases by accepted coins and decreases by any excess returned; bill stock decreases by payout. |

### EW-01 — GCash cash-in

**Setup:** Use the nominated GCash recipient and record the starting wallet balance. Record gross total G, fee F and net N = G - F from the quote. Prepare exact-funded PHP cash totalling G for the base run.

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| 1 | Tap **Start Transaction → E-Wallet → GCash → Cash In**. | The GCash cash-in reminder appears. |
| 2 | Read the reminder; tap **Proceed**. Review the fee table, then tap **Proceed**. | The fee table loads for the selected provider/direction, followed by **Enter Amount**. |
| 3 | Enter G on the keypad and tap **Check availability**. | An available quote is created and the account-name screen opens. |
| 4 | Enter the approved GCash account name and tap **Proceed**; enter its mobile number and tap **Proceed**. | Confirmation shows the entered recipient and the correct gross, fee and net credit. Witness checks details against the nominated account. |
| 5 | Read the cash-in/change/inactivity disclosure and tick **I understand and accept these cash-in rules.** Tap **Proceed** once. | The backend transaction starts and **Insert bills** opens. The recorded recipient and quote are retained. |
| 6 | Insert the prepared notes one at a time; wait for sorting and the counter update after each note. | Accepted value increases once per note; fee and wallet credit remain consistent with the quote. |
| 7 | For the coin-intake variant, prepare part of G as coins before starting; on intake tap **Insert coins instead** when enabled and insert those coins one at a time. Run this variant as a separate transaction for this provider. | **Insert coins** opens, coin intake is enabled and each accepted coin updates the same transaction total once. If unavailable, mark this variant BLOCKED before funding. |
| 8 | At accepted total G, stop inserting and wait; no final submit button is needed. | Processing starts automatically. The kiosk waits for verified transfer completion; pending transfer alone is not success. |
| 9 | Check the nominated GCash wallet transaction history and balance; capture masked credit evidence. | Exactly one credit of N appears; balance increases by N in the absence of other account activity. No cash payout/change is due in this exact-funded run. |
| 10 | Record the completed screen and execute C1–C5. | **Transaction complete** appears. Wallet credited equals N, accepted cash equals G, fee equals F, change is zero, and physical inventory increases by the accepted denominations. |

### EW-02 — GCash cash-out

**Setup:** Use the nominated QR Ph payer and record the starting wallet balance. Record gross total G, fee F and net N = G - F from the quote. Ensure stocked payout denominations can deliver N.

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| 1 | Tap **Start Transaction → E-Wallet → GCash → Cash Out**. | The GCash cash-out reminder appears. |
| 2 | Read the reminder; tap **Proceed**. Review the fee table, then tap **Proceed**. | The fee table loads for the selected provider/direction, followed by **Enter Amount**. |
| 3 | Enter G on the keypad and tap **Check availability**. | An available quote is created and confirmation opens directly; no recipient-name/mobile entry is required. |
| 4 | Compare confirmation total G, fee F and cash received N with the worksheet; tap **Proceed** once. | A dynamic QR Ph payment screen opens with transaction/payment reference. No cash has dispensed. |
| 5 | On the nominated payer's wallet/bank app, scan the displayed QR. Compare payment amount with G and authorise exactly one payment. | The payer records one debit of G and a payment reference. Scanning without successful payment is insufficient. |
| 6 | Wait for the kiosk to verify payment; do not pay again while waiting. | Only verified payment triggers cash dispensing; pending status is not presented as completion. |
| 7 | Collect and count all dispensed PHP notes/coins; compare denomination counts with the recorded payout plan. | Physical payout totals N = G - F; the customer is not asked to insert cash. |
| 8 | Record payer proof, kiosk reference and completed screen; execute C1–C5. | **Transaction complete** appears; durable cash dispensed equals N, wallet debit equals G, fee equals F, and inventory decreases by actual payout counts. |

### EW-03 — Maya cash-in

**Setup:** Use the nominated Maya recipient and record the starting wallet balance. Record gross total G, fee F and net N = G - F from the quote. Prepare exact-funded PHP cash totalling G for the base run.

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| 1 | Tap **Start Transaction → E-Wallet → Maya → Cash In**. | The Maya cash-in reminder appears. |
| 2 | Read the reminder; tap **Proceed**. Review the fee table, then tap **Proceed**. | The fee table loads for the selected provider/direction, followed by **Enter Amount**. |
| 3 | Enter G on the keypad and tap **Check availability**. | An available quote is created and the account-name screen opens. |
| 4 | Enter the approved Maya account name and tap **Proceed**; enter its mobile number and tap **Proceed**. | Confirmation shows the entered recipient and the correct gross, fee and net credit. Witness checks details against the nominated account. |
| 5 | Read the cash-in/change/inactivity disclosure and tick **I understand and accept these cash-in rules.** Tap **Proceed** once. | The backend transaction starts and **Insert bills** opens. The recorded recipient and quote are retained. |
| 6 | Insert the prepared notes one at a time; wait for sorting and the counter update after each note. | Accepted value increases once per note; fee and wallet credit remain consistent with the quote. |
| 7 | For the coin-intake variant, prepare part of G as coins before starting; on intake tap **Insert coins instead** when enabled and insert those coins one at a time. Run this variant as a separate transaction for this provider. | **Insert coins** opens, coin intake is enabled and each accepted coin updates the same transaction total once. If unavailable, mark this variant BLOCKED before funding. |
| 8 | At accepted total G, stop inserting and wait; no final submit button is needed. | Processing starts automatically. The kiosk waits for verified transfer completion; pending transfer alone is not success. |
| 9 | Check the nominated Maya wallet transaction history and balance; capture masked credit evidence. | Exactly one credit of N appears; balance increases by N in the absence of other account activity. No cash payout/change is due in this exact-funded run. |
| 10 | Record the completed screen and execute C1–C5. | **Transaction complete** appears. Wallet credited equals N, accepted cash equals G, fee equals F, change is zero, and physical inventory increases by the accepted denominations. |

### EW-04 — Maya cash-out

**Setup:** Use the nominated QR Ph payer and record the starting wallet balance. Record gross total G, fee F and net N = G - F from the quote. Ensure stocked payout denominations can deliver N.

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| 1 | Tap **Start Transaction → E-Wallet → Maya → Cash Out**. | The Maya cash-out reminder appears. |
| 2 | Read the reminder; tap **Proceed**. Review the fee table, then tap **Proceed**. | The fee table loads for the selected provider/direction, followed by **Enter Amount**. |
| 3 | Enter G on the keypad and tap **Check availability**. | An available quote is created and confirmation opens directly; no recipient-name/mobile entry is required. |
| 4 | Compare confirmation total G, fee F and cash received N with the worksheet; tap **Proceed** once. | A dynamic QR Ph payment screen opens with transaction/payment reference. No cash has dispensed. |
| 5 | On the nominated payer's wallet/bank app, scan the displayed QR. Compare payment amount with G and authorise exactly one payment. | The payer records one debit of G and a payment reference. Scanning without successful payment is insufficient. |
| 6 | Wait for the kiosk to verify payment; do not pay again while waiting. | Only verified payment triggers cash dispensing; pending status is not presented as completion. |
| 7 | Collect and count all dispensed PHP notes/coins; compare denomination counts with the recorded payout plan. | Physical payout totals N = G - F; the customer is not asked to insert cash. |
| 8 | Record payer proof, kiosk reference and completed screen; execute C1–C5. | **Transaction complete** appears; durable cash dispensed equals N, wallet debit equals G, fee equals F, and inventory decreases by actual payout counts. |

### FX-01 — USD to PHP

**Setup:** Prepare one USD 10 note for the base run. Repeat with USD 50 for denomination coverage. Record the locked quote, PHP fee, payout plan and any PHP change separately.

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| 1 | Tap **Start Transaction → Forex → USD-to-PHP**. | The reminder identifies USD input and PHP output. |
| 2 | Read the reminder and tap **Proceed**. | The exchange-rate screen loads current service availability and supported amounts. |
| 3 | Select **10** for the base run, then tap **Proceed**. | Confirmation identifies USD 10 as the source amount and PHP as the payout currency. |
| 4 | Record the quote ID/expiry, rate direction, converted PHP value, PHP fee and **Amount to Dispense**; independently check the arithmetic using the configured rounding rules. | Quoted PHP net equals converted PHP value less PHP fee, subject to the recorded rounding/payout rules. |
| 5 | Tap **Proceed** once while the quote is valid. | The transaction starts, the rate locks and the insertion screen requests USD notes. A refreshed/expired quote must be reviewed again before cash commitment. |
| 6 | Insert the single USD 10 note in the illustrated orientation and wait for authentication/sorting. | The note is authenticated once, counted in USD, and stored in slot 7. |
| 7 | Wait for automatic navigation to the conversion screen, compare the amounts, then tap **Proceed**. | The conversion uses the locked transaction values; the transaction summary opens without dispensing yet. |
| 8 | Review the summary payout and any PHP change against the worksheet, then tap **Proceed** once. | Processing starts for the approved exchange; currency labels and fee remain consistent. |
| 9 | Count the PHP bills/coins delivered, keeping any separately recorded change distinct. | PHP payout denomination counts and total equal the approved plan. No USD/EUR amount is added numerically to PHP. |
| 10 | Wait for success and perform C1–C5. | USD storage increases by the accepted note; PHP inventory decreases by the delivered denominations. Receipt, quote and completed record agree. |

### FX-02 — PHP to USD

**Setup:** Select USD 10 as the base foreign payout and prepare the PHP note combination required by the live quote. Repeat with USD 50 for denomination coverage. Record the locked quote, PHP fee, payout plan and any PHP change separately.

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| 1 | Tap **Start Transaction → Forex → PHP-to-USD**. | The reminder identifies PHP input and USD output. |
| 2 | Read the reminder and tap **Proceed**. | The exchange-rate screen loads current service availability and supported amounts. |
| 3 | Select **10** for the base run, then tap **Proceed**. | Confirmation identifies USD 10 as the foreign amount to receive; **Total Due** is PHP, not USD. |
| 4 | Record the quote ID/expiry, rate direction, converted PHP value, PHP fee and **Total Due**; independently check the arithmetic using the configured rounding rules. | PHP total due equals quoted converted PHP cost plus PHP fee. The foreign output amount remains the selected amount. |
| 5 | Tap **Proceed** once while the quote is valid. | The transaction starts, the rate locks and the insertion screen requests PHP notes. A refreshed/expired quote must be reviewed again before cash commitment. |
| 6 | Insert the recorded PHP notes one at a time, waiting for each acceptance/sorting update. Stop as soon as intake completes. | Each PHP note is counted once and routed to its denomination slot; accepted PHP matches the input plan. |
| 7 | Wait for automatic navigation to the conversion screen, compare the amounts, then tap **Proceed**. | The conversion uses the locked transaction values; the transaction summary opens without dispensing yet. |
| 8 | Review the summary payout and any PHP change against the worksheet, then tap **Proceed** once. | Processing starts for the approved exchange; currency labels and fee remain consistent. |
| 9 | Count the USD notes, then count returned PHP change separately. | Foreign output equals USD 10 for the base run. PHP change equals accepted PHP minus PHP total due and matches the recorded change plan. |
| 10 | Wait for success and perform C1–C5. | PHP inventory increases by accepted notes minus PHP change; USD inventory decreases by the dispensed notes. Receipt, quote and completed record agree. |

### FX-03 — EUR to PHP

**Setup:** Prepare one EUR 5 note for the base run. Repeat with EUR 10 for denomination coverage. Record the locked quote, PHP fee, payout plan and any PHP change separately.

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| 1 | Tap **Start Transaction → Forex → EUR-to-PHP**. | The reminder identifies EUR input and PHP output. |
| 2 | Read the reminder and tap **Proceed**. | The exchange-rate screen loads current service availability and supported amounts. |
| 3 | Select **5** for the base run, then tap **Proceed**. | Confirmation identifies EUR 5 as the source amount and PHP as the payout currency. |
| 4 | Record the quote ID/expiry, rate direction, converted PHP value, PHP fee and **Amount to Dispense**; independently check the arithmetic using the configured rounding rules. | Quoted PHP net equals converted PHP value less PHP fee, subject to the recorded rounding/payout rules. |
| 5 | Tap **Proceed** once while the quote is valid. | The transaction starts, the rate locks and the insertion screen requests EUR notes. A refreshed/expired quote must be reviewed again before cash commitment. |
| 6 | Insert the single EUR 5 note in the illustrated orientation and wait for authentication/sorting. | The note is authenticated once, counted in EUR, and stored in slot 8. |
| 7 | Wait for automatic navigation to the conversion screen, compare the amounts, then tap **Proceed**. | The conversion uses the locked transaction values; the transaction summary opens without dispensing yet. |
| 8 | Review the summary payout and any PHP change against the worksheet, then tap **Proceed** once. | Processing starts for the approved exchange; currency labels and fee remain consistent. |
| 9 | Count the PHP bills/coins delivered, keeping any separately recorded change distinct. | PHP payout denomination counts and total equal the approved plan. No USD/EUR amount is added numerically to PHP. |
| 10 | Wait for success and perform C1–C5. | EUR storage increases by the accepted note; PHP inventory decreases by the delivered denominations. Receipt, quote and completed record agree. |

### FX-04 — PHP to EUR

**Setup:** Select EUR 5 as the base foreign payout and prepare the PHP note combination required by the live quote. Repeat with EUR 10 for denomination coverage. Record the locked quote, PHP fee, payout plan and any PHP change separately.

| Step | Exact action | Expected outcome |
| --- | --- | --- |
| 1 | Tap **Start Transaction → Forex → PHP-to-EUR**. | The reminder identifies PHP input and EUR output. |
| 2 | Read the reminder and tap **Proceed**. | The exchange-rate screen loads current service availability and supported amounts. |
| 3 | Select **5** for the base run, then tap **Proceed**. | Confirmation identifies EUR 5 as the foreign amount to receive; **Total Due** is PHP, not EUR. |
| 4 | Record the quote ID/expiry, rate direction, converted PHP value, PHP fee and **Total Due**; independently check the arithmetic using the configured rounding rules. | PHP total due equals quoted converted PHP cost plus PHP fee. The foreign output amount remains the selected amount. |
| 5 | Tap **Proceed** once while the quote is valid. | The transaction starts, the rate locks and the insertion screen requests PHP notes. A refreshed/expired quote must be reviewed again before cash commitment. |
| 6 | Insert the recorded PHP notes one at a time, waiting for each acceptance/sorting update. Stop as soon as intake completes. | Each PHP note is counted once and routed to its denomination slot; accepted PHP matches the input plan. |
| 7 | Wait for automatic navigation to the conversion screen, compare the amounts, then tap **Proceed**. | The conversion uses the locked transaction values; the transaction summary opens without dispensing yet. |
| 8 | Review the summary payout and any PHP change against the worksheet, then tap **Proceed** once. | Processing starts for the approved exchange; currency labels and fee remain consistent. |
| 9 | Count the EUR notes, then count returned PHP change separately. | Foreign output equals EUR 5 for the base run. PHP change equals accepted PHP minus PHP total due and matches the recorded change plan. |
| 10 | Wait for success and perform C1–C5. | PHP inventory increases by accepted notes minus PHP change; EUR inventory decreases by the dispensed notes. Receipt, quote and completed record agree. |

### 4.3 Additional normal-flow variants

Run these as separate transactions, with their own worksheet and C1–C5 evidence.
They supplement, rather than replace, the 11 base cases above.

| Variant | Exact steps | Expected outcome |
| --- | --- | --- |
| EW-01-COIN / EW-03-COIN | Follow the relevant cash-in procedure using a prepared bill/coin mix totalling G. Before funding, confirm coin intake is available; during intake tap **Insert coins instead** and feed the recorded coins. | The same transaction accounts for both media once; wallet receives G - F and no change is due. |
| EW-01-CHANGE / EW-03-CHANGE | Prepare an approved quote and allowed note combination yielding change C, where 0 < C <= PHP 20, with coin stock available. Record C before insertion; follow cash-in steps and count the returned coins. | Accepted cash = G + C; returned coins = C; wallet credit = G - F. Net retained cash = G. A disallowed note must not be assumed acceptable merely because C is small. |
| MC-03-EXCESS | Use a feasible coin-to-bill quote with an explicitly supported coin excess/refund. Record total intake, fee, bills and excess before funding; follow MC-03 and count the two outputs separately. | Accepted coins equal bill payout + fee + returned coin excess. If no such quote is available, record BLOCKED; never force an extra coin after intake closes. |
| FX-02-CHANGE / FX-04-CHANGE | Obtain an approved PHP-to-foreign quote with feasible PHP change. Record the allowed note combination and change before intake; follow the direction-specific steps. | Foreign payout matches the selected foreign amount; PHP returned equals accepted PHP minus locked PHP total due. |
| Denomination repeats | Repeat the corresponding base procedure with each uncovered supported denomination and a newly recorded feasible quote. | Only physically observed, reconciled acceptance/payout earns a denomination-matrix mark. |


## 5. Run closeout and sign-off

1. Stop customer transactions and wait for all transaction screens to become idle.
2. Recount all affected bills and coins with the witness. Reconcile physical stock
   to starting stock plus accepted cash minus confirmed outputs for each currency.
3. Compare each online transaction with its wallet debit/credit and payment
   reference. Review admin transactions, claims, and reconciliation queues.
4. The run passes only when every required case is PASS, all denomination cells
   required by the planned run are completed, every receipt/evidence packet is
   retained, no claim remains open, and every discrepancy is zero/none.
5. If a case fails, leave the run **NOT ACCEPTED**, create a defect record, and
   do not conceal the result by retrying the same transaction until the prior
   accounting is reconciled.

| Run date | Release / firmware | Operator | Witness | Administrator | Approved exposure | Overall result |
| --- | --- | --- | --- | --- | ---: | --- |
|  |  |  |  |  |  |  |

## 6. Execution and defect templates

### Test result

| Test ID | Date/time | Transaction ID | Quote/payment reference | Input / output | Receipt evidence | Inventory + wallet reconciliation | Result / signatures |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |

### Defect report

| Field | Record |
| --- | --- |
| Defect ID / severity |  |
| Related UAT Test ID / transaction ID |  |
| Time, release, hardware/firmware |  |
| Expected result |  |
| Actual result and customer-facing screen |  |
| Cash/wallet impact and claim reference |  |
| Evidence retained (receipt, masked wallet proof, logs) |  |
| Immediate containment and reconciliation owner |  |
| Resolution / retest result |  |

## 7. Deferred resilience and recovery UAT

These cases are deliberately excluded from the initial happy-path production
acceptance. Plan them in an approved maintenance window with a test ledger,
physical access controls, and recovery owner; never improvise them during a live
customer session.

- Controlled power interruption before/after intake retention and at each payout
  boundary; confirm boot recovery never repeats cash motion or financial credit.
- Tamper during intake, sorting, dispensing, and forex legs; verify lockdown,
  halted motion, administrator-only recovery, and preserved obligation.
- Serial/controller disconnect, camera/authentication failure, network/rate loss,
  PayMongo timeout or delayed callback, and Paperang offline/print failure.
- Bill/coin jam, failed sensor, partial bill/coin payout, extra coin after input
  closure, malformed/lost coin-pulse trains, and inventory shortage.
- Expiry/inactivity, browser reload/disconnect, quote expiry or reapproval, and
  cancellation before and after cash/payment commitment.
- Claim-ticket issuance, provisional physical reconciliation, final settlement,
  duplicate-event/idempotency behavior, and administrator audit records.

