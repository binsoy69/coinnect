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
