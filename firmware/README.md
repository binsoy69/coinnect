# Coinnect Firmware

Arduino CLI firmware for the dual-Mega architecture.

## Controllers

1. **mega_bill**: Controls Bill Sorting (Stepper) and Dispensing (DC Motors).
2. **mega_coin_security**: Controls Coin Acceptor, Coin Sorter Servo, Coin Dispenser (Servos), and Security (Shock Sensors, Solenoid).

## Required Libraries

Install these before compiling:

```bash
arduino-cli lib install ArduinoJson
arduino-cli lib install AccelStepper
arduino-cli lib install Servo
```

## Compile

```bash
arduino-cli compile --fqbn arduino:avr:mega firmware/mega_bill
arduino-cli compile --fqbn arduino:avr:mega firmware/mega_coin_security
```

## Upload

```bash
arduino-cli upload --port /dev/ttyUSB0 --fqbn arduino:avr:mega firmware/mega_bill
arduino-cli upload --port /dev/ttyACM0 --fqbn arduino:avr:mega firmware/mega_coin_security
```

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
coins sort left; PHP 10 and PHP 20 coins sort right. The safe smoke test reads
`COIN_STATUS`; `--actuate` toggles the acceptor enable and moves the sorter.
