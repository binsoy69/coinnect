# Coinnect Project Roadmap

This document serves as the master checklist for the Coinnect development lifecycle. It is designed to be executed sequentially, but modules within phases can be parallelized.

**Technology Stack:**

- **Frontend**: React (Vite) + TailwindCSS (for "Stunning/Premium" UI).
- **Backend**: Python (FastAPI) + PySerial (Hardware Comms) + Ultralytics (ML).
- **Firmware**: C++ (PlatformIO/Arduino) for Arduino Mega 2560.

---

## ✅ Phase 0: Project Setup & Structure

- [x] **Initialize Project Structure**
  - Create `backend/`, `frontend/`, `firmware/` directories.
  - Set up `tests/` folders for unit and integration testing.
- [x] **Setup Python Environment**
  - [x] Create `backend/requirements.txt` with `fastapi`, `uvicorn`, `pyserial`, `ultralytics`, `pytest`, `pytest-asyncio`.
  - [x] Create virtual environment setup scripts (`setup_venv.sh` and `setup_venv.bat`).
  - [x] User needs to install Python 3.11+ and run setup script.
- [x] **Setup Frontend Environment**
  - [x] Initialize React + Vite project in `frontend/`.
  - [x] Install TailwindCSS and configure `postcss.config.js`.
  - [x] Install `lucide-react` (icons) and `framer-motion` (animations).

**Testing:**

- Verify Python setup: `python --version` (Should be 3.11+) - _Python not yet installed_
- Verify Frontend setup: `cd frontend && npm run dev` (Should load Coinnect welcome page with TailwindCSS styling)

---

## ✅ Phase 1: High-Impact UI/UX (Frontend Priority)

_Goal: Create a visually stunning, premium interface based on mockup designs before connecting real logic._

> **Detailed Implementation Plan**: See [`UI.md`](UI.md) for the complete UI/UX implementation roadmap including design system, file structure, routes, and screen-by-screen checklist.

**Current Scope (Money Converter Flow):**

- [x] **Phase 1.1: Foundation Setup**
  - [x] Install `react-router-dom`
  - [x] Update TailwindCSS to light theme with orange accents
  - [x] Setup router configuration
- [x] **Phase 1.2: Core Components**
  - [x] Button, Card, Header, Clock, Timer components
  - [x] PageLayout, PageTransition wrappers
- [x] **Phase 1.3: Initial Flow Screens**
  - [x] Initial/Attract Screen
  - [x] Transaction Type Selection
  - [x] Service Selection (Money Converter)
  - [x] Reminder/Disclaimer Screen
- [x] **Phase 1.4: Transaction Components**
  - [x] ServiceCard, DenominationGrid, DenominationCheckbox
  - [x] MoneyCounter, TransactionCard
- [x] **Phase 1.5: Transaction Flow Screens**
  - [x] Select Amount, Select Dispense, Transaction Fee
  - [x] Confirmation, Insert Money, Transaction Summary
- [x] **Phase 1.6: Feedback Screens**
  - [x] Processing (loading animation)
  - [x] Success (animated checkmark)
  - [x] Warning (amount mismatch)
- [x] **Phase 1.7: Additional Flows**
  - [x] Bill-to-Coin flow
  - [x] Coin-to-Bill flow
- [x] **Phase 1.8: Polish & Animations**
  - [x] Page transitions
  - [x] Button/card hover effects
  - [x] Sponsor panel integration

**Forex UI Flow (Phase 1.9):**

- [x] **Phase 1.9.1: Forex Foundation**
  - [x] Add forex route constants to `routes.js`
  - [x] Create forex service config in `forexData.js`
  - [x] Create `ForexContext` for state management
- [x] **Phase 1.9.2: Forex Components**
  - [x] `ExchangeRateCard` - Live rate display with flag
  - [x] `CurrencyAmountGrid` - Currency amount selection
  - [x] `ConversionDisplay` - Conversion table
- [x] **Phase 1.9.3: Forex Screens**
  - [x] ForexServiceSelectionScreen (4 service cards)
  - [x] ForexReminderScreen (red disclaimer)
  - [x] ExchangeRateScreen (rate + amount selection)
  - [x] ForexConfirmationScreen (confirm conversion)
  - [x] ForexInsertMoneyScreen (insert foreign/PHP bills)
  - [x] ForexConversionScreen (show conversion result)
  - [x] ForexSummaryScreen (transaction card)
  - [x] ForexProcessingScreen (loading animation)
  - [x] ForexSuccessScreen (green checkmark)
  - [x] ForexWarningScreen (amount mismatch)
- [x] **Phase 1.9.4: Flow Integration**
  - [x] Enable forex card on TransactionTypeScreen
  - [x] Test all 4 forex flows (USD↔PHP, EUR↔PHP)
  - [x] Verify red theme consistency
  - [x] Test animations and back navigation

**Future Additions (After Core Flow):**

- [ ] **Localization (i18n)**
  - [ ] Setup `react-i18next` with Filipino and English language files.
  - [ ] Create language selector component.
  - [ ] Translate all user-facing strings.
- [ ] **Session Timeout System**
  - [ ] Implement smart timeout with stage-aware durations.
  - [ ] Create countdown warning overlay (15s before timeout).
  - [ ] Handle graceful transaction cancellation on timeout.

**Automated Tests:**

- Check linting: `npm run lint`
- Component tests (optional if using Vitest): `npm test`

---

## ⚙️ Phase 2: Hardware Drivers & Emulation (Backend Layer 1)

_Goal: Create Python drivers that can talk to "Mock" Arduino, allowing development without hardware._

- [ ] **Serial Protocol Implementation**
  - [ ] Create `BillController` class (wraps Arduino #1 commands).
  - [ ] Create `CoinSecurityController` class (wraps Arduino #2 commands).
  - [ ] Implement `MockSerial` class to simulate Arduino responses for testing.
  - [ ] **Test**: `pytest tests/unit/test_serial_protocol.py` (Verify JSON framing/parsing).
- [ ] **Hardware State Machine**
  - [ ] Create `MachineStatus` store (holds current sensor states).
  - [ ] Implement event loop to poll/read from serial ports.
  - [ ] **Test**: `pytest tests/unit/test_state_machine.py`.
- [ ] **Receipt Printer Driver**
  - [ ] Implement ESC/POS protocol driver for thermal printer.
  - [ ] Create receipt templates (transaction receipt, claim ticket).
  - [ ] **Test**: `pytest tests/unit/test_printer_driver.py`.
- [ ] **Consumables Monitoring**
  - [ ] Implement paper level sensor reading.
  - [ ] Track storage slot bill counts (estimated fullness).
  - [ ] Track dispenser inventory levels.
  - [ ] Define alert thresholds for low consumables.
- [ ] **Claim Ticket System**
  - [ ] Generate unique alphanumeric claim codes.
  - [ ] Store claim ticket data (transaction ID, amounts, timestamp).
  - [ ] Expose API for customer service lookup.

---

## 💰 Phase 3: Money Changer (Offline Core)

_Goal: Enable PHP Bill <-> Coin conversion without Internet._

- [ ] **Bill Acceptance Logic**
  - [ ] Implement `accept_bill()` flow:
    - Trigger Camera -> Run YOLO -> Validate -> Command Sort -> Command Store.
  - [ ] **Test**: `pytest tests/integration/test_bill_acceptance.py`.
- [ ] **Dispensing Logic (Bills + Coins)**
  - [ ] Implement `calculate_change(amount)` algorithm.
  - [ ] Implement `dispense_sequence()` (send commands to Arduino #1 & #2).
  - [ ] **Test**: `pytest tests/unit/test_change_calculator.py` (Verify math is perfect).
- [ ] **Transaction Orchestrator (Money Changer)**
  - [ ] Connect Frontend "Money Changer" UI to Backend `start_transaction` API.
  - [ ] Handle `bill_inserted` events and push updates to UI via WebSocket/SSE.
- [ ] **Storage Slot Management**
  - [ ] Track bill counts per storage slot.
  - [ ] Implement fullness alerts at configurable thresholds (~80%).
  - [ ] Disable acceptance for specific denomination when slot is full.

---

## 📱 Phase 4: E-Wallet Integration (Online)

_Goal: Connect GCash/Maya flows._

- [ ] **API Client Wrapper**
  - [ ] Create `PaymentGateway` abstract class.
  - [ ] Implement `GCashProvider` (simulated or real sandbox API).
  - [ ] Implement `MayaProvider` (simulated or real sandbox API).
  - [ ] **Test**: `pytest tests/unit/test_payment_providers.py`.
- [ ] **Cash-In Flow**
  - [ ] UI: Phone Number Entry Keypad.
  - [ ] Backend: Validate Account -> Accept Cash -> Trigger Top-up API.
- [ ] **Cash-Out Flow**
  - [ ] UI: Amount Selection -> QR Code Display (for user to scan) OR Phone Entry.
  - [ ] Backend: Poll for payment completion -> Trigger Dispense.
  - [ ] **Test**: `pytest tests/integration/test_cash_out_flow.py`.

---

## 🌍 Phase 5: Foreign Exchange

_Goal: Accept USD/EUR and dispense PHP._

- [ ] **Forex Rate Service**
  - [ ] Implement `ForexAPI` client (fetch rates from external provider).
  - [ ] Implement local caching with 24-hour expiry.
  - [ ] Add "Spread/Fee" configuration.
  - [ ] Handle offline gracefully (use cached rates if valid, block if expired).
  - [ ] **Test**: `pytest tests/unit/test_forex_rates.py`.
- [ ] **Multi-Currency Bill Recognition**
  - [ ] Update YOLO model integration to handle USD/EUR labels.
  - [ ] Update `BillController` to map foreign bills to specific storage slots (7 & 8).
- [ ] **Exchange Logic**
  - [ ] `calculate_forex_conversion(input_currency, amount)` logic.
  - [ ] Update UI to show "Estimated Rate" and "Final Amount".

---

## 🔒 Phase 6: Security & Hardening

- [ ] **Security Controller Integration**
  - [ ] Listen for `TAMPER` events from Arduino #2.
  - [ ] Implement `LockdownMode`: Reject inputs, show red screen, lock solenoid.
  - [ ] **Test**: `pytest tests/integration/test_security_lockdown.py`.
- [ ] **Maintenance Mode**
  - [ ] Implement `RFID_AUTH` handler.
  - [ ] Create Hidden "Admin Dashboard" in Frontend (Inventory, Logs, Basic Status).
- [ ] **Remote Alert System**
  - [ ] Implement push notification service for technician alerts.
  - [ ] Alert categories: low consumables, hardware faults, security events, transaction anomalies.
  - [ ] Configure alert thresholds and recipient(s).

---

## 📊 Phase 6.5: Telemetry & Monitoring

_Goal: Enable basic remote visibility into kiosk health and operations._

- [ ] **Telemetry Collector**
  - [ ] Implement periodic health heartbeat (device status, connectivity).
  - [ ] Collect transaction summaries (counts, amounts, success/failure rates).
  - [ ] Queue telemetry data when offline, sync when online.
- [ ] **Cloud Sync**
  - [ ] Define telemetry payload format (JSON schema).
  - [ ] Implement HTTPS POST to telemetry endpoint.
  - [ ] Handle authentication (API key or token).
- [ ] **Consumables Dashboard API**
  - [ ] Expose current consumable levels via REST endpoint.
  - [ ] Expose recent alerts and incidents.

---

## 🧪 Phase 7: Verification & Deployment

- [ ] **End-to-End Simulation**
  - [ ] Run full software stack with `MockSerial`.
  - [ ] Perform full "User Journey": Start -> Cash In -> Success.
- [ ] **Hardware Integration Testing**
  - [ ] Flash Firmware to Arduinos.
  - [ ] Connect RPi and run "Smoke Tests" (Ping, Motor Move, LED toggle).
- [ ] **Kiosk Setup**
  - [ ] Configure RPi to boot directly into Browser (Kiosk Mode).
  - [ ] Set up `systemd` service for Backend.

---

## 🛠 Feature Tasks (Granular)

### Backend

**Core Infrastructure:**

- [ ] `[BE-001]` Create FastAPI entry point `main.py` with CORS and lifespan handlers
- [ ] `[BE-002]` Implement `SerialManager` with auto-reconnect and port detection
- [ ] `[BE-003]` Create Pydantic models for `Transaction`, `HardwareEvent`, `MachineState`
- [ ] `[BE-004]` Implement Logging (File-based + Console with rotation)

**Frontend Communication (WebSocket + REST):**

- [ ] `[BE-015]` Implement WebSocket manager (`/ws` endpoint) for real-time event broadcast
- [ ] `[BE-016]` Create `ConnectionManager` class to track active WebSocket clients
- [ ] `[BE-017]` Define WebSocket event schema (type, payload, timestamp)
- [ ] `[BE-018]` Implement REST API router structure (`/api/v1/`)
- [ ] `[BE-019]` Create transaction endpoints: `POST /transaction`, `GET /transaction/{id}`, `DELETE /transaction/{id}`
- [ ] `[BE-020]` Create machine status endpoint: `GET /status` (inventory, device health, connectivity)
- [ ] `[BE-021]` Implement event bridge: serial events → WebSocket broadcast

**Transaction State Machine:**

- [ ] `[BE-022]` Implement `TransactionStateMachine` class with defined states and transitions
- [ ] `[BE-023]` Define transaction states: `IDLE`, `WAITING_FOR_BILL`, `AUTHENTICATING`, `SORTING`, `WAITING_FOR_CONFIRMATION`, `DISPENSING`, `COMPLETE`, `CANCELLED`, `ERROR`
- [ ] `[BE-024]` Implement state transition validation (prevent invalid state jumps)
- [ ] `[BE-025]` Add state change event emission to WebSocket on every transition
- [ ] `[BE-026]` Implement transaction timeout handling (accept cancellation from frontend)
- [ ] `[BE-027]` Implement write-ahead logging for crash recovery

**Hardware Drivers:**

- [ ] `[BE-005]` Implement ESC/POS receipt printer driver
- [ ] `[BE-006]` Implement consumables monitoring (paper sensor, slot counters)
- [ ] `[BE-007]` Implement claim ticket generation system
- [ ] `[BE-008]` Add storage slot fullness tracking and alerts

**External Integrations:**

- [ ] `[BE-009]` Implement forex rate API client with local caching (24h expiry)
- [ ] `[BE-010]` Implement remote alert push notifications to technician
- [ ] `[BE-011]` Implement basic telemetry collector
- [ ] `[BE-012]` Implement telemetry cloud sync service
- [ ] `[BE-013]` Create consumables dashboard data API
- [ ] `[BE-014]` Implement offline queue for API calls (sync when online)

### Frontend

**Routing & State:**

- [ ] `[FE-001]` Setup React Router with route guards
- [ ] `[FE-002]` Create `WebSocketContext` for real-time hardware events
- [ ] `[FE-003]` Implement `useTransaction` hook (start, cancel, get state from backend)
- [ ] `[FE-009]` Create `useMachineStatus` hook (poll/subscribe to machine health)
- [ ] `[FE-010]` Implement WebSocket reconnection logic with exponential backoff

**UI Components:**

- [ ] `[FE-003]` Design `VirtualKeypad` component
- [ ] `[FE-007]` Design claim ticket display screen
- [ ] `[FE-008]` Create timeout countdown warning overlay
- [ ] `[FE-011]` Create hardware event toast/notification component
- [ ] `[FE-012]` Create "Out of Service" overlay (triggered by backend TAMPER event)

**Localization & Accessibility:**

- [ ] `[FE-004]` Integrate `react-i18next` with Filipino + English translations
- [ ] `[FE-005]` Create language selector component
- [ ] `[FE-006]` Implement smart session timeout with stage-aware durations

**Forex UI:**

- [ ] `[FE-013]` Create `ForexContext` with rate locking and conversion state
- [ ] `[FE-014]` Create `ExchangeRateCard` component (flag, country, rate)
- [ ] `[FE-015]` Create `CurrencyAmountGrid` component (€5, €10, $10, etc.)
- [ ] `[FE-016]` Create `ConversionDisplay` component (Amount | From | To table)
- [ ] `[FE-017]` Implement 10 forex screens (see UI.md Phase 1.9.3)
- [ ] `[FE-018]` Add forex routes and navigation
- [ ] `[FE-019]` Enable forex flow on TransactionTypeScreen

### Firmware

- [ ] `[FW-001]` **Mega #1**: Implement Stepper Control (AccelStepper)
- [ ] `[FW-002]` **Mega #1**: Implement Packet Parser (JSON)
- [ ] `[FW-003]` **Mega #2**: Implement Servo Control for Coin Dispenser
- [ ] `[FW-004]` **Mega #2**: Implement Interrupts for Shock Sensors
