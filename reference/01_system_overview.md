# Coinnect System Architecture

## 01 - System Overview

**Document Version:** 2.0  
**Date:** February 2026  
**Project:** Coinnect - A Unified Kiosk for Multiple Financial Services

---

## 1.1 System Architecture Philosophy

The Coinnect kiosk uses a **hybrid controller architecture** with **dual Arduino Megas**:

- **Raspberry Pi 4/5**: Handles time-critical bill authentication (camera + ML), user interface, API communications, and thermal printing
- **Arduino Mega #1 (Bill Controller)**: Handles bill sorting and bill dispensing systems
- **Arduino Mega #2 (Coin & Security Controller)**: Handles coin acceptance, coin dispensing, and security components

This dual-Arduino design provides:

- **Clean subsystem separation** - Bill handling is independent from coin/security operations
- **No pin conflicts** - Each subsystem has dedicated pins without time-multiplexing
- **Parallel operation** - Can dispense bills AND coins simultaneously
- **Fault isolation** - Security system remains operational if bill system fails
- **Simplified firmware** - Each Arduino runs focused, single-purpose code

---

## 1.2 High-Level System Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              COINNECT SYSTEM ARCHITECTURE                        │
│                                    Version 2.0                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────────┐
                                    │   CLOUD/APIs    │
                                    │  • Exchange API │
                                    │  • Xendit       │
                                    │  • Maya API     │
                                    │  • Firebase     │
                                    └────────┬────────┘
                                             │ WiFi/Ethernet
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           RASPBERRY PI 4/5 (Main Controller)                     │
│                                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │  YOLO Models   │  │  UI Server     │  │  API Client    │  │  Hardware    │  │
│  │  • Auth Model  │  │  (Touchscreen) │  │  (HTTP/REST)   │  │  Control     │  │
│  │  • Denom Model │  │                │  │                │  │  (GPIO)      │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  └──────────────┘  │
│                                                                                  │
│  DIRECTLY CONNECTED TO RPI:                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │ • USB Camera (Bill Authentication)                                        │   │
│  │ • Bill Acceptor Motor (via L298N on GPIO)                                 │   │
│  │ • Bill Acceptor IR Sensors x2 (GPIO Input)                                │   │
│  │ • UV LED Strip (GPIO + MOSFET)                                            │   │
│  │ • White LED (GPIO + MOSFET)                                               │   │
│  │ • Touchscreen Display (HDMI + USB)                                        │   │
│  │ • Thermal Printer (USB)                                                   │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────┬─────────────────────────────┘
                                                    │
                                    ┌───────────────┴───────────────┐
                                    │                               │
                          USB Serial                       USB Serial
                         (/dev/ttyUSB0)                   (/dev/ttyACM0)
                          Baud: 115200                     Baud: 115200
                                    │                               │
                                    ▼                               ▼
┌───────────────────────────────────────────┐ ┌───────────────────────────────────────────┐
│      ARDUINO MEGA #1 (Bill Controller)    │ │   ARDUINO MEGA #2 (Coin & Security)       │
│                                           │ │                                           │
│  ┌─────────────────────────────────────┐  │ │  ┌─────────────────────────────────────┐  │
│  │ BILL DISPENSING SYSTEM              │  │ │  │ COIN SYSTEM                         │  │
│  │ • 12 Dispenser Units                │  │ │  │ • 1 Multi-Coin Acceptor (CH-926)    │  │
│  │ • 24 DC Motors (2 per unit)         │  │ │  │ • 4 Servo Motors                    │  │
│  │ • 12 L298N Drivers                  │  │ │  │   (₱1, ₱5, ₱10, ₱20)                │  │
│  │ • 12 IR Sensors                     │  │ │  └─────────────────────────────────────┘  │
│  └─────────────────────────────────────┘  │ │                                           │
│                                           │ │  ┌─────────────────────────────────────┐  │
│  ┌─────────────────────────────────────┐  │ │  │ SECURITY SYSTEM                     │  │
│  │ BILL SORTING SYSTEM                 │  │ │  │ • 2 Shock Sensors                   │  │
│  │ • 1 NEMA 17 Stepper Motor           │  │ │  │ • 1 Solenoid Lock + Relay           │  │
│  │ • 1 A4988 Driver                    │  │ │  │ • 1 Matrix Keypad (4x3)             │  │
│  │ • 1 Limit Switch (Homing)           │  │ │  │ • LED Indicators (Red/Green)        │  │
│  │ • 8 Storage Compartments            │  │ │  └─────────────────────────────────────┘  │
│  └─────────────────────────────────────┘  │ │                                           │
└───────────────────────────────────────────┘ └───────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ATX POWER SUPPLY                                    │
│                                                                                  │
│   +12V Rail ────► DC Motors, Stepper, Solenoid, Coin Acceptor                   │
│   +5V Rail  ────► Raspberry Pi, Arduino, Servos, Sensors, LEDs                  │
│   GND       ────► Common Ground (Star Topology)                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1.3 Bill Acceptance Flow (RPi-Controlled)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            BILL ACCEPTANCE SEQUENCE                              │
└─────────────────────────────────────────────────────────────────────────────────┘

     USER                          RASPBERRY PI                      ARDUINO
       │                                │                               │
       │  Insert Bill                   │                               │
       │ ─────────────────────────────► │                               │
       │                                │                               │
       │                     ┌──────────┴──────────┐                    │
       │                     │ IR Sensor 1 Detects │                    │
       │                     │ Bill Entry          │                    │
       │                     └──────────┬──────────┘                    │
       │                                │                               │
       │                     ┌──────────┴──────────┐                    │
       │                     │ Motor ON (Forward)  │                    │
       │                     │ Pull bill inward    │                    │
       │                     └──────────┬──────────┘                    │
       │                                │                               │
       │                     ┌──────────┴──────────┐                    │
       │                     │ IR Sensor 2 Detects │                    │
       │                     │ Bill in Position    │                    │
       │                     └──────────┬──────────┘                    │
       │                                │                               │
       │                     ┌──────────┴──────────┐                    │
       │                     │ Motor STOP          │                    │
       │                     │ UV LED ON           │                    │
       │                     └──────────┬──────────┘                    │
       │                                │                               │
       │                     ┌──────────┴──────────┐                    │
       │                     │ Camera Capture      │                    │
       │                     │ YOLO Authentication │                    │
       │                     └──────────┬──────────┘                    │
       │                                │                               │
       │                    ┌───────────┴───────────┐                   │
       │                    │                       │                   │
       │               GENUINE                 NOT GENUINE              │
       │                    │                       │                   │
       │                    ▼                       ▼                   │
       │         ┌──────────────────┐    ┌──────────────────┐          │
       │         │ UV LED OFF       │    │ UV LED OFF       │          │
       │         │ White LED ON     │    │ Motor REVERSE    │          │
       │         └────────┬─────────┘    │ Eject Bill       │          │
       │                  │              └──────────────────┘          │
       │                  ▼                       │                    │
       │         ┌──────────────────┐             │                    │
       │         │ Camera Capture   │             │                    │
       │         │ YOLO Denomination│             │                    │
       │         └────────┬─────────┘             │                    │
       │                  │                       │                    │
       │                  ▼                       │                    │
       │         ┌──────────────────┐             │                    │
       │         │ White LED OFF    │             │                    │
       │         └────────┬─────────┘             │                    │
       │                  │                       │                    │
       │                  │  Serial Command       │                    │
       │                  │  {"cmd":"SORT",       │                    │
       │                  │   "denom":"PHP_100"}  │                    │
       │                  │ ──────────────────────┼──────────────────► │
       │                  │                       │                    │
       │                  │                       │    ┌───────────────┴───────┐
       │                  │                       │    │ Move Sorter to Slot   │
       │                  │                       │    │ (Stepper Motor)       │
       │                  │                       │    └───────────────┬───────┘
       │                  │                       │                    │
       │                  │                       │    ┌───────────────┴───────┐
       │                  │  {"status":"READY"}   │    │ Send Ready Signal     │
       │                  │ ◄──────────────────────────┤                       │
       │                  │                       │    └───────────────────────┘
       │                  │                       │                    │
       │         ┌────────┴─────────┐             │                    │
       │         │ Motor ON (Fwd)   │             │                    │
       │         │ Move to Storage  │             │                    │
       │         └────────┬─────────┘             │                    │
       │                  │                       │                    │
       │         ┌────────┴─────────┐             │                    │
       │         │ Bill Stored      │             │                    │
       │         │ Update Balance   │             │                    │
       │         └────────┬─────────┘             │                    │
       │                  │                       │                    │
       │  Display Updated │                       │                    │
       │ ◄────────────────┘                       │                    │
       │                                          │                    │
```

---

## 1.4 Component Summary

| Subsystem       | Controller      | Components                                            |
| --------------- | --------------- | ----------------------------------------------------- |
| Bill Acceptor   | Raspberry Pi    | 1 DC Motor, 2 IR Sensors, 1 Camera, UV LED, White LED |
| Bill Sorting    | Arduino Mega #1 | 1 Stepper Motor, 1 A4988, 1 Limit Switch              |
| Bill Dispensing | Arduino Mega #1 | 24 DC Motors, 12 L298N, 12 IR Sensors                 |
| Coin Acceptor   | Arduino Mega #2 | 1 CH-926 Module                                       |
| Coin Dispensing | Arduino Mega #2 | 4 Servo Motors                                        |
| Security        | Arduino Mega #2 | 2 Shock Sensors, 1 Solenoid, 1 Keypad, LEDs           |
| User Interface  | Raspberry Pi    | Touchscreen (HDMI+USB)                                |
| Printing        | Raspberry Pi    | Thermal Printer (USB)                                 |
| Power           | -               | ATX Power Supply                                      |

---

## 1.5 Document Index

| Document                     | Description                                  |
| ---------------------------- | -------------------------------------------- |
| 01_system_overview.md        | This document - high-level architecture      |
| 02_bill_acceptor_system.md   | RPi GPIO connections, motor, sensors, camera |
| 03_bill_sorting_system.md    | Stepper motor, linear rail, storage layout   |
| 04_bill_dispensing_system.md | DC motors, L298N drivers, IR sensors         |
| 05_coin_system.md            | Coin acceptor module, servo dispensers       |
| 06_security_system.md        | Shock sensors, solenoid lock, keypad         |
| 07_power_distribution.md     | ATX PSU integration, wiring                  |
| 08_communication_protocol.md | RPi-Arduino serial protocol                  |
| 09_pin_assignments.md        | Complete GPIO/pin mapping                    |
| 10_bill_of_materials.md      | Component list with costs                    |

---

_Document 1 of 10 - Coinnect System Architecture_
