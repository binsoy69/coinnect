# Coinnect System Architecture

## 09 - Pin Assignments

**Document Version:** 2.1
**Date:** May 2026

---

## 9.1 Raspberry Pi 4/5 GPIO Assignments

### 9.1.1 Bill Acceptor System

| GPIO | Header Pin | Function | Direction | Notes |
| ---- | ---------- | -------- | --------- | ----- |
| GPIO17 | 11 | L298N IN1 | Output | Bill acceptor motor direction |
| GPIO27 | 13 | L298N IN2 | Output | Bill acceptor motor direction |
| GPIO22 | 15 | L298N ENA | Output PWM | Bill acceptor motor speed |
| GPIO5 | 29 | Entry IR Sensor | Input | Bill entry, pull-up enabled |
| GPIO6 | 31 | Unused | - | Available spare GPIO |
| GPIO23 | 16 | UV LED Control | Output | Relay or MOSFET driver |
| GPIO24 | 18 | White LED Control | Output | MOSFET driver |
| 3.3V | 1, 17 | Sensor Power | Power | IR sensor VCC |
| GND | Multiple | Common Ground | Ground | Shared signal ground |

### 9.1.2 RPi Peripheral Connections

| Interface | Device | Notes |
| --------- | ------ | ----- |
| USB 3.0 | 1080p Camera | Bill authentication |
| USB 2.0 | Arduino Mega #1 | Bill Controller, `/dev/ttyUSB0` |
| USB 2.0 | Arduino Mega #2 | Coin & Security Controller, `/dev/ttyACM0` |
| Bluetooth | Paperang P1 Printer | Receipt printing |
| HDMI | Touchscreen Display | 10-15 inch display |
| USB | Touchscreen Touch | Touch input |

---

## 9.2 Arduino Mega Controller Separation

The system uses two Arduino Mega 2560 boards. Pin numbers are scoped to the
controller they are on, so `D7` on Mega #1 and `D7` on Mega #2 are independent
signals and do not conflict.

| Controller | Serial Port | Subsystems |
| ---------- | ----------- | ---------- |
| Arduino Mega #1 | `/dev/ttyUSB0` | Bill sorting and bill dispensing |
| Arduino Mega #2 | `/dev/ttyACM0` | Coin acceptance, coin dispensing, sorter, and security |

---

## 9.3 Arduino Mega #1: Bill Controller

### 9.3.1 Bill Sorting System

| Pin | Function | Type | Notes |
| --- | -------- | ---- | ----- |
| D2 | A4988 STEP | Output | Step pulse |
| D3 | A4988 DIR | Output | Direction |
| D4 | A4988 ENABLE | Output | Active LOW |
| D5 | Limit Switch | Input | `INPUT_PULLUP`, LOW = home |

### 9.3.2 Bill Dispensing System

| Unit | Denomination | IN1 | IN2 | IN3 | IN4 | IR Sensor |
| ---- | ------------ | --- | --- | --- | --- | --------- |
| 1 | PHP_20 | D22 | D23 | D24 | D25 | A0 |
| 2 | PHP_50 | D26 | D27 | D28 | D29 | A1 |
| 3 | PHP_100 | D30 | D31 | D32 | D33 | A2 |
| 4 | PHP_200 | D34 | D35 | D36 | D37 | A3 |
| 5 | PHP_500 | D38 | D39 | D40 | D41 | A4 |
| 6 | PHP_1000 | D42 | D43 | D44 | D45 | A5 |
| 7 | USD_10 | D46 | D47 | D48 | D49 | A6 |
| 8 | USD_50 | D50 | D51 | D52 | D53 | A7 |
| 9 | USD_100 | A8 | A9 | A10 | A11 | D14 |
| 10 | EUR_5 | A12 | A13 | A14 | A15 | D15 |
| 11 | EUR_10 | D7 | D8 | D9 | D10 | D16 |
| 12 | EUR_20 | D11 | D12 | D13 | - | D17 |

Unit 12 uses three motor direction pins in the current firmware. Analog pins
`A0-A15` are used as digital I/O on Mega #1.

---

## 9.4 Arduino Mega #2: Coin & Security Controller

### 9.4.1 Coin Acceptance and Sorting

| Pin | Function | Type | Notes |
| --- | -------- | ---- | ----- |
| D18 | Coin Acceptor Pulse | Input interrupt | `INT5`, pulse count maps 1/5/10/20 to PHP_1/PHP_5/PHP_10/PHP_20 |
| D24 | Coin Acceptor Enable | Output | Active HIGH, default LOW/disabled |
| D7 | Coin Sorter Servo | PWM output | `CENTER=81`, `LEFT=45`, `RIGHT=120` |

The acceptor enable line must be driven HIGH only while coin intake is allowed.
If the coin acceptor module enable input is not 5V Arduino-logic compatible,
drive it through a transistor, optocoupler, or level shifter instead of wiring
`D24` directly.

### 9.4.2 Coin Dispensing

| Pin | Function | Type |
| --- | -------- | ---- |
| D44 | PHP_1 dispenser servo | PWM output |
| D45 | PHP_5 dispenser servo | PWM output |
| D46 | PHP_10 dispenser servo | PWM output |
| D6 | PHP_20 dispenser servo | PWM output |

### 9.4.3 Security and Maintenance

| Pin | Function | Type | Notes |
| --- | -------- | ---- | ----- |
| D19 | Shock Sensor A | Input interrupt | `INT4`, SW-420 NC module DO, HIGH idle / LOW vibration |
| D20 | Shock Sensor B | Input interrupt | `INT3`, SW-420 NC module DO, HIGH idle / LOW vibration |
| D21 | Solenoid Relay | Output | Lock control |
| D22 | Red Status LED | Output | Fault/lockdown indicator |
| D23 | Green Status LED | Output | Ready/normal indicator |
| A0-A6 | Keypad Matrix | I/O | 4 rows + 3 columns |

Shock sensors use the SW-420 module digital output. The sensing element is
normally closed at rest, but firmware reads module `DO`: HIGH means idle/no
vibration, LOW means vibration/tamper. Inputs use `INPUT_PULLUP` and detect
tamper on the falling edge. This is not a fail-safe broken-wire NC loop.

---

## 9.5 Pin Conflict Notes

The dual-Mega design resolves the previous single-controller conflicts:

- Mega #1 owns bill sorting and all bill dispenser motor/sensor pins.
- Mega #2 owns coin acceptance, coin dispensing, the coin sorter servo, and security pins.
- `D7` is a bill dispenser signal on Mega #1 and the coin sorter servo signal on Mega #2.
- `D24` is a bill dispenser signal on Mega #1 and the active-HIGH coin acceptor enable signal on Mega #2.
- Shared pin numbers across controllers are expected and do not indicate a wiring conflict.

---

## 9.6 Wiring Color Code Standard

| Color | Purpose |
| ----- | ------- |
| Red | +5V power |
| Yellow | +12V power |
| Black | Ground |
| Orange | +3.3V power |
| Green | Signal input |
| Blue | Signal output |
| White | Serial TX |
| Gray | Serial RX |
| Purple | PWM signal |
| Brown | Motor A+ |
| Pink | Motor A- |

---

## 9.7 Connector Reference

| Connection | Recommended Connector |
| ---------- | --------------------- |
| Main 12V/5V | XT60 or Anderson Powerpole |
| Distribution | Screw terminals or Wago connectors |
| L298N to motor | JST XH 2-pin |
| L298N to Arduino | Dupont headers or JST XH |
| IR sensors | JST XH 3-pin |
| Shock sensors | JST XH 3-pin |
| Servos | Standard 3-pin servo headers |
| Arduino to drivers | Ribbon cable with IDC connectors |

---

_Document 9 of 10 - Coinnect System Architecture_
