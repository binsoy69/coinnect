# Coinnect System Architecture

## 07 - Power Distribution

**Document Version:** 2.0  
**Date:** February 2026  
**Power Source:** ATX Power Supply

---

## 7.1 Overview

The Coinnect system uses an ATX (computer) power supply as the main power source. ATX PSUs are ideal for this application because they provide multiple regulated voltage rails, built-in protection circuits, and are readily available.

**ATX PSU Advantages:**

- Multiple voltage rails (+12V, +5V, +3.3V)
- High current capacity
- Built-in overcurrent protection
- Built-in overvoltage protection
- Efficient and reliable
- Standardized connectors
- Cost-effective

---

## 7.2 ATX Power Supply Basics

### 7.2.1 ATX Connector Pinout (24-Pin Main)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       ATX 24-PIN MAIN CONNECTOR                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

    CONNECTOR VIEW (Looking at pins from wire side):

           ┌─────────────────────────────────────────────────┐
           │  12   11   10   9    8    7    6    5    4    3    2    1  │
           │  ●    ●    ●    ●    ●    ●    ●    ●    ●    ●    ●    ●  │
           │  ●    ●    ●    ●    ●    ●    ●    ●    ●    ●    ●    ●  │
           │  24   23   22   21   20   19   18   17   16   15   14   13 │
           └─────────────────────────────────────────────────┘

    PIN ASSIGNMENT:
    ════════════════

    ┌──────┬─────────────┬─────────────────────────────────────────────────────┐
    │ Pin  │  Color      │  Function                                           │
    ├──────┼─────────────┼─────────────────────────────────────────────────────┤
    │  1   │  Orange     │  +3.3V                                              │
    │  2   │  Orange     │  +3.3V                                              │
    │  3   │  Black      │  GND                                                │
    │  4   │  Red        │  +5V                                                │
    │  5   │  Black      │  GND                                                │
    │  6   │  Red        │  +5V                                                │
    │  7   │  Black      │  GND                                                │
    │  8   │  Gray       │  PWR_OK (Power Good signal)                         │
    │  9   │  Purple     │  +5V_SB (Standby - always on)                       │
    │  10  │  Yellow     │  +12V                                               │
    │  11  │  Yellow     │  +12V                                               │
    │  12  │  Orange     │  +3.3V                                              │
    │  13  │  Orange     │  +3.3V                                              │
    │  14  │  Blue       │  -12V (rarely used, low current)                    │
    │  15  │  Black      │  GND                                                │
    │  16  │  GREEN      │  PS_ON (Power On - connect to GND to turn on)       │
    │  17  │  Black      │  GND                                                │
    │  18  │  Black      │  GND                                                │
    │  19  │  Black      │  GND                                                │
    │  20  │  White      │  -5V (often not present on newer PSUs)              │
    │  21  │  Red        │  +5V                                                │
    │  22  │  Red        │  +5V                                                │
    │  23  │  Red        │  +5V                                                │
    │  24  │  Black      │  GND                                                │
    └──────┴─────────────┴─────────────────────────────────────────────────────┘


    KEY WIRES FOR COINNECT:
    ═══════════════════════

    YELLOW  (+12V) ────► DC Motors, Stepper, Solenoid, Coin Acceptor
    RED     (+5V)  ────► Raspberry Pi, Arduino, Servos, Sensors, LEDs
    ORANGE  (+3.3V)────► (Optional) Some sensors
    BLACK   (GND)  ────► Common Ground for ALL components
    GREEN   (PS_ON)────► Connect to BLACK (GND) to turn PSU ON
```

### 7.2.2 Turning On ATX PSU Without Motherboard

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       ATX PSU POWER-ON METHOD                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

    The ATX PSU requires the PS_ON signal (Green wire) to be connected
    to GND (Black wire) to turn on.

    METHOD 1: Permanent Jumper (Simple)
    ════════════════════════════════════

    Simply connect Green wire to any Black wire:

    ┌─────────────────────────────────────┐
    │        ATX 24-PIN CONNECTOR         │
    │                                     │
    │   GREEN (Pin 16) ─────┐             │
    │                       │ Wire/Jumper │
    │   BLACK (Pin 17) ─────┘             │
    │                                     │
    └─────────────────────────────────────┘

    PSU turns ON when AC power is connected.
    PSU turns OFF when AC power is disconnected.


    METHOD 2: Toggle Switch (Recommended)
    ═════════════════════════════════════

                    ┌─────────┐
    GREEN ──────────┤  SWITCH ├────────── BLACK
                    │   ON/OFF│
                    └─────────┘

    Allows manual ON/OFF control without unplugging AC.
```

---

## 7.3 Power Requirements Analysis

### 7.3.1 Component Power Consumption

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       POWER CONSUMPTION TABLE                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

+12V RAIL COMPONENTS:
═════════════════════

┌─────────────────────────────┬─────────┬─────────┬─────────┬─────────────────────┐
│  Component                  │  Qty    │ Current │  Peak   │  Notes              │
│                             │         │ (each)  │  Total  │                     │
├─────────────────────────────┼─────────┼─────────┼─────────┼─────────────────────┤
│  DC Motors (Dispensers)     │  24     │  300mA  │  3.6A*  │  Max 4 running      │
│  DC Motor (Bill Acceptor)   │  1      │  500mA  │  0.5A   │                     │
│  NEMA 17 Stepper            │  1      │  1.5A   │  1.5A   │  Continuous when on │
│  Solenoid Lock              │  1      │  500mA  │  0.5A   │  Intermittent       │
│  Coin Acceptor              │  1      │  200mA  │  0.2A   │  Standby ~50mA      │
│  UV LED Strip               │  1      │  300mA  │  0.3A   │  Intermittent       │
│  White LED                  │  1      │  200mA  │  0.2A   │  Intermittent       │
├─────────────────────────────┼─────────┼─────────┼─────────┼─────────────────────┤
│  SUBTOTAL +12V              │         │         │  6.8A   │  *Typical: ~4A      │
└─────────────────────────────┴─────────┴─────────┴─────────┴─────────────────────┘

+5V RAIL COMPONENTS:
════════════════════

┌─────────────────────────────┬─────────┬─────────┬─────────┬─────────────────────┐
│  Component                  │  Qty    │ Current │  Peak   │  Notes              │
│                             │         │ (each)  │  Total  │                     │
├─────────────────────────────┼─────────┼─────────┼─────────┼─────────────────────┤
│  Raspberry Pi 4             │  1      │  3.0A   │  3.0A   │  Under load         │
│  Arduino Mega (x2)          │  2      │  200mA  │  0.4A   │  Via USB from Pi    │
│  Servo Motors (MG996R)      │  4      │  500mA  │  2.0A   │  Peak during move   │
│  L298N Logic (VCC)          │  13     │  10mA   │  0.13A  │  Driver logic       │
│  IR Sensors                 │  14     │  20mA   │  0.28A  │  Always on          │
│  Shock Sensors              │  2      │  15mA   │  0.03A  │                     │
│  LEDs (Indicators)          │  2      │  20mA   │  0.04A  │                     │
│  A4988 Driver (VDD)         │  1      │  10mA   │  0.01A  │  Logic supply       │
│  Relay Module               │  1      │  70mA   │  0.07A  │  When active        │
│  USB Camera                 │  1      │  500mA  │  0.5A   │  USB powered        │
├─────────────────────────────┼─────────┼─────────┼─────────┼─────────────────────┤
│  SUBTOTAL +5V               │         │         │  6.3A   │  Typical: ~4A       │
└─────────────────────────────┴─────────┴─────────┴─────────┴─────────────────────┘


POWER SUMMARY:
══════════════

┌───────────────────────────────────────────────────────────────────────────────┐
│  Rail    │  Peak Current  │  Peak Power   │  Typical Current  │  Typical Power │
├──────────┼────────────────┼───────────────┼───────────────────┼────────────────┤
│  +12V    │  6.8A          │  81.6W        │  4A               │  48W           │
│  +5V     │  6.3A          │  31.5W        │  4A               │  20W           │
├──────────┼────────────────┼───────────────┼───────────────────┼────────────────┤
│  TOTAL   │                │  113W (peak)  │                   │  68W (typical) │
└──────────┴────────────────┴───────────────┴───────────────────┴────────────────┘
```

### 7.3.2 Recommended PSU Specifications

```
    MINIMUM REQUIREMENTS:
    ═════════════════════

    Total Wattage:     300W (provides headroom)
    +12V Rail:         15A minimum (180W)
    +5V Rail:          10A minimum (50W)

    RECOMMENDED PSU: 400-500W ATX Power Supply
    - 80+ Bronze efficiency or better
    - Single +12V rail preferred
    - Quality brand (EVGA, Corsair, Seasonic, etc.)
```

---

## 7.4 Power Distribution Wiring

### 7.4.1 Star Grounding Topology

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       STAR GROUNDING TOPOLOGY                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

    Star grounding prevents ground loops and reduces electrical noise.
    All grounds connect to a single central point.

                                    ATX PSU
                                 ┌───────────┐
                                 │    GND ───┼───┐
                                 │   (Black) │   │
                                 └───────────┘   │
                                                 │
                              ┌──────────────────┼──────────────────┐
                              │        CENTRAL GROUND BUS          │
                              │         (Copper Bus Bar)           │
                              └──────────────────┼──────────────────┘
                                                 │
                 ┌───────────────┬───────────────┼───────────────┬───────────────┐
                 │               │               │               │               │
            ┌────┴────┐    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
            │   RPi   │    │ Arduino │    │ Motors  │    │ Servos  │    │ Sensors │
            │   GND   │    │   GND   │    │   GND   │    │   GND   │    │   GND   │
            └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

---

## 7.5 Wire Gauge Selection

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       WIRE GAUGE RECOMMENDATIONS                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────┬────────────────┬────────────────────────────────────┐
│  Application              │  AWG           │  Notes                             │
├───────────────────────────┼────────────────┼────────────────────────────────────┤
│  Main +12V from PSU       │  14-16 AWG     │  High current trunk line           │
│  Main +5V from PSU        │  16-18 AWG     │  Moderate current trunk            │
│  Main GND from PSU        │  14-16 AWG     │  Must handle combined return       │
│  To L298N (12V)           │  18-20 AWG     │  Per driver                        │
│  Motor wires              │  20-22 AWG     │  Short runs OK                     │
│  To Raspberry Pi          │  18-20 AWG     │  3A capability                     │
│  Servo power              │  20-22 AWG     │  Per servo                         │
│  Sensor wiring            │  22-26 AWG     │  Low current signals               │
│  Signal wires             │  22-26 AWG     │  Digital signals                   │
└───────────────────────────┴────────────────┴────────────────────────────────────┘
```

---

## 7.6 Protection Circuits

### 7.6.1 Fuse Protection

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       FUSE PROTECTION SCHEME                                     │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┬────────────┬──────────────────────────────────────────────────┐
│  Fuse           │  Rating    │  Protected Circuit                               │
├─────────────────┼────────────┼──────────────────────────────────────────────────┤
│  F1             │  10A       │  +12V Main                                       │
│  F2             │  3A        │  +12V Motors Branch 1                            │
│  F3             │  3A        │  +12V Motors Branch 2                            │
│  F4             │  2A        │  +12V Stepper                                    │
│  F5             │  10A       │  +5V Main                                        │
│  F6             │  5A        │  +5V RPi + Logic                                 │
│  F7             │  3A        │  +5V Servos                                      │
└─────────────────┴────────────┴──────────────────────────────────────────────────┘
```

### 7.6.2 Capacitor Placement

```
    AT EACH L298N DRIVER:           AT STEPPER DRIVER (A4988):
    ═════════════════════           ══════════════════════════

         +12V                            +12V (VMOT)
          │                               │
     ┌────┴────┐                     ┌────┴────┐
     │  100µF  │  Electrolytic       │  100µF  │  CRITICAL!
     │  25V    │                     │  25V    │
     └────┬────┘                     └────┬────┘
          │                               │
     ┌────┴────┐                     ┌────┴────┐
     │  0.1µF  │  Ceramic            │  A4988  │
     │  (104)  │                     │  VMOT   │
     └────┬────┘                     └─────────┘
          │
     ┌────┴────┐
     │  L298N  │
     └─────────┘
```

---

## 7.7 Raspberry Pi Power Options

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       RASPBERRY PI POWER OPTIONS                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

    OPTION A: USB-C Power Delivery (Recommended)
    ═════════════════════════════════════════════

    Use a quality USB-C power supply or USB-C PD board from ATX 5V rail.


    OPTION B: GPIO Header Power (Use with Caution)
    ═══════════════════════════════════════════════

    Power via GPIO pins 2,4 (5V) and 6 (GND):

    WARNING: This bypasses the Pi's protection circuits!
             Voltage must be exactly 5.0-5.25V.


    OPTION C: Official Pi Power Supply (Safest)
    ════════════════════════════════════════════

    Use a separate official Raspberry Pi power supply.
    Requires separate AC outlet but guarantees correct voltage.
```

---

## 7.8 Power-On Sequence

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       RECOMMENDED POWER-ON SEQUENCE                              │
└─────────────────────────────────────────────────────────────────────────────────┘

    1. Connect AC power to ATX PSU (PSU in standby)

    2. Close PS_ON switch (or jumper Green to Black)
       - ATX PSU turns ON
       - +12V and +5V rails become active

    3. Raspberry Pi boots (automatic)
       - Loads OS
       - Starts control software
       - Initializes GPIO

    4. Arduino Mega boots (automatic via USB power from Pi)
       - Runs setup()
       - Initializes all pins
       - Homes sorting mechanism

    5. System ready for operation


    POWER-OFF SEQUENCE:
    ═══════════════════

    1. RPi sends shutdown command to Arduino
    2. RPi initiates shutdown (sudo shutdown -h now)
    3. Wait for Pi to fully power down (~10 seconds)
    4. Open PS_ON switch
    5. (Optional) Disconnect AC power
```

---

_Document 7 of 10 - Coinnect System Architecture_
