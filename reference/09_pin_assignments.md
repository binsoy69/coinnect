# Coinnect System Architecture

## 09 - Pin Assignments

**Document Version:** 2.0  
**Date:** February 2026

---

## 9.1 Raspberry Pi 4/5 GPIO Assignments

### 9.1.1 Bill Acceptor System (RPi-Controlled)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       RASPBERRY PI GPIO PINOUT                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

    RPi GPIO Header (40-pin)

                    3.3V  (1) (2)  5V
          (SDA1) GPIO2  (3) (4)  5V
         (SCL1) GPIO3  (5) (6)  GND
                GPIO4  (7) (8)  GPIO14 (TXD)
                  GND  (9) (10) GPIO15 (RXD)
               GPIO17 (11) (12) GPIO18 (PWM0)
               GPIO27 (13) (14) GND
               GPIO22 (15) (16) GPIO23
                 3.3V (17) (18) GPIO24
      (SPI_MOSI)GPIO10 (19) (20) GND
      (SPI_MISO) GPIO9 (21) (22) GPIO25
       (SPI_CLK)GPIO11 (23) (24) GPIO8 (CE0)
                  GND (25) (26) GPIO7 (CE1)
         (ID_SD) GPIO0 (27) (28) GPIO1 (ID_SC)
                GPIO5 (29) (30) GND
                GPIO6 (31) (32) GPIO12 (PWM0)
               GPIO13 (33) (34) GND
               GPIO19 (35) (36) GPIO16
               GPIO26 (37) (38) GPIO20
                  GND (39) (40) GPIO21
```

### 9.1.2 Bill Acceptor Pin Assignment Table

| GPIO   | Pin      | Function                 | Direction | Notes                   |
| ------ | -------- | ------------------------ | --------- | ----------------------- |
| GPIO17 | 11       | L298N IN1 (Motor Dir 1)  | Output    | Motor direction control |
| GPIO27 | 13       | L298N IN2 (Motor Dir 2)  | Output    | Motor direction control |
| GPIO22 | 15       | L298N ENA (PWM)          | Output    | Motor speed control     |
| GPIO5  | 29       | IR Sensor 1 (Bill Entry) | Input     | Pull-up enabled         |
| GPIO6  | 31       | IR Sensor 2 (Position)   | Input     | Pull-up enabled         |
| GPIO23 | 16       | UV LED Control           | Output    | Via MOSFET              |
| GPIO24 | 18       | White LED Control        | Output    | Via MOSFET              |
| 3.3V   | 1,17     | Sensor Power             | Power     | IR sensors VCC          |
| GND    | Multiple | Common Ground            | Ground    |                         |

### 9.1.3 RPi Peripheral Connections

| Interface | Device              | Notes                          |
| --------- | ------------------- | ------------------------------ |
| USB 3.0   | 1080p Camera        | Bill authentication            |
| USB 2.0   | Arduino Mega #1     | Bill Controller (/dev/ttyUSB0) |
| USB 2.0   | Arduino Mega #2     | Coin & Security (/dev/ttyACM0) |
| USB 2.0   | Thermal Printer     | Receipt printing               |
| HDMI      | Touchscreen Display | 10-15" display                 |
| USB       | Touchscreen Touch   | Touch input                    |

---

## 9.2 Arduino Mega Pin Assignments

The system uses **two Arduino Mega 2560 controllers** for optimal pin management and subsystem separation:

- **Arduino Mega #1 (Bill Controller):** Bill Sorting + Bill Dispensing
- **Arduino Mega #2 (Coin & Security Controller):** Coin System + Security System

---

## 9.2.1 Arduino Mega #1: Bill Controller

**Serial Port:** `/dev/ttyUSB0`  
**Subsystems:** Bill Sorting, Bill Dispensing

### Complete Pin Map - Arduino #1

DIGITAL PINS:
═════════════

┌──────┬───────────────────────────────────────────────────────────────────────────┐
│ Pin │ Function │
├──────┼───────────────────────────────────────────────────────────────────────────┤
│ 0 │ RX0 (Serial to RPi via USB) - RESERVED │
│ 1 │ TX0 (Serial to RPi via USB) - RESERVED │
│ 2 │ Stepper STEP (A4988) │
│ 3 │ Stepper DIR (A4988) │
│ 4 │ Stepper ENABLE (A4988) │
│ 5 │ Limit Switch (Sorter Home) │
│ 6 │ Servo 4 Signal (₱20 coin) - PWM │
│ 7 │ Dispenser 11 - IN1 (€10) │
│ 8 │ Dispenser 11 - IN2 (€10) │
│ 9 │ Dispenser 11 - IN3 (€10) │
│ 10 │ Dispenser 11 - IN4 (€10) │
│ 11 │ Dispenser 12 - IN1 (€20) │
│ 12 │ Dispenser 12 - IN2 (€20) │
│ 13 │ Dispenser 12 - IN3 (€20) │
│ 14 │ IR Sensor 9 (Dispenser $100) / TX3 │
│ 15 │ IR Sensor 10 (Dispenser €5) / RX3 │
│ 16 │ IR Sensor 11 (Dispenser €10) / TX2 │
│ 17 │ IR Sensor 12 (Dispenser €20) / RX2 │
│ 18 │ Coin Acceptor Pulse Input (INT5) │
│ 19 │ Shock Sensor A (INT4) │
│ 20 │ Shock Sensor B (INT3) │
│ 21 │ Solenoid Lock Relay │
│ 22 │ Dispenser 1 - IN1 (₱20) / LED Red │
│ 23 │ Dispenser 1 - IN2 (₱20) / LED Green │
│ 24 │ Dispenser 1 - IN3 (₱20) │
│ 25 │ Dispenser 1 - IN4 (₱20) │
│ 26 │ Dispenser 2 - IN1 (₱50) │
│ 27 │ Dispenser 2 - IN2 (₱50) │
│ 28 │ Dispenser 2 - IN3 (₱50) │
│ 29 │ Dispenser 2 - IN4 (₱50) │
│ 30 │ Dispenser 3 - IN1 (₱100) │
│ 31 │ Dispenser 3 - IN2 (₱100) │
│ 32 │ Dispenser 3 - IN3 (₱100) │
│ 33 │ Dispenser 3 - IN4 (₱100) │
│ 34 │ Dispenser 4 - IN1 (₱200) │
│ 35 │ Dispenser 4 - IN2 (₱200) │
│ 36 │ Dispenser 4 - IN3 (₱200) │
│ 37 │ Dispenser 4 - IN4 (₱200) │
│ 38 │ Dispenser 5 - IN1 (₱500) │
│ 39 │ Dispenser 5 - IN2 (₱500) │
│ 40 │ Dispenser 5 - IN3 (₱500) │
│ 41 │ Dispenser 5 - IN4 (₱500) │
│ 42 │ Dispenser 6 - IN1 (₱1000) │
│ 43 │ Dispenser 6 - IN2 (₱1000) │
│ 44 │ Dispenser 6 - IN3 (₱1000) / Servo 1 Signal (₱1) - PWM │
│ 45 │ Dispenser 6 - IN4 (₱1000) / Servo 2 Signal (₱5) - PWM │
│ 46 │ Dispenser 7 - IN1 ($10) / Servo 3 Signal (₱10) - PWM │
│ 47 │ Dispenser 7 - IN2 ($10) / Keypad Row 1 │
│ 48 │ Dispenser 7 - IN3 ($10) / Keypad Row 2 │
│ 49 │ Dispenser 7 - IN4 ($10) / Keypad Row 3 │
│ 50 │ Dispenser 8 - IN1 ($50) / Keypad Row 4 / SPI MISO │
│ 51 │ Dispenser 8 - IN2 ($50) / Keypad Col 1 / SPI MOSI │
│ 52 │ Dispenser 8 - IN3 ($50) / Keypad Col 2 / SPI SCK │
│ 53 │ Dispenser 8 - IN4 ($50) / Keypad Col 3 / SPI SS │
└──────┴───────────────────────────────────────────────────────────────────────────┘

ANALOG PINS (Used as Digital):
══════════════════════════════

┌──────┬───────────────────────────────────────────────────────────────────────────┐
│ Pin │ Function │
├──────┼───────────────────────────────────────────────────────────────────────────┤
│ A0 │ IR Sensor 1 (Dispenser ₱20) │
│ A1 │ IR Sensor 2 (Dispenser ₱50) │
│ A2 │ IR Sensor 3 (Dispenser ₱100) │
│ A3 │ IR Sensor 4 (Dispenser ₱200) │
│ A4 │ IR Sensor 5 (Dispenser ₱500) │
│ A5 │ IR Sensor 6 (Dispenser ₱1000) │
│ A6 │ IR Sensor 7 (Dispenser $10) │
│ A7 │ IR Sensor 8 (Dispenser $50) │
│ A8 │ Dispenser 9 - IN1 ($100) │
│ A9 │ Dispenser 9 - IN2 ($100) │
│ A10 │ Dispenser 9 - IN3 ($100) │
│ A11 │ Dispenser 9 - IN4 ($100) │
│ A12 │ Dispenser 10 - IN1 (€5) │
│ A13 │ Dispenser 10 - IN2 (€5) │
│ A14 │ Dispenser 10 - IN3 (€5) │
│ A15 │ Dispenser 10 - IN4 (€5) │
└──────┴───────────────────────────────────────────────────────────────────────────┘

```

---

## 9.3 Subsystem Pin Summary

### 9.3.1 Bill Sorting System

| Pin | Function | Type |
|-----|----------|------|
| D2 | A4988 STEP | Output |
| D3 | A4988 DIR | Output |
| D4 | A4988 ENABLE | Output (Active LOW) |
| D5 | Limit Switch | Input (PULLUP) |

### 9.3.2 Bill Dispensing System (12 Units)

**Motor Direction Pins (4 per unit):**

| Unit | Denom | IN1 | IN2 | IN3 | IN4 | IR Sensor |
|------|-------|-----|-----|-----|-----|-----------|
| 1 | ₱20 | D22 | D23 | D24 | D25 | A0 |
| 2 | ₱50 | D26 | D27 | D28 | D29 | A1 |
| 3 | ₱100 | D30 | D31 | D32 | D33 | A2 |
| 4 | ₱200 | D34 | D35 | D36 | D37 | A3 |
| 5 | ₱500 | D38 | D39 | D40 | D41 | A4 |
| 6 | ₱1000 | D42 | D43 | D44 | D45 | A5 |
| 7 | $10 | D46 | D47 | D48 | D49 | A6 |
| 8 | $50 | D50 | D51 | D52 | D53 | A7 |
| 9 | $100 | A8 | A9 | A10 | A11 | D14 |
| 10 | €5 | A12 | A13 | A14 | A15 | D15 |
| 11 | €10 | D7 | D8 | D9 | D10 | D16 |
| 12 | €20 | D11 | D12 | D13 | - | D17 |

**Note:** Unit 12 uses only 3 direction pins (simplified control)

### 9.3.3 Coin System

| Pin | Function | Type |
|-----|----------|------|
| D18 | Coin Acceptor Pulse | Input (INT5) |
| D44 | Servo 1 (₱1) | PWM Output |
| D45 | Servo 2 (₱5) | PWM Output |
| D46 | Servo 3 (₱10) | PWM Output |
| D6 | Servo 4 (₱20) | PWM Output |

### 9.3.4 Security System

| Pin | Function | Type |
|-----|----------|------|
| D19 | Shock Sensor A | Input (INT4) |
| D20 | Shock Sensor B | Input (INT3) |
| D21 | Solenoid Relay | Output |
| D22 | LED Red | Output |
| D23 | LED Green | Output |
| D47-D53 | Keypad (4 rows + 3 cols) | I/O |

---

## 9.4 Pin Conflicts - RESOLVED

### 9.4.1 Dual-Arduino Resolution

With the dual-Arduino architecture, **all previous pin conflicts are eliminated**:

```

┌─────────────────────────────────────────────────────────────────────────────────┐
│ PIN CONFLICT STATUS: ✓ ALL RESOLVED │
└─────────────────────────────────────────────────────────────────────────────────┘

ARDUINO MEGA #1 (Bill Controller):
══════════════════════════════════
• Bill Sorting: D2-D5 (4 pins)
• Bill Dispensing: D6-D53, A0-A15 (60 pins for 12 units)
• Total Used: 64 pins
• Available Pins: ~10 spare pins
• Conflicts: NONE

ARDUINO MEGA #2 (Coin & Security Controller):
═════════════════════════════════════════════
• Coin Acceptor: D18 (1 interrupt pin)
• Coin Dispensers: D6, D44-D46 (4 PWM pins for servos)
• Shock Sensors: D19-D20 (2 interrupt pins)
• Solenoid Lock: D21 (1 pin)
• LED Indicators: D22-D23 (2 pins)
• Keypad: D47-D53 (7 pins)
• Total Used: 17 pins
• Available Pins: ~55 spare pins
• Conflicts: NONE

PREVIOUS CONFLICTS (NOW RESOLVED):
──────────────────────────────────
✓ Servo/Dispenser overlap: Servos now on Arduino #2, Dispensers on Arduino #1
✓ Keypad/Dispenser overlap: Keypad now on Arduino #2, Dispensers on Arduino #1
✓ LED/Dispenser overlap: LEDs now on Arduino #2, Dispensers on Arduino #1
✓ SPI pin usage: No longer a concern with separate controllers

```

> **Note:** I/O expanders are no longer required for this design. The dual-Arduino approach provides a cleaner, more reliable solution.

- SDA: Pin 20
- SCL: Pin 21

```

---

## 9.5 Wiring Color Code Standard

```

┌─────────────────────────────────────────────────────────────────────────────────┐
│ RECOMMENDED WIRE COLOR CODE │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┬───────────────────────────────────────────────────────────┐
│ Color │ Purpose │
├─────────────────────┼───────────────────────────────────────────────────────────┤
│ RED │ +5V Power │
│ YELLOW │ +12V Power │
│ BLACK │ Ground (GND) │
│ ORANGE │ +3.3V Power │
│ GREEN │ Signal - Input │
│ BLUE │ Signal - Output │
│ WHITE │ Serial TX │
│ GRAY │ Serial RX │
│ PURPLE │ PWM Signals │
│ BROWN │ Motor A+ │
│ PINK │ Motor A- │
└─────────────────────┴───────────────────────────────────────────────────────────┘

```

---

## 9.6 Connector Reference

```

RECOMMENDED CONNECTORS:
═══════════════════════

Power Connections:

- Main 12V/5V: XT60 or Anderson PowerPole
- Distribution: Screw terminals or Wago connectors

Motor Connections:

- L298N to Motor: JST XH 2-pin
- L298N to Arduino: Dupont headers or JST XH

Sensor Connections:

- IR Sensors: JST XH 3-pin (VCC, GND, OUT)
- Shock Sensors: JST XH 3-pin

Servo Connections:

- Standard 3-pin servo headers

Signal Wires:

- Arduino to Drivers: Ribbon cable with IDC connectors
- Individual signals: Dupont jumpers

```

---

_Document 9 of 10 - Coinnect System Architecture_

```

```
