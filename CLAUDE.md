# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Coinnect is a self-service financial kiosk for cash-in/cash-out and money conversion. It integrates hardware (bill/coin handling, security), firmware (dual Arduino Mega controllers), and a Python backend (Raspberry Pi) with ML-based bill authentication.

**Key Architecture:**
- **Raspberry Pi 4/5**: Main controller handling UI, transaction orchestration, bill authentication (camera + YOLO ML), printing, RFID access control, and API calls
- **Arduino Mega #1 (Bill Controller)**: Bill sorting (stepper motor + linear rail) and dispensing (12-unit dispenser array)
- **Arduino Mega #2 (Coin & Security Controller)**: Coin acceptance/dispensing and security hardware (solenoid lock, shock sensors)

**Operational Modes:**
- **Offline**: Money-changer only (PHP cash-to-cash, coin↔bill, bill↔bill)
- **Online**: E-wallet transactions (GCash/Maya) and foreign exchange

## Repository Structure

```
coinnect/
├── backend/          # Python FastAPI backend (Raspberry Pi)
│   ├── app/
│   │   ├── api/      # FastAPI routers (frontend communication)
│   │   ├── core/     # Config, logging, error handling
│   │   ├── drivers/  # Hardware layer (serial, camera)
│   │   ├── services/ # Business logic (transactions, payments)
│   │   └── ml/       # YOLO bill authentication models
│   └── tests/        # PyTest suite
├── firmware/         # Arduino firmware
│   ├── mega_bill/              # Arduino #1 (sorting + dispensing)
│   └── mega_coin_security/     # Arduino #2 (coin + security)
├── frontend/         # (UI - structure TBD)
├── scripts/          # Build/deployment scripts
└── reference/        # Technical specifications (10 documents)
```

## Development Commands

### Backend (Python/FastAPI)

Development environment setup and testing commands are not yet defined. The backend uses:
- Python 3.11+
- FastAPI for REST API
- PySerial for Arduino communication
- Ultralytics YOLO for ML
- PyTest for testing

### Firmware (Arduino)

Firmware uses Arduino IDE or PlatformIO. Build/upload commands are not yet standardized.

## Serial Communication Protocol

**Critical:** All Raspberry Pi ↔ Arduino communication uses JSON over USB serial.

**Port Assignment:**
- Arduino #1 (Bill): `/dev/ttyUSB0` @ 115200 baud
- Arduino #2 (Coin/Security): `/dev/ttyACM0` @ 115200 baud

**Message Format:**
- Command: `{"cmd":"COMMAND","param":"value"}`
- Response: `{"status":"OK","data":{...}}` or `{"status":"ERROR","code":"ERROR_CODE"}`
- Event: `{"event":"EVENT_NAME","data":{...}}`

**Command Routing:**
- Bill sorting/dispensing → Arduino #1 via `/dev/ttyUSB0`
- Coin operations/security → Arduino #2 via `/dev/ttyACM0`

See `reference/08_communication_protocol.md` for full protocol specification.

## Denomination Conventions

**Always use these exact strings:**

**Bills:**
- PHP: `PHP_20`, `PHP_50`, `PHP_100`, `PHP_200`, `PHP_500`, `PHP_1000`
- USD: `USD_10`, `USD_50`, `USD_100`
- EUR: `EUR_5`, `EUR_10`, `EUR_20`

**Sorting Slot Mapping (Arduino #1):**
- Slots 1-6: PHP_20, PHP_50, PHP_100, PHP_200, PHP_500, PHP_1000
- Slot 7: USD (all denominations)
- Slot 8: EUR (all denominations)

## Hardware Pin Conventions

**Raspberry Pi (Bill Acceptor):**
- GPIO17, GPIO27: L298N motor direction (IN1, IN2)
- GPIO22: L298N PWM enable (ENA)
- GPIO5, GPIO6: IR sensors (entry, position)
- GPIO23: UV LED control (relay)
- GPIO24: White LED control (MOSFET)

**Arduino Mega #1 (Bill):**
- D2-D5: Stepper control (STEP, DIR, ENABLE, LIMIT)
- D22-D53 + A0-A15: Dispenser control (see `reference/09_pin_assignments.md`)

**Arduino Mega #2 (Coin/Security):**
- D18: Coin acceptor pulse (INT5)
- D44-D46, D6: Servo PWM (coin dispensers)
- D19-D20: Shock sensors (INT4/INT3)
- D21: Solenoid lock relay
- D22-D23: Status LEDs (red/green)
- A0-A6: Keypad matrix

**Sensor Logic Levels:**
- IR obstacle sensors: LOW = detected (bill/obstacle present)
- SW-420 shock sensors: LOW = vibration detected

## System Design Principles

### Power Loss Recovery
**No UPS present.** System must handle hard power loss at any moment:
- Write-ahead logging for transactions
- Reconcile pending transactions on boot
- Hardware homing sequences on startup to establish known states

### State Management
- Raspberry Pi is the single source of truth for inventory
- No implicit motion: all actuators require explicit commands
- Reserve inventory before dispensing, reconcile after completion
- Security lockdown overrides all other operations

### Configuration Authority
- **Centralized on Raspberry Pi**: All hardware thresholds, servo angles, sensor triggers stored on RPi
- Settings pushed to Arduinos on connection/initialization
- Firmware updates are manual (no OTA)

### Offline-First Design
- Core hardware control is local
- Connectivity required only for e-wallet and foreign exchange
- Offline queue for telemetry/logs when cloud is available

## Error Handling

**Common Error Codes (Serial Protocol):**
- `PARSE_ERROR`, `UNKNOWN_CMD`: Protocol/command issues
- `INVALID_DENOM`, `INVALID_COUNT`: Parameter validation
- `NOT_HOMED`: Sorting mechanism not initialized
- `JAM`, `EMPTY`, `TIMEOUT`, `MOTOR_FAULT`: Hardware faults
- `LOCKED_OUT`: Security lockdown active

**Hardware Timing Expectations:**
- Bill acceptance: ~3-6s typical, 10s max
- Sorting move: ~0.7s per adjacent slot, ~5.5s full travel
- Bill dispense: ~600-700ms per bill
- Coin dispense: ~250ms per coin

## Transaction Flow Examples

### Cash-In (Bills → E-Wallet)
1. User selects provider (GCash/Maya), enters account
2. RPi creates local transaction (pending state)
3. User inserts bills
4. RPi authenticates via camera + ML, identifies denomination
5. RPi commands Arduino #1 to align sorting slot
6. Bill routed to storage, inventory updated
7. On confirmation, RPi calls provider API (requires online)
8. On success: finalize ledger, print receipt
9. On failure: abort transaction, record incident

### Cash-Out (E-Wallet → Cash)
1. User selects provider, requests amount
2. RPi validates capability (inventory, device status)
3. RPi calls provider API to authorize/debit (requires online)
4. RPi computes dispense plan (bills first, then coins)
5. Commands Arduino #1 for bills, Arduino #2 for coins
6. On completion: print receipt, finalize ledger
7. On fault: record incident for operator resolution

### Tamper/Maintenance Flow
1. Arduino #2 detects shock → enters LOCKDOWN, sends TAMPER event
2. RPi halts transactions, displays "Out of Service"
3. Technician scans RFID card (connected to RPi)
4. RPi verifies card, sends SECURITY_UNLOCK to Arduino #2
5. RPi enters maintenance UI (inventory, diagnostics)
6. On exit: RPi sends SECURITY_LOCK to re-arm

## Reference Documentation

Comprehensive technical specs in `reference/`:
- `01_system_overview.md`: High-level architecture
- `02_bill_acceptor_system.md`: Bill intake and authentication
- `03_bill_sorting_system.md`: Linear rail sorting mechanism
- `04_bill_dispensing_system.md`: 12-unit dispenser array
- `05_coin_system.md`: Coin acceptance and dispensing
- `06_security_system.md`: Tamper detection, access control
- `07_power_distribution.md`: ATX PSU, wiring, grounding
- `08_communication_protocol.md`: Serial protocol specification
- `09_pin_assignments.md`: Complete pin mappings
- `10_bill_of_materials.md`: Component list

Additional context:
- `ARCHITECTURE.md`: System-level architecture summary
- `PROJECT.md`: Project goals and status
- `AGENT.md`: Quick reference for hardware conventions
- `ROADMAP.md`: Development roadmap
