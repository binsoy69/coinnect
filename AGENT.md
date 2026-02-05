# Coinnect Agent Notes

These notes summarize project conventions and architecture based on the reference docs in `reference/` (version 2.0, February 2026). Use this as a quick context guide when working on hardware, firmware, or integration tasks.

**Project Summary**
Coinnect is a unified kiosk for multiple financial services. It combines bill acceptance (camera + ML), bill sorting and dispensing, coin acceptance and dispensing, security controls, and a touchscreen UI with printing. A Raspberry Pi is the main controller and two Arduino Mega boards split the hardware subsystems.

**System Architecture**
- Raspberry Pi 4/5
- Handles bill authentication (camera + ML), UI, API communication, and thermal printing
- Directly controls the bill acceptor motor and sensors
- Arduino Mega #1 (Bill Controller)
- Bill sorting (stepper + A4988)
- Bill dispensing (12 L298N units, 24 DC motors, 12 IR sensors)
- Arduino Mega #2 (Coin + Security Controller)
- Coin acceptor (pulse input)
- Coin dispensers (4 servos)
- Security (shock sensors, solenoid lock, keypad, LEDs)

**Serial Protocol (RPi <-> Arduino)**
- Two USB serial ports
- Arduino #1: `/dev/ttyUSB0`
- Arduino #2: `/dev/ttyACM0`
- 115200 baud, 8N1, newline delimited JSON

Message formats:
- Command: `{"cmd":"COMMAND","param":"value"}`
- Response: `{"status":"OK","data":{...}}` or `{"status":"ERROR","code":"ERROR_CODE"}`
- Event: `{"event":"EVENT_NAME","data":{...}}`

Command routing:
- Sorting: `SORT`, `HOME`, `SORT_STATUS` -> Arduino #1
- Dispense bills: `DISPENSE`, `DISPENSE_STATUS` -> Arduino #1
- Coin: `COIN_DISPENSE`, `COIN_CHANGE`, `COIN_RESET` -> Arduino #2
- Security: `SECURITY_LOCK`, `SECURITY_UNLOCK`, `SECURITY_STATUS` -> Arduino #2
- System: `PING`, `VERSION`, `RESET` -> either

**Denomination Conventions**
Use these exact strings in commands and mappings:
- PHP: `PHP_20`, `PHP_50`, `PHP_100`, `PHP_200`, `PHP_500`, `PHP_1000`
- USD: `USD_10`, `USD_50`, `USD_100`
- EUR: `EUR_5`, `EUR_10`, `EUR_20`

Sorting slot mapping (Arduino #1):
- Slot 1: PHP_20
- Slot 2: PHP_50
- Slot 3: PHP_100
- Slot 4: PHP_200
- Slot 5: PHP_500
- Slot 6: PHP_1000
- Slot 7: USD_* (10, 50, 100)
- Slot 8: EUR_* (5, 10, 20)

**Key Pin Conventions**
Raspberry Pi (bill acceptor):
- GPIO17: L298N IN1 (motor direction)
- GPIO27: L298N IN2 (motor direction)
- GPIO22: L298N ENA (PWM)
- GPIO5: IR Sensor 1 (bill entry)
- GPIO6: IR Sensor 2 (bill position)
- GPIO23: UV LED control (relay)
- GPIO24: White LED control (MOSFET)

Arduino Mega #1 (bill sorting + dispensing):
- Stepper: D2 (STEP), D3 (DIR), D4 (ENABLE), D5 (LIMIT)
- Dispensers: D22-D53 and A0-A15 (see `reference/09_pin_assignments.md`)

Arduino Mega #2 (coin + security):
- D18: Coin acceptor pulse (INT5)
- D44/D45/D46/D6: Servo PWM for coin dispensers
- D19/D20: Shock sensors (INT4/INT3)
- D21: Solenoid lock relay
- D22/D23: LED red/green
- A0-A6: Keypad rows/cols

**Logic Levels and Sensor Behavior**
- IR obstacle sensors (bill acceptor + dispensers): LOW means obstacle detected (bill present)
- SW-420 shock sensors: LOW means vibration detected

**Timing Expectations (Typical)**
- Bill acceptance (RPi-controlled): ~3-6s typical, 10s max
- Sorting move: ~0.7s per adjacent slot, ~5.5s full travel
- Bill dispense: ~600-700ms per bill
- Coin dispense: ~250ms per coin

**Error Codes and Status Conventions**
Common error codes from serial protocol:
- `PARSE_ERROR`, `UNKNOWN_CMD`, `INVALID_DENOM`, `INVALID_COUNT`, `NOT_HOMED`
- `JAM`, `EMPTY`, `TIMEOUT`, `MOTOR_FAULT`, `LOCKED_OUT`
Bill dispense specific:
- `INVALID_UNIT`, `UNKNOWN_DENOM`, `JAM_OR_EMPTY`, `MOTOR_FAULT`

**Power and Wiring Conventions**
- Main power: ATX PSU with +12V, +5V, +3.3V rails
- Use star-grounding with a central ground bus
- Wire color code:
  - RED: +5V
  - YELLOW: +12V
  - BLACK: GND
  - ORANGE: +3.3V
  - GREEN: signal input
  - BLUE: signal output
  - WHITE: serial TX
  - GRAY: serial RX
  - PURPLE: PWM
- Do not power Raspberry Pi from L298N 5V output
- Servo power must be external 5V (not Arduino 5V) and share a common ground
- Add decoupling caps near each L298N and the A4988 as specified in docs

**Safety and Operational Notes**
- Keep common ground between PSU, RPi, Arduinos, and all peripherals
- Use fuses per branch as outlined in `reference/07_power_distribution.md`
- Security system supports keypad PIN, tamper detection, and lockout

**Reference Docs**
- System overview: `reference/01_system_overview.md`
- Bill acceptor: `reference/02_bill_acceptor_system.md`
- Bill sorting: `reference/03_bill_sorting_system.md`
- Bill dispensing: `reference/04_bill_dispensing_system.md`
- Coin system: `reference/05_coin_system.md`
- Security system: `reference/06_security_system.md`
- Power distribution: `reference/07_power_distribution.md`
- Serial protocol: `reference/08_communication_protocol.md`
- Pin assignments: `reference/09_pin_assignments.md`
- BOM: `reference/10_bill_of_materials.md`
