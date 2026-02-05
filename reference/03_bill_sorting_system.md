# Coinnect System Architecture

## 03 - Bill Sorting System

**Document Version:** 2.0  
**Date:** February 2026  
**Controller:** Arduino Mega #1 (Bill Controller) via `/dev/ttyUSB0`

---

## 3.1 Overview

The bill sorting system uses a single stepper motor with a linear rail mechanism to position the storage compartments beneath the bill acceptor exit point. After the Raspberry Pi identifies the bill denomination, it sends a command to the Arduino to move the correct storage slot into position.

**Components:**

- 1x NEMA 17 Stepper Motor (1.8° step angle)
- 1x A4988 Stepper Driver
- 1x Limit Switch (homing)
- 8x Storage Compartments
- Linear Rail + GT2 Belt + Pulleys

**Storage Layout:**
| Slot | Denomination | Currency |
|------|--------------|----------|
| 1 | ₱20 | PHP |
| 2 | ₱50 | PHP |
| 3 | ₱100 | PHP |
| 4 | ₱200 | PHP |
| 5 | ₱500 | PHP |
| 6 | ₱1000 | PHP |
| 7 | All USD ($10, $50, $100) | USD |
| 8 | All EUR (€5, €10, €20) | EUR |

---

## 3.2 System Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        BILL SORTING SYSTEM (Linear Rail)                         │
└─────────────────────────────────────────────────────────────────────────────────┘

                           FROM BILL ACCEPTOR
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         BILL DROP ZONE                                   │
    │                              ║                                           │
    │                              ║                                           │
    │                              ▼                                           │
    │  ┌───────────────────────────────────────────────────────────────────┐  │
    │  │                     LINEAR RAIL MECHANISM                          │  │
    │  │                                                                    │  │
    │  │   LIMIT                                              STEPPER       │  │
    │  │   SWITCH                                              MOTOR        │  │
    │  │     │                                                   │          │  │
    │  │     ▼                                                   ▼          │  │
    │  │   ┌─┐  ┌──────────────────────────────────────────┐  ┌─────┐      │  │
    │  │   │█│  │            GT2 TIMING BELT               │  │NEMA │      │  │
    │  │   └─┘  │  ◄════════════════════════════════════►  │  │ 17  │      │  │
    │  │        └──────────────────────────────────────────┘  └─────┘      │  │
    │  │                          │                                         │  │
    │  │                          │ (Belt attached to carriage)             │  │
    │  │                          ▼                                         │  │
    │  │   ╔═══════════════════════════════════════════════════════════╗   │  │
    │  │   ║                    STORAGE CARRIAGE                        ║   │  │
    │  │   ║  ┌────┬────┬────┬────┬────┬────┬────┬────┐                ║   │  │
    │  │   ║  │ S1 │ S2 │ S3 │ S4 │ S5 │ S6 │ S7 │ S8 │                ║   │  │
    │  │   ║  │₱20 │₱50 │₱100│₱200│₱500│₱1K │USD │EUR │                ║   │  │
    │  │   ║  │    │    │    │    │    │    │    │    │                ║   │  │
    │  │   ║  └────┴────┴────┴────┴────┴────┴────┴────┘                ║   │  │
    │  │   ╚═══════════════════════════════════════════════════════════╝   │  │
    │  │                                                                    │  │
    │  │   ◄─────────────────── LINEAR GUIDE RAIL ──────────────────────►  │  │
    │  │                                                                    │  │
    │  └────────────────────────────────────────────────────────────────────┘  │
    │                                                                          │
    └──────────────────────────────────────────────────────────────────────────┘


    SIDE VIEW:
    ══════════

    From Acceptor
          │
          ▼
       ┌──────┐
       │ Bill │
       │ Drop │
       └──┬───┘
          │
          ▼
    ┌───────────┐
    │  Storage  │
    │   Slot    │
    │ (Current) │
    └───────────┘
          │
          │ ◄── Carriage moves left/right
          │     to align correct slot
    ══════╧══════════════════════
         LINEAR RAIL
```

---

## 3.3 Mechanical Specifications

### 3.3.1 Dimensions and Calculations

```
STORAGE COMPARTMENT SIZING:
───────────────────────────

PHP Bill Dimensions: 160mm × 66mm (standard)
USD Bill Dimensions: 156mm × 66mm
EUR Bill Dimensions: 120-160mm × 62-82mm (varies)

Compartment Internal Width:  70mm (allows for bill thickness stack)
Compartment Internal Length: 170mm (accommodates all bill sizes)
Compartment Internal Depth:  100mm (holds ~500 bills)

Wall Thickness: 3mm (acrylic or sheet metal)

Total Compartment Width: 70mm + 3mm (wall) = 73mm per slot
                         (except last slot which has wall on both sides)

TOTAL CARRIAGE WIDTH:
─────────────────────
8 compartments × 73mm = 584mm
Plus end wall: 584mm + 3mm = 587mm ≈ 600mm

RAIL LENGTH:
────────────
Travel needed: 7 slot transitions × 73mm = 511mm
Home position buffer: 50mm
End buffer: 50mm
Total rail length: 511mm + 100mm = ~620mm minimum

Recommended rail length: 700mm (allows for adjustment)
```

### 3.3.2 Stepper Motor Specifications

```
RECOMMENDED: NEMA 17 STEPPER MOTOR
─────────────────────────────────────

Model: 17HS4401 or similar
Step Angle: 1.8° (200 steps/revolution)
Holding Torque: 40-45 N·cm (0.4-0.45 Nm)
Rated Current: 1.5-1.7A per phase
Voltage: 12V (with appropriate driver)

PULLEY AND BELT:
────────────────
GT2 Pulley: 20 teeth
GT2 Belt Pitch: 2mm
Pulley Circumference: 20 × 2mm = 40mm per revolution

MOVEMENT CALCULATION:
─────────────────────
Steps per revolution: 200 (full step)
                      400 (half step)
                      1600 (1/8 microstepping)
                      3200 (1/16 microstepping)

Distance per step (1/16 microstepping):
= 40mm / 3200 steps = 0.0125mm per step

Steps per compartment (73mm):
= 73mm / 0.0125mm = 5840 steps

SPEED CALCULATION:
──────────────────
Target speed: 100mm/second
Steps per second: 100mm / 0.0125mm = 8000 steps/second
Stepper frequency: 8000 Hz (8 kHz)
```

### 3.3.3 Position Table

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    STORAGE SLOT POSITIONS (from Home)                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Slot  │  Denomination  │  Distance (mm)  │  Steps (1/16)  │  Steps (1/8)      │
├────────┼────────────────┼─────────────────┼────────────────┼───────────────────┤
│  HOME  │  Limit Switch  │  0              │  0             │  0                │
│  1     │  ₱20           │  36.5*          │  2920          │  1460             │
│  2     │  ₱50           │  109.5          │  8760          │  4380             │
│  3     │  ₱100          │  182.5          │  14600         │  7300             │
│  4     │  ₱200          │  255.5          │  20440         │  10220            │
│  5     │  ₱500          │  328.5          │  26280         │  13140            │
│  6     │  ₱1000         │  401.5          │  32120         │  16060            │
│  7     │  USD           │  474.5          │  37960         │  18980            │
│  8     │  EUR           │  547.5          │  43800         │  21900            │
└────────┴────────────────┴─────────────────┴────────────────┴───────────────────┘

* First slot position = half compartment width (36.5mm) to center
  Subsequent slots = previous position + 73mm
```

---

## 3.4 Wiring Diagram

### 3.4.1 A4988 Stepper Driver Connection

```
                          A4988 STEPPER DRIVER
                       ┌─────────────────────────┐
                       │         A4988           │
                       │                         │
         +12V (ATX) ───┤ VMOT            VDD ├─── +5V (ATX or Arduino)
         GND ──────────┤ GND             GND ├─── GND
                       │                         │
   NEMA 17 Coil A+ ────┤ 1A            STEP ├◄── Arduino D2
   NEMA 17 Coil A- ────┤ 1B             DIR ├◄── Arduino D3
   NEMA 17 Coil B+ ────┤ 2A          ENABLE ├◄── Arduino D4 (Active LOW)
   NEMA 17 Coil B- ────┤ 2B                 │
                       │                         │
                       │      MS1  MS2  MS3      │
                       │       │    │    │       │
                       │      +5V +5V +5V        │ (1/16 microstepping)
                       │                         │
                       │   ┌───────────────┐     │
                       │   │ Current Adj   │     │ Set to motor rating
                       │   │     Pot       │     │ Vref = Imax × 8 × Rsense
                       │   └───────────────┘     │
                       │                         │
                       └─────────────────────────┘

    CRITICAL: Add 100µF electrolytic capacitor between VMOT and GND
              Close to the driver to prevent voltage spikes!

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  MICROSTEPPING CONFIGURATION (MS1, MS2, MS3)                            │
    ├───────────┬───────────┬───────────┬─────────────────────────────────────┤
    │   MS1     │   MS2     │   MS3     │   Resolution                        │
    ├───────────┼───────────┼───────────┼─────────────────────────────────────┤
    │   LOW     │   LOW     │   LOW     │   Full step (200 steps/rev)         │
    │   HIGH    │   LOW     │   LOW     │   Half step (400 steps/rev)         │
    │   LOW     │   HIGH    │   LOW     │   1/4 step (800 steps/rev)          │
    │   HIGH    │   HIGH    │   LOW     │   1/8 step (1600 steps/rev)         │
    │   HIGH    │   HIGH    │   HIGH    │   1/16 step (3200 steps/rev)        │
    └───────────┴───────────┴───────────┴─────────────────────────────────────┘

    RECOMMENDED: 1/16 microstepping for smooth, quiet operation
```

### 3.4.2 NEMA 17 Stepper Motor Wiring

```
    NEMA 17 STEPPER MOTOR (4-wire bipolar)

    Common wire colors:

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  Wire Color    │  Connection    │  A4988 Pin                           │
    ├────────────────┼────────────────┼──────────────────────────────────────┤
    │  BLACK         │  Coil A+       │  1A                                  │
    │  GREEN         │  Coil A-       │  1B                                  │
    │  RED           │  Coil B+       │  2A                                  │
    │  BLUE          │  Coil B-       │  2B                                  │
    └────────────────┴────────────────┴──────────────────────────────────────┘

    Note: Wire colors vary by manufacturer. Use multimeter to identify coil pairs.
    Coil pairs will show continuity (low resistance ~1-3Ω between them).

    IDENTIFYING COIL PAIRS:
    ───────────────────────
    1. Measure resistance between all wire combinations
    2. Two wires with ~1-3Ω resistance = one coil
    3. The other two wires = second coil
    4. If motor vibrates but doesn't turn, swap ONE pair of wires
```

### 3.4.3 Limit Switch Connection

```
    LIMIT SWITCH (Normally Open - NO)

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                                                                          │
    │     Mechanical Limit Switch                     Arduino Connection       │
    │                                                                          │
    │        ┌─────────┐                                                       │
    │        │   NO    │───────────────────────────────► Arduino D5           │
    │        │  ┌──┐   │                                 (INPUT_PULLUP)        │
    │        │  │  │   │                                                       │
    │    ────┤  └──┘   │                                                       │
    │        │   COM   │───────────────────────────────► GND                   │
    │        └─────────┘                                                       │
    │                                                                          │
    │     When switch is pressed:                                              │
    │     - NO connects to COM                                                 │
    │     - Arduino pin reads LOW (0)                                          │
    │                                                                          │
    │     When switch is open:                                                 │
    │     - Internal pull-up keeps pin HIGH (1)                                │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘

    MOUNTING POSITION:
    ──────────────────
    Mount at the HOME position (leftmost or rightmost end of travel).
    The carriage should trigger the switch before hitting a hard stop.
```

---

## 3.5 Complete Wiring Schematic

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    BILL SORTING SYSTEM - COMPLETE WIRING                         │
└─────────────────────────────────────────────────────────────────────────────────┘

                        +12V (ATX)                    +5V (ATX)
                           │                            │
                           │         ┌──────────────────┤
                           │         │                  │
                      ┌────┴────┐    │                  │
                      │  100µF  │    │                  │
                      │   CAP   │    │                  │
                      └────┬────┘    │                  │
                           │         │                  │
                      ┌────┴─────────┴────┐             │
                      │      A4988        │             │
                      │                   │             │
    NEMA 17 ──────────┤ 1A           VMOT├─────────────┤
    (BLACK)           │                   │             │
                      │ 1B            GND├─────────────┼───┐
    NEMA 17 ──────────┤                   │             │   │
    (GREEN)           │ 2A            VDD├─────────────┘   │
                      │                   │                 │
    NEMA 17 ──────────┤ 2B            GND├─────────────────┤
    (RED)             │                   │                 │
                      │              STEP├◄────────────────┼─── Arduino D2
    NEMA 17 ──────────┤                   │                 │
    (BLUE)            │               DIR├◄────────────────┼─── Arduino D3
                      │                   │                 │
                      │            ENABLE├◄────────────────┼─── Arduino D4
                      │                   │                 │
                      │     MS1 MS2 MS3   │                 │
                      │      │   │   │    │                 │
                      └──────┼───┼───┼────┘                 │
                             │   │   │                      │
                            +5V +5V +5V                     │
                                                            │
    ════════════════════════════════════════════════════════╪══════════════════
                              GND BUS                       │
                                                            │
    ┌───────────────────────────────────────────────────────┴──────────────────┐
    │                                                                          │
    │                            ARDUINO MEGA 2560                             │
    │                                                                          │
    │   ┌──────────────────────────────────────────────────────────────────┐   │
    │   │  D2  ──────► A4988 STEP                                          │   │
    │   │  D3  ──────► A4988 DIR                                           │   │
    │   │  D4  ──────► A4988 ENABLE (Active LOW - set HIGH to disable)     │   │
    │   │  D5  ◄────── Limit Switch (with INPUT_PULLUP)                    │   │
    │   │                                                                   │   │
    │   │  GND ──────► Common Ground                                        │   │
    │   └──────────────────────────────────────────────────────────────────┘   │
    │                                                                          │
    └──────────────────────────────────────────────────────────────────────────┘
```

---

## 3.6 Arduino Control Code

### 3.6.1 Pin Definitions and Setup

```cpp
// Bill Sorting System - Arduino Code

// Pin Definitions
#define STEP_PIN    2
#define DIR_PIN     3
#define ENABLE_PIN  4
#define LIMIT_PIN   5

// Motor Configuration
#define STEPS_PER_REV     3200    // 1/16 microstepping
#define MM_PER_REV        40.0    // GT2-20T pulley circumference
#define STEPS_PER_MM      (STEPS_PER_REV / MM_PER_REV)  // 80 steps/mm
#define SLOT_WIDTH_MM     73.0
#define STEPS_PER_SLOT    (long)(SLOT_WIDTH_MM * STEPS_PER_MM)  // 5840 steps

// Slot positions in steps from home
const long SLOT_POSITIONS[8] = {
    2920,   // Slot 1: PHP 20
    8760,   // Slot 2: PHP 50
    14600,  // Slot 3: PHP 100
    20440,  // Slot 4: PHP 200
    26280,  // Slot 5: PHP 500
    32120,  // Slot 6: PHP 1000
    37960,  // Slot 7: USD
    43800   // Slot 8: EUR
};

// Current position tracking
volatile long currentPosition = 0;
bool isHomed = false;

void setup() {
    // Configure pins
    pinMode(STEP_PIN, OUTPUT);
    pinMode(DIR_PIN, OUTPUT);
    pinMode(ENABLE_PIN, OUTPUT);
    pinMode(LIMIT_PIN, INPUT_PULLUP);

    // Disable motor initially
    digitalWrite(ENABLE_PIN, HIGH);

    Serial.begin(115200);
    Serial.println("Bill Sorting System Ready");
}
```

### 3.6.2 Homing Function

```cpp
void homeCarriage() {
    Serial.println("Homing...");

    // Enable motor
    digitalWrite(ENABLE_PIN, LOW);

    // Set direction toward home (limit switch)
    digitalWrite(DIR_PIN, LOW);  // Adjust based on your wiring

    // Move until limit switch is triggered
    while (digitalRead(LIMIT_PIN) == HIGH) {
        // Step
        digitalWrite(STEP_PIN, HIGH);
        delayMicroseconds(200);  // 2500 Hz = ~31mm/s
        digitalWrite(STEP_PIN, LOW);
        delayMicroseconds(200);
    }

    // Back off slightly from switch
    digitalWrite(DIR_PIN, HIGH);
    for (int i = 0; i < 800; i++) {  // ~10mm
        digitalWrite(STEP_PIN, HIGH);
        delayMicroseconds(200);
        digitalWrite(STEP_PIN, LOW);
        delayMicroseconds(200);
    }

    // Set position to zero
    currentPosition = 0;
    isHomed = true;

    Serial.println("Homing complete");
}
```

### 3.6.3 Movement Function

```cpp
void moveToSlot(int slotNumber) {
    if (!isHomed) {
        Serial.println("ERROR: Not homed");
        return;
    }

    if (slotNumber < 1 || slotNumber > 8) {
        Serial.println("ERROR: Invalid slot number");
        return;
    }

    long targetPosition = SLOT_POSITIONS[slotNumber - 1];
    long stepsToMove = targetPosition - currentPosition;

    Serial.print("Moving to slot ");
    Serial.print(slotNumber);
    Serial.print(" (");
    Serial.print(stepsToMove);
    Serial.println(" steps)");

    // Enable motor
    digitalWrite(ENABLE_PIN, LOW);

    // Set direction
    if (stepsToMove > 0) {
        digitalWrite(DIR_PIN, HIGH);  // Forward
    } else {
        digitalWrite(DIR_PIN, LOW);   // Backward
        stepsToMove = -stepsToMove;
    }

    // Acceleration parameters
    int minDelay = 100;   // Maximum speed (microseconds between steps)
    int maxDelay = 500;   // Starting speed
    int accelSteps = 1000; // Steps to accelerate

    // Move with acceleration/deceleration
    for (long i = 0; i < stepsToMove; i++) {
        int stepDelay;

        // Acceleration phase
        if (i < accelSteps) {
            stepDelay = map(i, 0, accelSteps, maxDelay, minDelay);
        }
        // Deceleration phase
        else if (i > stepsToMove - accelSteps) {
            stepDelay = map(i, stepsToMove - accelSteps, stepsToMove, minDelay, maxDelay);
        }
        // Constant speed phase
        else {
            stepDelay = minDelay;
        }

        // Step pulse
        digitalWrite(STEP_PIN, HIGH);
        delayMicroseconds(stepDelay);
        digitalWrite(STEP_PIN, LOW);
        delayMicroseconds(stepDelay);

        // Update position
        if (digitalRead(DIR_PIN) == HIGH) {
            currentPosition++;
        } else {
            currentPosition--;
        }
    }

    // Disable motor to save power (optional - remove if holding torque needed)
    // digitalWrite(ENABLE_PIN, HIGH);

    Serial.println("Move complete");
}
```

### 3.6.4 Slot Mapping Function

```cpp
int denominationToSlot(String denom) {
    if (denom == "PHP_20")   return 1;
    if (denom == "PHP_50")   return 2;
    if (denom == "PHP_100")  return 3;
    if (denom == "PHP_200")  return 4;
    if (denom == "PHP_500")  return 5;
    if (denom == "PHP_1000") return 6;
    if (denom == "USD_10" || denom == "USD_50" || denom == "USD_100") return 7;
    if (denom == "EUR_5" || denom == "EUR_10" || denom == "EUR_20")   return 8;
    return -1;  // Unknown denomination
}
```

---

## 3.7 Integration with RPi

### 3.7.1 Serial Command Format

```
COMMAND FROM RPI:
{"cmd":"SORT","denom":"PHP_100"}

RESPONSE FROM ARDUINO:
{"status":"READY"}        // Sorter in position
{"status":"ERROR","code":"NOT_HOMED"}
{"status":"ERROR","code":"INVALID_DENOM"}
```

### 3.7.2 Command Handler

```cpp
void handleSerialCommand() {
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n');

        // Parse JSON (simple parser for this use case)
        if (command.indexOf("SORT") > 0) {
            // Extract denomination
            int denomStart = command.indexOf("denom") + 8;
            int denomEnd = command.indexOf("\"", denomStart);
            String denom = command.substring(denomStart, denomEnd);

            int slot = denominationToSlot(denom);

            if (slot > 0) {
                moveToSlot(slot);
                Serial.println("{\"status\":\"READY\"}");
            } else {
                Serial.println("{\"status\":\"ERROR\",\"code\":\"INVALID_DENOM\"}");
            }
        }
        else if (command.indexOf("HOME") > 0) {
            homeCarriage();
            Serial.println("{\"status\":\"OK\"}");
        }
        else if (command.indexOf("STATUS") > 0) {
            Serial.print("{\"position\":");
            Serial.print(currentPosition);
            Serial.print(",\"homed\":");
            Serial.print(isHomed ? "true" : "false");
            Serial.println("}");
        }
    }
}

void loop() {
    handleSerialCommand();
}
```

---

## 3.8 Timing Specifications

| Operation             | Duration     | Notes                        |
| --------------------- | ------------ | ---------------------------- |
| Homing                | 5-10 seconds | Depends on starting position |
| Move to adjacent slot | ~0.7 seconds | 73mm at 100mm/s              |
| Move across all slots | ~5.5 seconds | 547mm at 100mm/s             |
| Step pulse width      | 100µs min    | A4988 requirement            |

---

_Document 3 of 10 - Coinnect System Architecture_
