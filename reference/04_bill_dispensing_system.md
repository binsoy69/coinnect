# Coinnect System Architecture

## 04 - Bill Dispensing System

**Document Version:** 2.0  
**Date:** February 2026  
**Controller:** Arduino Mega #1 (Bill Controller) via `/dev/ttyUSB0`

---

## 4.1 Overview

The bill dispensing system has hardware capacity for 12 independent dispenser units. The firmware currently maps and implements 10 units for the standard supported denominations. Each unit uses two DC motors controlled by one L298N driver and one IR sensor for bill detection.

**Components per Dispenser Unit:**

- 2x DC Motors (12V)
  - Motor A: Pusher/Feeder (pushes bill from stack)
  - Motor B: Roller (pulls bill out and dispenses)
- 1x L298N Dual H-Bridge Driver
- 1x IR Sensor (detects dispensed bill)

**Total Components (Capacity / Active in Firmware):**

- 12 Dispenser Units (10 active in firmware)
- 24 DC Motors (20 active in firmware)
- 12 L298N Drivers (10 active in firmware)
- 12 IR Sensors (10 active in firmware)

**Dispenser Allocation:**

| Unit # | Denomination | Currency | Notes      |
| ------ | ------------ | -------- | ---------- |
| 1      | ₱20          | PHP      |            |
| 2      | ₱50          | PHP      |            |
| 3      | ₱100         | PHP      | Most used  |
| 4      | ₱200         | PHP      |            |
| 5      | ₱500         | PHP      | High value |
| 6      | ₱1000        | PHP      | High value |
| 7      | $10          | USD      |            |
| 8      | $50          | USD      |            |
| 9      | €5           | EUR      |            |
| 10     | €10          | EUR      |            |

---

## 4.2 Single Dispenser Unit Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        SINGLE BILL DISPENSER UNIT                                │
└─────────────────────────────────────────────────────────────────────────────────┘

    TOP VIEW (Bill Stack)
    ═════════════════════

              BILL STACK
           ┌─────────────┐
           │ ╔═════════╗ │
           │ ║  BILLS  ║ │
           │ ║ (stack) ║ │
           │ ╚═════════╝ │
           │      │      │
           │      ▼      │
           │  ┌───────┐  │
           │  │MOTOR A│  │  ◄── Pusher Motor
           │  │(Pusher│  │      Pushes bottom bill toward roller
           │  └───┬───┘  │
           │      │      │
           │      ▼      │
           │  ┌───────┐  │
           │  │MOTOR B│  │  ◄── Roller Motor
           │  │(Roller│  │      Grips and pulls bill out
           │  └───┬───┘  │
           │      │      │
           └──────┼──────┘
                  │
                  ▼
              ┌───────┐
              │IR SENS│    ◄── Detects bill passing through
              └───┬───┘
                  │
                  ▼
             ═══════════
              OUTPUT SLOT
             (to shared chute - future implementation)


    SIDE VIEW (Mechanism)
    ═════════════════════

         ┌─────────────────────────────────────────┐
         │             BILL STACK                  │
         │     ┌───────────────────────┐           │
         │     │███████████████████████│ ◄─ Bills  │
         │     │███████████████████████│           │
         │     │███████████████████████│           │
         │     │███████████████████████│           │
         │     └───────────┬───────────┘           │
         │                 │                       │
         │           ┌─────┴─────┐                 │
         │           │  MOTOR A  │                 │
         │           │  ┌─────┐  │                 │
         │           │  │  ◯  │  │ ◄─ Pusher wheel │
         │           │  └──┬──┘  │    on motor shaft│
         │           └─────┼─────┘                 │
         │                 │                       │
         │                 ▼                       │
         │           ┌───────────┐                 │
         │           │  MOTOR B  │                 │
         │           │ ┌───┐┌───┐│                 │
         │           │ │ ◯ ││ ◯ ││ ◄─ Rubber      │
         │           │ └───┘└───┘│    roller pair  │
         │           └─────┬─────┘                 │
         │                 │                       │
         │            ┌────┴────┐                  │
         │            │ IR SENS │                  │
         │            └────┬────┘                  │
         │                 │                       │
         └─────────────────┼───────────────────────┘
                           │
                           ▼
                      OUTPUT CHUTE
```

---

## 4.3 Dispensing Sequence

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          BILL DISPENSING ALGORITHM                               │
└─────────────────────────────────────────────────────────────────────────────────┘

    START
      │
      ▼
    ┌─────────────────────────┐
    │ Receive command from Pi │
    │ {"cmd":"DISPENSE",      │
    │  "denom":"PHP_100",     │
    │  "count":2}             │
    └───────────┬─────────────┘
                │
                ▼
    ┌─────────────────────────┐
    │ Validate denom & count  │
    │ (count: 1 to 20)        │
    └───────────┬─────────────┘
                │
                ▼
    ┌─────────────────────────┐
    │ Spin up Roller Motor B  │
    │ (keeps running during   │
    │ entire session)         │
    └───────────┬─────────────┘
                │
                ▼
          ┌─────┴─────┐
          │ bills_rem │
          │   > 0?    │
          └─────┬─────┘
                │
         YES    │    NO ────────────────────────────────┐
                │                                       │
                ▼                                       │
    ┌─────────────────────────┐                        │
    │ Attempt = 0             │                        │
    └───────────┬─────────────┘                        │
                │                                       │
                ▼◄──────────────────────────┐           │
          ┌─────┴─────┐                     │           │
          │ Attempt < │                     │           │
          │ 5?        │                     │           │
          └─────┬─────┘                     │           │
                │                           │           │
         YES    │    NO ──────────────────┐ │           │
                │                         │ │           │
                ▼                         ▼ │           │
    ┌─────────────────────────┐     ┌───────────┐       │
    │ Pulse Pusher Motor A    │     │ Stop B    │       │
    │ (Forward for 200ms)     │     │ return    │       │
    │ Then Stop Pusher A      │     │ JAM error │       │
    └───────────┬─────────────┘     └───────────┘       │
                │                                       │
                ▼                                       │
          ┌─────┴─────┐                                 │
          │ Bill IR   │                                 │
          │ Detected? │                                 │
          └─────┬─────┘                                 │
                │                                       │
         YES    │    NO ────────────────► [Attempt++] ──┘
                │
                ▼
    ┌─────────────────────────┐
    │ Delay ROLLER_EXTRA      │
    │ (300ms) to pull bill    │
    └───────────┬─────────────┘
                │
                ▼
    ┌─────────────────────────┐
    │ bills_rem -= 1          │
    └───────────┬─────────────┘
                │
                ▼
          ┌─────┴─────┐
          │ Wait for  │
          │ IR clear  │
          │ (1000ms)? │
          └─────┬─────┘
                │
         YES    │    NO ──────────────────┐
                │                         │
                ▼                         ▼
          ┌─────┴─────┐             ┌───────────┐
          │ bills_rem │             │ Stop B    │
          │   == 0?   │             │ return    │
          └─────┬─────┘             │ JAM error │
                │                   └───────────┘
         NO     │    YES ───────────────┐
                │                       │
                ▼                       │
    ┌─────────────────────────┐         │
    │ Delay INTER_BILL        │         │
    │ (100ms)                 │         │
    └───────────┬─────────────┘         │
                │                       │
                └───────────────────────┼───────┐
                                        │       │
    ◄───────────────────────────────────┘       │
                │                               │
                ▼                               ▼
    ┌─────────────────────────┐           ┌───────────┐
    │ Stop Roller Motor B     │           │ Run       │
    │                         │           │ Conveyor  │
    │                         │           │ (3s)      │
    └─────────────────────────┘           └─────┬─────┘
                                                │
                                                ▼
                                           ┌─────────┐
                                           │ Return  │
                                           │ OK      │
                                           └─────────┘
                │
                ▼
              END
```

---

## 4.4 L298N Wiring Per Unit

```
                          L298N MOTOR DRIVER
                       ┌─────────────────────────┐
                       │                         │
         +12V (ATX) ───┤ +12V            +5V OUT├─── (Do not use for Arduino)
                       │                         │
         GND ──────────┤ GND                 GND├─── GND
                       │                         │
                       │                         │
    Motor A (+) ───────┤ OUT1             IN1 ├◄─── Arduino (Direction 1)
    Motor A (-) ───────┤ OUT2             IN2 ├◄─── Arduino (Direction 2)
                       │                         │
    Motor B (+) ───────┤ OUT3             IN3 ├◄─── Arduino (Direction 1)
    Motor B (-) ───────┤ OUT4             IN4 ├◄─── Arduino (Direction 2)
                       │                         │
                       │                  ENA ├◄─── Arduino (PWM or jumper HIGH)
                       │                  ENB ├◄─── Arduino (PWM or jumper HIGH)
                       │                         │
                       └─────────────────────────┘


    MOTOR CONTROL LOGIC:
    ════════════════════

    ┌───────────┬───────┬───────┬──────────────────┐
    │  Action   │  IN1  │  IN2  │     Result       │
    ├───────────┼───────┼───────┼──────────────────┤
    │  Forward  │ HIGH  │  LOW  │  Motor CW        │
    │  Reverse  │  LOW  │ HIGH  │  Motor CCW       │
    │  Brake    │ HIGH  │ HIGH  │  Active brake    │
    │  Coast    │  LOW  │  LOW  │  Motor free      │
    └───────────┴───────┴───────┴──────────────────┘

    ENA/ENB: Set HIGH to enable, or use PWM for speed control
             Leave jumper ON to keep always enabled at full speed
```

---

## 4.5 GPIO Requirements Analysis

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    GPIO REQUIREMENTS PER DISPENSER                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Component          │  Pins Needed  │  Type                                     │
├─────────────────────┼───────────────┼───────────────────────────────────────────┤
│  Motor A Direction  │  2            │  Digital Output (IN1, IN2)                │
│  Motor B Direction  │  2            │  Digital Output (IN3, IN4)                │
│  Motor A Enable     │  1            │  PWM or Digital (ENA)                     │
│  Motor B Enable     │  1            │  PWM or Digital (ENB)                     │
│  IR Sensor          │  1            │  Digital Input                            │
├─────────────────────┼───────────────┼───────────────────────────────────────────┤
│  TOTAL PER UNIT     │  7 pins       │                                           │
│  TOTAL (12 units)   │  84 pins      │  Exceeds Arduino Mega (54 digital)        │
└─────────────────────┴───────────────┴───────────────────────────────────────────┘


    SOLUTION: Pin Optimization Strategies
    ═════════════════════════════════════

    Option A: Tie ENA/ENB HIGH (use jumpers on L298N)
    ─────────────────────────────────────────────────
    - Removes 2 pins per unit = saves 24 pins
    - Motors always at full speed (OK for dispensing)
    - Total: 5 pins × 12 = 60 pins (still tight)

    Option B: Share direction pins with enable control
    ─────────────────────────────────────────────────
    - Use IN1/IN2 pattern for forward/reverse/stop
    - ENA as enable gate only
    - 4 direction pins + 1 IR = 5 pins per unit
    - Total: 5 pins × 12 = 60 pins

    Option C: Use I/O Expander (Recommended)
    ─────────────────────────────────────────────────
    - MCP23017: 16 GPIO pins per chip via I2C
    - 4-5 chips for motor direction control
    - Keep IR sensors on Arduino direct pins
    - I2C only needs 2 pins (SDA, SCL)

    Option D: Simplified control per unit
    ─────────────────────────────────────────────────
    - Use ONLY direction pairs (no separate enable)
    - IN1/IN2 for Motor A, IN3/IN4 for Motor B
    - 4 direction + 1 IR = 5 pins
    - Tie ENA/ENB HIGH with jumpers
    - Total: 60 pins needed

    RECOMMENDED: Option D with careful pin assignment
    Arduino Mega has 54 digital + 16 analog = 70 usable pins
```

---

## 4.6 Pin Assignment (Arduino Mega #1)

### 4.6.1 Dispenser Motor Pins

Using Option D (ENA/ENB tied HIGH with jumpers, driving only IN1-IN4):

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    DISPENSER MOTOR PIN ASSIGNMENTS                               │
├────────┬─────────────┬────────────────────────────────────────────────────────────┤
│ Unit # │ Denomination│   IN1    IN2    IN3    IN4   │  Notes                     │
├────────┼─────────────┼────────────────────────────────┼────────────────────────────┤
│   1    │   ₱20       │   D10    D11    D12    D13    │                            │
│   2    │   ₱50       │   D14    D15    D16    D17    │                            │
│   3    │   ₱100      │   D18    D19    D20    D21    │                            │
│   4    │   ₱200      │   D22    D23    D24    D25    │                            │
│   5    │   ₱500      │   D26    D27    D28    D29    │                            │
│   6    │   ₱1000     │   D30    D31    D32    D33    │                            │
│   7    │   $10       │   D34    D35    D36    D37    │                            │
│   8    │   $50       │   D38    D39    D40    D41    │                            │
│   9    │   €5        │   D42    D43    D44    D45    │                            │
│   10   │   €10       │   D46    D47    D48    D49    │                            │
└────────┴─────────────┴────────────────────────────────┴────────────────────────────┘
```

### 4.6.2 IR Sensor Pins

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       IR SENSOR PIN ASSIGNMENTS                                  │
├────────┬─────────────┬──────────────┬────────────────────────────────────────────┤
│ Unit # │ Denomination│   IR Pin     │  Notes                                     │
├────────┼─────────────┼──────────────┼────────────────────────────────────────────┤
│   1    │   ₱20       │   A0         │ Analog inputs used as digital              │
│   2    │   ₱50       │   A1         │ Analog inputs used as digital              │
│   3    │   ₱100      │   A2         │ Analog inputs used as digital              │
│   4    │   ₱200      │   A3         │ Analog inputs used as digital              │
│   5    │   ₱500      │   A4         │ Analog inputs used as digital              │
│   6    │   ₱1000     │   A5         │ Analog inputs used as digital              │
│   7    │   $10       │   A6         │ Analog inputs used as digital              │
│   8    │   $50       │   A7         │ Analog inputs used as digital              │
│   9    │   €5        │   A8         │ Analog inputs used as digital              │
│   10   │   €10       │   A9         │ Analog inputs used as digital              │
└────────┴─────────────┴──────────────┴────────────────────────────────────────────┘
```

---

## 4.7 Complete Wiring Schematic (One Unit Example)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│              DISPENSER UNIT 3 (₱100) - COMPLETE WIRING                           │
└─────────────────────────────────────────────────────────────────────────────────┘

                              +12V (ATX)
                                 │
                    ┌────────────┴────────────┐
                    │                         │
               ┌────┴────┐               ┌────┴────┐
               │  100µF  │               │  100µF  │
               │   CAP   │               │   CAP   │
               └────┬────┘               └────┬────┘
                    │                         │
                    │    ┌───────────────┐    │
                    └────┤    L298N #3   ├────┘
                         │               │
                         │ +12V      GND ├────────────────┐
                         │               │                │
    Motor A   ┌──────────┤ OUT1     IN1 ├◄───── D30      │
    (Pusher)  │          │               │                │
              │  ┌───────┤ OUT2     IN2 ├◄───── D31      │
              │  │       │               │                │
              └──┤  M    │               │                │
                 │  A    │ OUT3     IN3 ├◄───── D32      │
              ┌──┤       │               │                │
    Motor B   │  │       │ OUT4     IN4 ├◄───── D33      │
    (Roller)  │  └───────┤               │                │
              └──────────┤               │                │
                         │  ENA     ENB  │                │
                         │   ║       ║   │                │
                         │ JUMPER JUMPER │ (Keep jumpers) │
                         │               │                │
                         └───────────────┘                │
                                                          │
                                                          │
    ┌─────────────────────────────────────────────────────┤
    │                                                     │
    │    IR SENSOR (FC-51)                                │
    │    ┌───────────────┐                                │
    │    │               │                                │
    │    │  VCC ─────────┼──── 5V (ATX or Arduino)        │
    │    │  GND ─────────┼────────────────────────────────┘
    │    │  OUT ─────────┼──── A2 (Arduino)
    │    │               │
    │    └───────────────┘
    │
    │
    │
    ════════════════════════════════════════════════════════
                           GND BUS


    ┌──────────────────────────────────────────────────────┐
    │                   ARDUINO MEGA                       │
    │                                                      │
    │    D30 ───► L298N IN1 (Motor A Dir 1)               │
    │    D31 ───► L298N IN2 (Motor A Dir 2)               │
    │    D32 ───► L298N IN3 (Motor B Dir 1)               │
    │    D33 ───► L298N IN4 (Motor B Dir 2)               │
    │                                                      │
    │    A2  ◄─── IR Sensor OUT                           │
    │                                                      │
    │    GND ───► Common Ground                           │
    │                                                      │
    └──────────────────────────────────────────────────────┘
```

---

## 4.8 Arduino Control Code

### 4.8.1 Dispenser Class Definition

```cpp
// Bill Dispensing System - Arduino Code

// Dispenser Unit Structure
struct DispenserUnit {
    uint8_t motorAIn1;
    uint8_t motorAIn2;
    uint8_t motorBIn3;
    uint8_t motorBIn4;
    uint8_t irSensorPin;
    const char *denom;
};

// Define all 10 dispensers
DispenserUnit dispensers[] = {
    {10, 11, 12, 13, A0, "PHP_20"},
    {14, 15, 16, 17, A1, "PHP_50"},
    {18, 19, 20, 21, A2, "PHP_100"},
    {22, 23, 24, 25, A3, "PHP_200"},
    {26, 27, 28, 29, A4, "PHP_500"},
    {30, 31, 32, 33, A5, "PHP_1000"},
    {34, 35, 36, 37, A6, "USD_10"},
    {38, 39, 40, 41, A7, "USD_50"},
    {42, 43, 44, 45, A8, "EUR_5"},
    {46, 47, 48, 49, A9, "EUR_10"}
};

static const uint8_t DISPENSER_COUNT = sizeof(dispensers) / sizeof(dispensers[0]);

// Conveyor motor control pins
static const uint8_t CONVEYOR_PHP_IN1 = 2;
static const uint8_t CONVEYOR_PHP_IN2 = 3;
static const uint8_t CONVEYOR_FOREIGN_IN1 = 8;
static const uint8_t CONVEYOR_FOREIGN_IN2 = 9;

// Configurable conveyor run duration (in milliseconds)
static const unsigned long CONVEYOR_DURATION_MS = 3000;

// Timing constants (milliseconds)
static const unsigned long PUSHER_DURATION_MS = 200;
static const uint8_t DISPENSE_RETRY_ATTEMPTS = 5;
static const unsigned long ROLLER_SPINUP_MS = 500;
static const unsigned long IR_DETECT_TIMEOUT_MS = 1000;
static const unsigned long BILL_CLEAR_TIMEOUT_MS = 1000;
static const unsigned long ROLLER_EXTRA_MS = 300;
static const unsigned long INTER_BILL_DELAY_MS = 100;
static const uint8_t NO_PIN = 255;
```

### 4.8.2 Setup Function

```cpp
void setupDispensers() {
    for (uint8_t i = 0; i < DISPENSER_COUNT; i++) {
        // Motor control pins as output
        pinMode(dispensers[i].motorAIn1, OUTPUT);
        pinMode(dispensers[i].motorAIn2, OUTPUT);
        pinMode(dispensers[i].motorBIn3, OUTPUT);
        if (dispensers[i].motorBIn4 != NO_PIN) {
            pinMode(dispensers[i].motorBIn4, OUTPUT);
        }

        // IR sensor as input
        pinMode(dispensers[i].irSensorPin, INPUT_PULLUP);
    }
    stopAllDispensers();
}
```

### 4.8.3 Motor Control Functions

```cpp
void setPinLowIfPresent(uint8_t pin) {
    if (pin != NO_PIN) {
        digitalWrite(pin, LOW);
    }
}

void setPinHighIfPresent(uint8_t pin) {
    if (pin != NO_PIN) {
        digitalWrite(pin, HIGH);
    }
}

void stopMotorA(uint8_t unitIndex) {
    setPinLowIfPresent(dispensers[unitIndex].motorAIn1);
    setPinLowIfPresent(dispensers[unitIndex].motorAIn2);
}

void stopMotorB(uint8_t unitIndex) {
    setPinLowIfPresent(dispensers[unitIndex].motorBIn3);
    setPinLowIfPresent(dispensers[unitIndex].motorBIn4);
}

void stopAllDispensers() {
    for (uint8_t i = 0; i < DISPENSER_COUNT; i++) {
        stopMotorA(i);
        stopMotorB(i);
    }
}

void motorAForward(uint8_t unitIndex) {
    setPinHighIfPresent(dispensers[unitIndex].motorAIn1);
    setPinLowIfPresent(dispensers[unitIndex].motorAIn2);
}

void motorBForward(uint8_t unitIndex) {
    setPinHighIfPresent(dispensers[unitIndex].motorBIn3);
    setPinLowIfPresent(dispensers[unitIndex].motorBIn4);
}

bool isBillDetected(uint8_t unitIndex) {
    // IR sensor: LOW = obstacle detected (bill present)
    return digitalRead(dispensers[unitIndex].irSensorPin) == LOW;
}

bool waitForBillDetected(uint8_t unitIndex, unsigned long timeoutMs) {
    const unsigned long startedAt = millis();
    while (millis() - startedAt < timeoutMs) {
        if (isBillDetected(unitIndex)) {
            return true;
        }
        delay(10);
    }
    return false;
}

bool waitForBillCleared(uint8_t unitIndex, unsigned long timeoutMs) {
    const unsigned long startedAt = millis();
    while (millis() - startedAt < timeoutMs) {
        if (!isBillDetected(unitIndex)) {
            return true;
        }
        delay(10);
    }
    return false;
}
```

### 4.8.4 Dispense Function

```cpp
int dispenseBills(uint8_t unitIndex, int count, const char **errorCode) {
    int dispensed = 0;
    *errorCode = nullptr;

    // Roller Motor B starts before loop and spins during the whole dispense operation
    motorBForward(unitIndex);
    delay(ROLLER_SPINUP_MS);

    for (int i = 0; i < count; i++) {
        bool detected = false;

        for (uint8_t attempt = 0; attempt < DISPENSE_RETRY_ATTEMPTS; attempt++) {
            motorAForward(unitIndex);
            delay(PUSHER_DURATION_MS);
            stopMotorA(unitIndex);

            if (waitForBillDetected(unitIndex, IR_DETECT_TIMEOUT_MS)) {
                detected = true;
                break;
            }
        }

        if (!detected) {
            stopMotorA(unitIndex);
            stopMotorB(unitIndex);
            *errorCode = "JAM";
            return dispensed;
        }

        delay(ROLLER_EXTRA_MS);
        dispensed++;

        if (!waitForBillCleared(unitIndex, BILL_CLEAR_TIMEOUT_MS)) {
            stopMotorA(unitIndex);
            stopMotorB(unitIndex);
            *errorCode = "JAM";
            return dispensed;
        }

        if (i < count - 1) {
            delay(INTER_BILL_DELAY_MS);
        }
    }

    stopMotorA(unitIndex);
    stopMotorB(unitIndex);
    return dispensed;
}
```

### 4.8.5 Find Unit by Denomination

```cpp
int findDispenserIndex(const char *denom) {
    if (denom == nullptr) {
        return -1;
    }
    for (uint8_t i = 0; i < DISPENSER_COUNT; i++) {
        if (strcmp(dispensers[i].denom, denom) == 0) {
            return i;
        }
    }
    return -1;
}
```

---

## 4.9 Serial Command Handler

```cpp
#include <ArduinoJson.h>

void sendDocument(JsonDocument &doc) {
    serializeJson(doc, Serial);
    Serial.println();
}

void sendError(const char *code, int dispensed = -1) {
    StaticJsonDocument<128> doc;
    doc["status"] = "ERROR";
    doc["code"] = code;
    if (dispensed >= 0) {
        doc["dispensed"] = dispensed;
    }
    sendDocument(doc);
}

void runConveyorForDenom(const char *denom) {
    bool isPhp = (strncmp(denom, "PHP_", 4) == 0);
    if (isPhp) {
        digitalWrite(CONVEYOR_PHP_IN1, HIGH);
        digitalWrite(CONVEYOR_PHP_IN2, LOW);
        delay(CONVEYOR_DURATION_MS);
        digitalWrite(CONVEYOR_PHP_IN1, LOW);
        digitalWrite(CONVEYOR_PHP_IN2, LOW);
    } else {
        digitalWrite(CONVEYOR_FOREIGN_IN1, HIGH);
        digitalWrite(CONVEYOR_FOREIGN_IN2, LOW);
        delay(CONVEYOR_DURATION_MS);
        digitalWrite(CONVEYOR_FOREIGN_IN1, LOW);
        digitalWrite(CONVEYOR_FOREIGN_IN2, LOW);
    }
}

void handleDispense(JsonDocument &cmdDoc) {
    const char *denom = cmdDoc["denom"] | "";
    const int count = cmdDoc["count"] | 0;
    const int unitIndex = findDispenserIndex(denom);
    if (unitIndex < 0) {
        sendError("INVALID_DENOM");
        return;
    }
    if (count < 1 || count > 20) {
        sendError("INVALID_COUNT");
        return;
    }

    const char *errorCode = nullptr;
    const int dispensed = dispenseBills((uint8_t)unitIndex, count, &errorCode);
    
    if (dispensed > 0) {
        runConveyorForDenom(denom);
    }

    if (errorCode != nullptr) {
        sendError(errorCode, dispensed);
        return;
    }

    StaticJsonDocument<96> doc;
    doc["status"] = "OK";
    doc["dispensed"] = dispensed;
    sendDocument(doc);
}
```

---

## 4.10 Timing Specifications

| Operation                | Duration         | Notes                     |
| ------------------------ | ---------------- | ------------------------- |
| Pusher activation        | 200ms            | Push one bill             |
| Bill detection wait      | Up to 2000ms     | Timeout limit             |
| Roller extra run         | 300ms            | Ensure bill clears        |
| Inter-bill delay         | 100ms            | Between consecutive bills |
| **Single bill dispense** | **~600-700ms**   | Typical                   |
| **5 bills dispense**     | **~3-4 seconds** |                           |

---

## 4.11 Error Handling

| Error Code      | Description                | Suggested Action               |
| --------------- | -------------------------- | ------------------------------ |
| `INVALID_UNIT`  | Unit index out of range    | Check command format           |
| `UNKNOWN_DENOM` | Denomination not found     | Verify denomination string     |
| `JAM_OR_EMPTY`  | IR timeout during dispense | Check for jam, refill if empty |
| `MOTOR_FAULT`   | Motor not responding       | Check wiring, driver           |

---

## 4.12 Future Enhancement: Shared Output Chute

```
    SHARED OUTPUT CHUTE CONCEPT (Future Implementation)
    ════════════════════════════════════════════════════

                    ┌─────────────────────────────────────────────────────┐
                    │              DISPENSER ARRAY (12 UNITS)              │
                    │                                                      │
                    │  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐              │
                    │  │ 1 │ │ 2 │ │ 3 │ │ 4 │ │ 5 │ │ 6 │   PHP        │
                    │  └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘              │
                    │    │     │     │     │     │     │                 │
                    │    └─────┴─────┴─────┴─────┴─────┴──────┐          │
                    │                                          │          │
                    │  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐   │          │
                    │  │ 7 │ │ 8 │ │ 9 │ │10│ │11│ │12│   │  Foreign   │
                    │  └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘   │          │
                    │    │     │     │     │     │     │      │          │
                    │    └─────┴─────┴─────┴─────┴─────┴──────┤          │
                    │                                          │          │
                    │                                          ▼          │
                    │                              ┌────────────────┐     │
                    │                              │  COLLECTION    │     │
                    │                              │    CHUTE       │     │
                    │                              └───────┬────────┘     │
                    │                                      │              │
                    └──────────────────────────────────────┼──────────────┘
                                                           │
                                                           ▼
                                                    ┌─────────────┐
                                                    │   OUTPUT    │
                                                    │    TRAY     │
                                                    └─────────────┘

    Implementation Options:
    1. Gravity chute (angled slides)
    2. Conveyor belt collector
    3. Pneumatic/vacuum transport
```

---

_Document 4 of 10 - Coinnect System Architecture_
