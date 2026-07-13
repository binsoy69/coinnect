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
| 7 | USD ($10, $50) | USD |
| 8 | EUR (€5, €10) | EUR |

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
│  Slot  │  Denomination  │  Steps (Actual Firmware Value)                           │
├────────┼────────────────┼─────────────────────────────────────────────────────────┤
│  1     │  ₱20           │  0 (Home alignment)                                     │
│  2     │  ₱50           │  30000                                                  │
│  3     │  ₱100          │  60000                                                  │
│  4     │  ₱200          │  90000                                                  │
│  5     │  ₱500          │  122500                                                 │
│  6     │  ₱1000         │  153500                                                 │
│  7     │  USD           │  187500                                                 │
│  8     │  EUR           │  219500                                                 │
└────────┴────────────────┴─────────────────────────────────────────────────────────┘

* Note: Actual step coordinates are calibrated and stored in firmware to align perfectly under the bill acceptor drop slot.
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
   NEMA 17 Coil A+ ────┤ 1A            STEP ├◄── Arduino D6
   NEMA 17 Coil A- ────┤ 1B             DIR ├◄── Arduino D7
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
                      │              STEP├◄────────────────┼─── Arduino D6
    NEMA 17 ──────────┤                   │                 │
    (GREEN)           │               DIR├◄────────────────┼─── Arduino D7
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
    │   │  D6  ──────► A4988 STEP                                          │   │
    │   │  D7  ──────► A4988 DIR                                           │   │
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
// Bill Sorting System - Arduino Code (uses AccelStepper library)
#include <Arduino.h>
#include <AccelStepper.h>

// Pin Definitions
#define STEP_PIN    6
#define DIR_PIN     7
#define ENABLE_PIN  4
#define LIMIT_PIN   5

// Motor Configuration
#define STEPS_PER_REV     3200    // 1/16 microstepping
#define MM_PER_REV        40.0    // GT2-20T pulley circumference
#define STEPS_PER_MM      (STEPS_PER_REV / MM_PER_REV)  // 80 steps/mm

// Motion Constraints
const float SORT_MAX_SPEED = 12000.0;
const float SORT_ACCELERATION = 30000.0;
const long HOME_SPEED_STEPS_PER_SEC = -7500; // Moving negative is the homing direction
const long HOME_BACKOFF_STEPS = 800;
const unsigned long HOME_TIMEOUT_MS = 60000;
const unsigned long SORT_TIMEOUT_MS = 60000;
const bool HOLD_SORTER_AFTER_MOVE = true;

// Slot positions in steps from home
const long SLOT_POSITIONS[8] = {
    0,      // Slot 1: PHP_20
    30000,  // Slot 2: PHP_50
    60000,  // Slot 3: PHP_100
    90000,  // Slot 4: PHP_200
    122500, // Slot 5: PHP_500
    153500, // Slot 6: PHP_1000
    187500, // Slot 7: USD
    219500  // Slot 8: EUR
};

AccelStepper sorter(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);
bool sorterHomed = false;
int currentSlot = 0;

void enableStepper() {
    digitalWrite(ENABLE_PIN, LOW);
}

void disableStepperIfAllowed() {
    if (!HOLD_SORTER_AFTER_MOVE) {
        digitalWrite(ENABLE_PIN, HIGH);
    }
}

bool limitTriggered() {
    // Require multiple consecutive LOW reads to filter EMI noise
    const uint8_t DEBOUNCE_COUNT = 5;
    for (uint8_t i = 0; i < DEBOUNCE_COUNT; i++) {
        if (digitalRead(LIMIT_PIN) != LOW) {
            return false;
        }
        delayMicroseconds(1000); // 1ms between reads
    }
    return true;
}

void setup() {
    pinMode(STEP_PIN, OUTPUT);
    pinMode(DIR_PIN, OUTPUT);
    pinMode(ENABLE_PIN, OUTPUT);
    pinMode(LIMIT_PIN, INPUT_PULLUP);

    // Disable motor initially
    digitalWrite(ENABLE_PIN, HIGH);

    sorter.setMaxSpeed(SORT_MAX_SPEED);
    sorter.setAcceleration(SORT_ACCELERATION);

    Serial.begin(115200);
}
```

### 3.6.2 Non-Blocking Homing and State Machine

To prevent blocking serial communication for up to 12s, the homing routine is non-blocking. It is driven by a state machine inside the main loop:

```cpp
enum SorterState {
  STATE_IDLE,
  STATE_HOMING_TO_LIMIT,
  STATE_HOMING_BACKOFF,
  STATE_SORTING_MOVE
};

static SorterState sorterState = STATE_IDLE;
static unsigned long sorterActionStartMs = 0;
static long sorterTargetPos = 0;
static long targetSlotAfterMove = 0;
static long asyncCommandId = -1;

void handleHome() {
  sorterHomeFailed = false;
  enableStepper();
  sorter.setMaxSpeed(abs(HOME_SPEED_STEPS_PER_SEC));
  sorter.setAcceleration(SORT_ACCELERATION);
  sorter.setSpeed(HOME_SPEED_STEPS_PER_SEC);

  sorterState = STATE_HOMING_TO_LIMIT;
  sorterActionStartMs = millis();
  asyncCommandId = currentCommandId;
}

void updateSorterStateMachine() {
  if (sorterState == STATE_IDLE) {
    return;
  }

  if (sorterState == STATE_HOMING_TO_LIMIT) {
    sorter.runSpeed();
    if (limitTriggered()) {
      sorter.stop();
      sorter.setCurrentPosition(0);
      sorter.moveTo(HOME_BACKOFF_STEPS);
      sorterState = STATE_HOMING_BACKOFF;
    } else if (millis() - sorterActionStartMs > HOME_TIMEOUT_MS) {
      sorter.stop();
      sorterHomed = false;
      sorterHomeFailed = true;
      currentSlot = 0;
      disableStepperIfAllowed();
      sorterState = STATE_IDLE;
      
      currentCommandId = asyncCommandId;
      sendError("TIMEOUT");
      currentCommandId = -1;
    }
  } 
  else if (sorterState == STATE_HOMING_BACKOFF) {
    sorter.run();
    if (sorter.distanceToGo() == 0) {
      sorter.setCurrentPosition(0);
      sorterHomed = true;
      sorterHomeFailed = false;
      currentSlot = 0;
      disableStepperIfAllowed();
      sorterState = STATE_IDLE;

      currentCommandId = asyncCommandId;
      StaticJsonDocument<96> doc;
      doc["status"] = "OK";
      doc["position"] = 0;
      sendDocument(doc);
      currentCommandId = -1;
    } else if (millis() - sorterActionStartMs > HOME_TIMEOUT_MS) {
      sorter.stop();
      sorterHomed = false;
      sorterHomeFailed = true;
      currentSlot = 0;
      disableStepperIfAllowed();
      sorterState = STATE_IDLE;

      currentCommandId = asyncCommandId;
      sendError("TIMEOUT");
      currentCommandId = -1;
    }
  }
}
```

### 3.6.3 Movement Function

```cpp
bool moveSorterToSlot(uint8_t slot) {
    if (!sorterHomed || slot < 1 || slot > 8) {
        return false;
    }

    const long targetPosition = SLOT_POSITIONS[slot - 1];
    const long currentPos = sorter.currentPosition();
    const long steps = targetPosition - currentPos;

    if (steps == 0) {
        currentSlot = slot;
        return true;
    }

    enableStepper();
    float speed = (steps > 0) ? SORT_MAX_SPEED : -SORT_MAX_SPEED;
    sorter.setMaxSpeed(SORT_MAX_SPEED);
    sorter.setSpeed(speed);

    const unsigned long startedAt = millis();
    while ((steps > 0 && sorter.currentPosition() < targetPosition) ||
           (steps < 0 && sorter.currentPosition() > targetPosition)) {
        sorter.runSpeed();
        if (millis() - startedAt > SORT_TIMEOUT_MS) {
            sorter.stop();
            currentSlot = 0;
            return false;
        }
    }

    currentSlot = slot;
    disableStepperIfAllowed();
    return true;
}
```

### 3.6.4 Slot Mapping Function

```cpp
struct SortSlotMap {
    const char *denom;
    uint8_t slot;
};

static const SortSlotMap sortSlotMap[] = {
    {"PHP_20", 1},   {"PHP_50", 2},   {"PHP_100", 3},
    {"PHP_200", 4},  {"PHP_500", 5},  {"PHP_1000", 6},
    {"USD_10", 7},   {"USD_50", 7},
    {"EUR_5", 8},    {"EUR_10", 8},
};

int slotForDenom(const char *denom) {
    if (denom == nullptr) {
        return -1;
    }
    const uint8_t mapCount = sizeof(sortSlotMap) / sizeof(sortSlotMap[0]);
    for (uint8_t i = 0; i < mapCount; i++) {
        if (strcmp(sortSlotMap[i].denom, denom) == 0) {
            return sortSlotMap[i].slot;
        }
    }
    return -1;
}
```

---

## 3.7 Integration with RPi

### 3.7.1 Serial Command Format

```
COMMAND FROM RPI:
{"cmd":"SORT","denom":"PHP_100"}

RESPONSE FROM ARDUINO:
{"status":"READY","slot":3}        // Sorter in position
{"status":"ERROR","code":"NOT_HOMED"}
{"status":"ERROR","code":"INVALID_DENOM"}
{"status":"ERROR","code":"TIMEOUT"}
```

### 3.7.2 Command Handler

```cpp
#include <ArduinoJson.h>

void sendDocument(JsonDocument &doc) {
    serializeJson(doc, Serial);
    Serial.println();
}

void sendError(const char *code) {
    StaticJsonDocument<128> doc;
    doc["status"] = "ERROR";
    doc["code"] = code;
    sendDocument(doc);
}

void handleSort(JsonDocument &cmdDoc) {
    const char *denom = cmdDoc["denom"] | "";
    const int slot = slotForDenom(denom);
    if (slot < 1) {
        sendError("INVALID_DENOM");
        return;
    }
    if (!sorterHomed) {
        sendError("NOT_HOMED");
        return;
    }
    if (!moveSorterToSlot((uint8_t)slot)) {
        sendError("TIMEOUT");
        return;
    }

    StaticJsonDocument<96> doc;
    doc["status"] = "READY";
    doc["slot"] = slot;
    sendDocument(doc);
}

void handleSortStatus() {
    StaticJsonDocument<160> doc;
    doc["status"] = "OK";
    doc["position"] = sorter.currentPosition();
    doc["slot"] = currentSlot;
    doc["homed"] = sorterHomed;
    sendDocument(doc);
}

void dispatchCommand(const String &line) {
    StaticJsonDocument<384> cmdDoc;
    DeserializationError err = deserializeJson(cmdDoc, line);
    if (err) {
        sendError("PARSE_ERROR");
        return;
    }

    const char *cmd = cmdDoc["cmd"] | "";
    if (strcmp(cmd, "HOME") == 0) {
        handleHome();
    } else if (strcmp(cmd, "SORT") == 0) {
        handleSort(cmdDoc);
    } else if (strcmp(cmd, "SORT_STATUS") == 0) {
        handleSortStatus();
    } else {
        sendError("UNKNOWN_CMD");
    }
}

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
