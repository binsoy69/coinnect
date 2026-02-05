# Coinnect System Architecture

## 04 - Bill Dispensing System

**Document Version:** 2.0  
**Date:** February 2026  
**Controller:** Arduino Mega #1 (Bill Controller) via `/dev/ttyUSB0`

---

## 4.1 Overview

The bill dispensing system consists of 12 independent dispenser units, each capable of dispensing one denomination. Each unit uses two DC motors controlled by one L298N driver and one IR sensor for bill detection.

**Components per Dispenser Unit:**

- 2x DC Motors (12V)
  - Motor A: Pusher/Feeder (pushes bill from stack)
  - Motor B: Roller (pulls bill out and dispenses)
- 1x L298N Dual H-Bridge Driver
- 1x IR Sensor (detects dispensed bill)

**Total Components:**

- 12 Dispenser Units
- 24 DC Motors
- 12 L298N Drivers
- 12 IR Sensors

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
| 9      | $100         | USD      |            |
| 10     | €5           | EUR      |            |
| 11     | €10          | EUR      |            |
| 12     | €20          | EUR      |            |

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
    │  "unit":3,              │
    │  "count":2}             │
    └───────────┬─────────────┘
                │
                ▼
    ┌─────────────────────────┐
    │ Validate unit number    │
    │ (1-12)                  │
    └───────────┬─────────────┘
                │
                ▼
    ┌─────────────────────────┐
    │ Set bills_remaining =   │
    │ requested count         │
    └───────────┬─────────────┘
                │
                ▼
          ┌─────┴─────┐
          │bills_rem >│
          │    0?     │
          └─────┬─────┘
                │
         YES    │    NO ────────────────────────────────┐
                │                                       │
                ▼                                       │
    ┌─────────────────────────┐                        │
    │ STEP 1: Activate Pusher │                        │
    │ Motor A: Forward        │                        │
    │ Duration: 200ms         │                        │
    └───────────┬─────────────┘                        │
                │                                       │
                ▼                                       │
    ┌─────────────────────────┐                        │
    │ STEP 2: Activate Roller │                        │
    │ Motor B: Forward        │                        │
    │ (Motor A stops)         │                        │
    └───────────┬─────────────┘                        │
                │                                       │
                ▼                                       │
    ┌─────────────────────────┐                        │
    │ STEP 3: Wait for IR     │                        │
    │ Timeout: 2 seconds      │                        │
    └───────────┬─────────────┘                        │
                │                                       │
         ┌──────┴──────┐                               │
         │             │                               │
    IR TRIGGERED   TIMEOUT                             │
         │             │                               │
         ▼             ▼                               │
    ┌─────────┐  ┌──────────────────┐                  │
    │ Success │  │ ERROR: JAM or    │                  │
    │         │  │ EMPTY STACK      │                  │
    └────┬────┘  └────────┬─────────┘                  │
         │                │                            │
         ▼                ▼                            │
    ┌─────────┐  ┌──────────────────┐                  │
    │bills_rem│  │ Stop all motors  │                  │
    │  -= 1   │  │ Report error     │                  │
    └────┬────┘  │ Exit loop        │                  │
         │       └────────┬─────────┘                  │
         │                │                            │
         ▼                │                            │
    ┌─────────────────────┴────┐                       │
    │ STEP 4: Continue roller  │                       │
    │ for 300ms more           │                       │
    │ (ensure bill clears)     │                       │
    └───────────┬──────────────┘                       │
                │                                      │
                ▼                                      │
    ┌─────────────────────────┐                        │
    │ STEP 5: Stop Motor B    │                        │
    │ Brief delay (100ms)     │                        │
    └───────────┬─────────────┘                        │
                │                                      │
                └───────────────►(loop back)           │
                                                       │
    ◄──────────────────────────────────────────────────┘
                │
                ▼
    ┌─────────────────────────┐
    │ Report completion       │
    │ {"status":"OK",         │
    │  "dispensed":2}         │
    └─────────────────────────┘
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

## 4.6 Pin Assignment (Arduino Mega)

### 4.6.1 Dispenser Motor Pins

Using Option D (ENA/ENB tied HIGH with jumpers):

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    DISPENSER MOTOR PIN ASSIGNMENTS                               │
├────────┬─────────────┬────────────────────────────────────────────────────────────┤
│ Unit # │ Denomination│   IN1    IN2    IN3    IN4   │  Notes                     │
├────────┼─────────────┼────────────────────────────────┼────────────────────────────┤
│   1    │   ₱20       │   D22    D23    D24    D25    │                            │
│   2    │   ₱50       │   D26    D27    D28    D29    │                            │
│   3    │   ₱100      │   D30    D31    D32    D33    │                            │
│   4    │   ₱200      │   D34    D35    D36    D37    │                            │
│   5    │   ₱500      │   D38    D39    D40    D41    │                            │
│   6    │   ₱1000     │   D42    D43    D44    D45    │                            │
│   7    │   $10       │   D46    D47    D48    D49    │                            │
│   8    │   $50       │   D50    D51    D52    D53    │  D50-53 also SPI (avoid)   │
│   9    │   $100      │   A8     A9     A10    A11    │  Using analog as digital   │
│   10   │   €5        │   A12    A13    A14    A15    │  Using analog as digital   │
│   11   │   €10       │   D6     D7     D8     D9     │                            │
│   12   │   €20       │   D10    D11    D12    D13    │                            │
└────────┴─────────────┴────────────────────────────────┴────────────────────────────┘

Note: D50-D53 are SPI pins. If SPI is not needed, they can be used.
      Otherwise, use I/O expander for units 8-10.
```

### 4.6.2 IR Sensor Pins

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       IR SENSOR PIN ASSIGNMENTS                                  │
├────────┬─────────────┬──────────────┬────────────────────────────────────────────┤
│ Unit # │ Denomination│   IR Pin     │  Notes                                     │
├────────┼─────────────┼──────────────┼────────────────────────────────────────────┤
│   1    │   ₱20       │   A0         │                                            │
│   2    │   ₱50       │   A1         │                                            │
│   3    │   ₱100      │   A2         │                                            │
│   4    │   ₱200      │   A3         │                                            │
│   5    │   ₱500      │   A4         │                                            │
│   6    │   ₱1000     │   A5         │                                            │
│   7    │   $10       │   A6         │                                            │
│   8    │   $50       │   A7         │                                            │
│   9    │   $100      │   D14 (TX3)  │  Serial3 TX - OK if Serial3 unused        │
│   10   │   €5        │   D15 (RX3)  │  Serial3 RX - OK if Serial3 unused        │
│   11   │   €10       │   D16 (TX2)  │  Serial2 TX - OK if Serial2 unused        │
│   12   │   €20       │   D17 (RX2)  │  Serial2 RX - OK if Serial2 unused        │
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
    uint8_t motorA_IN1;
    uint8_t motorA_IN2;
    uint8_t motorB_IN3;
    uint8_t motorB_IN4;
    uint8_t irSensorPin;
    String denomination;
};

// Define all 12 dispensers
DispenserUnit dispensers[12] = {
    // Unit 1: PHP 20
    {22, 23, 24, 25, A0, "PHP_20"},
    // Unit 2: PHP 50
    {26, 27, 28, 29, A1, "PHP_50"},
    // Unit 3: PHP 100
    {30, 31, 32, 33, A2, "PHP_100"},
    // Unit 4: PHP 200
    {34, 35, 36, 37, A3, "PHP_200"},
    // Unit 5: PHP 500
    {38, 39, 40, 41, A4, "PHP_500"},
    // Unit 6: PHP 1000
    {42, 43, 44, 45, A5, "PHP_1000"},
    // Unit 7: USD 10
    {46, 47, 48, 49, A6, "USD_10"},
    // Unit 8: USD 50
    {50, 51, 52, 53, A7, "USD_50"},
    // Unit 9: USD 100
    {A8, A9, A10, A11, 14, "USD_100"},
    // Unit 10: EUR 5
    {A12, A13, A14, A15, 15, "EUR_5"},
    // Unit 11: EUR 10
    {6, 7, 8, 9, 16, "EUR_10"},
    // Unit 12: EUR 20
    {10, 11, 12, 13, 17, "EUR_20"}
};

// Timing constants (milliseconds)
#define PUSHER_DURATION     200
#define ROLLER_TIMEOUT      2000
#define ROLLER_EXTRA        300
#define INTER_BILL_DELAY    100
```

### 4.8.2 Setup Function

```cpp
void setupDispensers() {
    for (int i = 0; i < 12; i++) {
        // Motor control pins as output
        pinMode(dispensers[i].motorA_IN1, OUTPUT);
        pinMode(dispensers[i].motorA_IN2, OUTPUT);
        pinMode(dispensers[i].motorB_IN3, OUTPUT);
        pinMode(dispensers[i].motorB_IN4, OUTPUT);

        // IR sensor as input
        pinMode(dispensers[i].irSensorPin, INPUT);

        // Initialize motors to OFF
        stopMotorA(i);
        stopMotorB(i);
    }
}
```

### 4.8.3 Motor Control Functions

```cpp
void motorA_Forward(int unitIndex) {
    digitalWrite(dispensers[unitIndex].motorA_IN1, HIGH);
    digitalWrite(dispensers[unitIndex].motorA_IN2, LOW);
}

void motorA_Reverse(int unitIndex) {
    digitalWrite(dispensers[unitIndex].motorA_IN1, LOW);
    digitalWrite(dispensers[unitIndex].motorA_IN2, HIGH);
}

void stopMotorA(int unitIndex) {
    digitalWrite(dispensers[unitIndex].motorA_IN1, LOW);
    digitalWrite(dispensers[unitIndex].motorA_IN2, LOW);
}

void motorB_Forward(int unitIndex) {
    digitalWrite(dispensers[unitIndex].motorB_IN3, HIGH);
    digitalWrite(dispensers[unitIndex].motorB_IN4, LOW);
}

void motorB_Reverse(int unitIndex) {
    digitalWrite(dispensers[unitIndex].motorB_IN3, LOW);
    digitalWrite(dispensers[unitIndex].motorB_IN4, HIGH);
}

void stopMotorB(int unitIndex) {
    digitalWrite(dispensers[unitIndex].motorB_IN3, LOW);
    digitalWrite(dispensers[unitIndex].motorB_IN4, LOW);
}

bool isBillDetected(int unitIndex) {
    // IR sensor: LOW = obstacle detected (bill present)
    return digitalRead(dispensers[unitIndex].irSensorPin) == LOW;
}
```

### 4.8.4 Dispense Function

```cpp
struct DispenseResult {
    bool success;
    int dispensed;
    String error;
};

DispenseResult dispenseBills(int unitIndex, int count) {
    DispenseResult result = {true, 0, ""};

    // Validate unit index
    if (unitIndex < 0 || unitIndex >= 12) {
        result.success = false;
        result.error = "INVALID_UNIT";
        return result;
    }

    for (int i = 0; i < count; i++) {
        // Step 1: Activate pusher motor
        motorA_Forward(unitIndex);
        delay(PUSHER_DURATION);
        stopMotorA(unitIndex);

        // Step 2: Activate roller motor
        motorB_Forward(unitIndex);

        // Step 3: Wait for IR sensor to detect bill
        unsigned long startTime = millis();
        bool billDetected = false;

        while (millis() - startTime < ROLLER_TIMEOUT) {
            if (isBillDetected(unitIndex)) {
                billDetected = true;
                break;
            }
            delay(10);  // 10ms polling
        }

        if (!billDetected) {
            // Timeout - bill jam or empty
            stopMotorB(unitIndex);
            result.success = false;
            result.error = "JAM_OR_EMPTY";
            return result;
        }

        // Step 4: Continue roller to clear bill
        delay(ROLLER_EXTRA);

        // Step 5: Stop roller
        stopMotorB(unitIndex);

        result.dispensed++;

        // Brief delay between bills
        if (i < count - 1) {
            delay(INTER_BILL_DELAY);
        }
    }

    return result;
}
```

### 4.8.5 Find Unit by Denomination

```cpp
int findUnitByDenomination(String denom) {
    for (int i = 0; i < 12; i++) {
        if (dispensers[i].denomination == denom) {
            return i;
        }
    }
    return -1;  // Not found
}
```

---

## 4.9 Serial Command Handler

```cpp
void handleDispenseCommand(String command) {
    // Expected format: {"cmd":"DISPENSE","denom":"PHP_100","count":2}

    // Extract denomination
    int denomStart = command.indexOf("denom") + 8;
    int denomEnd = command.indexOf("\"", denomStart);
    String denom = command.substring(denomStart, denomEnd);

    // Extract count
    int countStart = command.indexOf("count") + 7;
    int countEnd = command.indexOf("}", countStart);
    int count = command.substring(countStart, countEnd).toInt();

    // Find dispenser unit
    int unitIndex = findUnitByDenomination(denom);

    if (unitIndex < 0) {
        Serial.println("{\"status\":\"ERROR\",\"code\":\"UNKNOWN_DENOM\"}");
        return;
    }

    // Dispense bills
    DispenseResult result = dispenseBills(unitIndex, count);

    if (result.success) {
        Serial.print("{\"status\":\"OK\",\"dispensed\":");
        Serial.print(result.dispensed);
        Serial.println("}");
    } else {
        Serial.print("{\"status\":\"ERROR\",\"code\":\"");
        Serial.print(result.error);
        Serial.print("\",\"dispensed\":");
        Serial.print(result.dispensed);
        Serial.println("}");
    }
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
