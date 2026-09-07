# Coinnect Firmware

Arduino CLI firmware for the dual-Mega architecture, with an Arduino Uno
variant for the coin/security controller.

## Controllers

1. **mega_bill**: Controls Bill Sorting (Stepper) and Dispensing (DC Motors).
2. **mega_coin_security**: Controls Coin Acceptor, Coin Sorter Servo, Coin Dispenser (Servos), and Security (Shock Sensors, Solenoid).
3. **uno_coin_security**: Pin-compatible Uno alternative for the coin/security controller. It implements the same operation-ID recovery protocol using the Uno EEPROM.

## Required Libraries

Install these before compiling:

```bash
arduino-cli lib install ArduinoJson@6.21.6
arduino-cli lib install AccelStepper
arduino-cli lib install Servo
arduino-cli lib install MFRC522
arduino-cli lib install PinChangeInterrupt
```

`uno_coin_security` requires ArduinoJson 6.x. ArduinoJson 7 uses heap-backed
JSON documents and can exhaust the Uno's 2 KB SRAM, causing valid commands to
produce empty `{}` serial responses. The sketch includes a compile-time guard
against building the Uno firmware with ArduinoJson 7.

Uno firmware 3.1.1 keeps JSON field names in flash with `F()` rather than in
permanent SRAM. ArduinoJson copies those keys into the active response document;
`COMMAND_JSON_CAPACITY` reserves six fields plus 80 bytes for those copies.
With Arduino AVR Boards 1.8.8 and ArduinoJson 6.21.6, the build uses 1,106 bytes
of global SRAM, leaving 942 bytes for the stack and interrupts (3.1.0 left only
566). The previous build's serial corruption is reproducible in the AVR
simulator below. Do not increase document sizes without rechecking memory use.
An overflowing response now returns `ERROR/RESPONSE_OVERFLOW` with its command
ID instead of sending a partial success response.

The Uno also has a 64-byte hardware serial receive ring while operation-ID
commands can exceed 100 bytes. The backend therefore resynchronizes and paces
coin-controller writes, and firmware 3.0.5 prioritizes serial draining over
potentially blocking MFRC522 polls, avoids heap-allocating RFID strings, and
detaches idle servos to reduce reset-inducing current draw. Keep both transport
protections enabled to avoid truncated commands and `PARSE_ERROR` responses.

## Compile

```bash
arduino-cli compile --fqbn arduino:avr:mega firmware/mega_bill
arduino-cli compile --fqbn arduino:avr:mega firmware/mega_coin_security
arduino-cli compile --fqbn arduino:avr:uno firmware/uno_coin_security
arduino-cli compile --fqbn arduino:avr:mega firmware/test_shock_sensor
arduino-cli compile --fqbn arduino:avr:mega firmware/test_solenoid
```

## Upload

```bash
arduino-cli upload --port /dev/ttyUSB0 --fqbn arduino:avr:mega firmware/mega_bill
arduino-cli upload --port /dev/ttyACM0 --fqbn arduino:avr:mega firmware/mega_coin_security
arduino-cli upload --port /dev/ttyACM0 --fqbn arduino:avr:uno firmware/uno_coin_security
arduino-cli upload --port /dev/ttyACM0 --fqbn arduino:avr:mega firmware/test_shock_sensor
arduino-cli upload --port /dev/ttyACM0 --fqbn arduino:avr:mega firmware/test_solenoid
```

Upload only one sketch at a time to the coin/security Mega. The `test_*`
sketches are bench tools and replace the production `mega_coin_security`
firmware until the production sketch is uploaded again.

Upload either `mega_coin_security` or `uno_coin_security`, according to the
installed board. Both require UUID operation IDs for `COIN_DISPENSE`, journal
dispense intent before servo motion, and support operation status and
ambiguity acknowledgement commands.

## Smoke Test

Default smoke checks avoid actuator commands:

```bash
python scripts/firmware_smoke.py
```

After flashing the Uno, stop the backend so it does not compete for the serial
port, then run repeated coin-controller recovery probes:

```bash
python scripts/firmware_smoke.py --skip-bill --coin-port /dev/coinnect_coin --iterations 25
```

The safe probe verifies command IDs and operation IDs, rejects malformed UTF-8
or JSON with the raw bytes included in the error, queries unknown operation
status/acknowledgement, verifies converter protocol 2, checks `PONG` after each
recovery reply, and repeatedly confirms the coin acceptor is disabled.
If the controller reports an operation requiring reconciliation, the probe
stops before continuing; resolve that operation through the backend first.

### Uno serial regression without hardware

The simulator runs the actual compiled HEX with 2 KB SRAM, timer interrupts,
UART and erased EEPROM. RFID register reads are stubbed; this does not replace
the physical smoke test. The original 3.1.0 build fails with malformed JSON;
3.1.1 passes the repeated recovery, capability, ping and status checks.

From the repository root (Linux/Raspberry Pi):

```bash
arduino-cli compile --fqbn arduino:avr:uno --build-path /tmp/coinnect-uno firmware/uno_coin_security
npm install --prefix /tmp/coinnect-avr-test avr8js@0.21.1 --no-audit --no-fund
NODE_PATH=/tmp/coinnect-avr-test/node_modules node scripts/test_uno_serial.cjs /tmp/coinnect-uno/uno_coin_security.ino.hex
```

Run actuator checks only after wiring is verified:

```bash
python scripts/firmware_smoke.py --actuate
```

The bill controller emits `READY` on boot, then attempts sorter auto-home with
a timeout fail-safe. If homing fails, `SORT_STATUS` reports `homed: false` and
`SORT` returns `NOT_HOMED`.

The coin/security controller keeps the coin acceptor disabled on boot. `D24`
is the active-HIGH acceptor enable signal, and `D7` drives the three-position
coin sorter servo: `CENTER=81`, `LEFT=45`, and `RIGHT=120`. PHP 1 and PHP 5
coins sort right; PHP 10 and PHP 20 coins sort left. The safe smoke test reads
`COIN_STATUS`; `--actuate` toggles the acceptor enable and moves the sorter.

## Hardware Bench Tests

`firmware/test_shock_sensor` tests the production shock sensor pins D19 and
D20. The SW-420 sensing element is normally closed at rest, while module `DO`
is HIGH at idle/no vibration and falls LOW on vibration. The sketch uses
`INPUT_PULLUP`, falling-edge interrupts, and prints current levels plus tamper
events at 115200 baud.

`firmware/test_solenoid` tests the production solenoid relay pin D21 and LEDs
D22/D23. It boots locked/off with D21 LOW, red LED on, and green LED off.
Actuation is serial-command only: send `LOCK`, `UNLOCK`, `PULSE`, `STATUS`, or
`HELP` at 115200 baud. `PULSE` energizes D21 briefly and then returns locked.
