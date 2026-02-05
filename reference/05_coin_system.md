# Coinnect System Architecture

## 05 - Coin System

**Document Version:** 2.0  
**Date:** February 2026  
**Controller:** Arduino Mega #2 (Coin & Security Controller) via `/dev/ttyACM0`

---

## 5.1 Overview

The coin system consists of two subsystems:

1. **Coin Acceptor** - Validates and accepts coins from users
2. **Coin Dispenser** - Dispenses coins to users as change

**Components:**

- 1x Multi-Coin Acceptor Module (CH-926 or similar)
- 4x Servo Motors (for dispensing)
- 4x Coin Storage Tubes

**Supported Denominations:**
| Coin | Diameter | Thickness | Weight |
|------|----------|-----------|--------|
| ₱1 | 20mm | 1.5mm | 3.3g |
| ₱5 | 25mm | 1.9mm | 7.4g |
| ₱10 | 27mm | 2.0mm | 8.7g |
| ₱20 | 28mm | 2.0mm | 9.5g |

---

## 5.2 Coin Acceptor System

### 5.2.1 Multi-Coin Acceptor Overview

The CH-926 (or similar) multi-coin acceptor handles coin validation internally using:

- Size detection (diameter)
- Thickness measurement
- Material/metal detection (inductive sensing)
- Weight verification (optional, higher-end models)

The acceptor outputs pulses to indicate accepted coins.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       MULTI-COIN ACCEPTOR MODULE                                 │
│                            (e.g., CH-926)                                        │
└─────────────────────────────────────────────────────────────────────────────────┘

                         ┌─────────────────────────────────────┐
                         │         COIN ACCEPTOR               │
                         │                                     │
     COIN INSERT ───────►│  ┌─────────────────────────────┐   │
                         │  │      VALIDATION UNIT        │   │
                         │  │                             │   │
                         │  │   ┌─────┐  ┌─────┐         │   │
                         │  │   │Size │  │Metal│         │   │
                         │  │   │Check│  │Check│         │   │
                         │  │   └──┬──┘  └──┬──┘         │   │
                         │  │      │        │            │   │
                         │  │      └────┬───┘            │   │
                         │  │           │                │   │
                         │  │      ┌────┴────┐           │   │
                         │  │      │ COMPARE │           │   │
                         │  │      │ SAMPLES │           │   │
                         │  │      └────┬────┘           │   │
                         │  │           │                │   │
                         │  └───────────┼────────────────┘   │
                         │              │                     │
                         │       ┌──────┴──────┐              │
                         │       │             │              │
                         │    ACCEPT        REJECT            │
                         │       │             │              │
                         │       ▼             ▼              │
                         │  ┌─────────┐  ┌─────────────┐     │
                         │  │ ACCEPT  │  │  REJECT     │     │
                         │  │ CHUTE   │  │  CHUTE      │     │
                         │  │         │  │  (Return)   │     │
                         │  └────┬────┘  └─────────────┘     │
                         │       │                            │
                         │       ▼                            │
                         │  ┌─────────┐                       │
                         │  │ SORTER  │ ──► To coin storage   │
                         │  └─────────┘     (gravity sort)    │
                         │                                     │
                         └─────────────────────────────────────┘


    WIRING (4-Wire Connection):
    ───────────────────────────

    ┌────────────────┬──────────────────┬─────────────────────────────────────┐
    │  Wire Color    │  Function        │  Connection                         │
    ├────────────────┼──────────────────┼─────────────────────────────────────┤
    │  RED           │  +12V DC         │  ATX +12V Rail                      │
    │  BLACK         │  GND             │  Common Ground                      │
    │  WHITE/GRAY    │  COIN (Pulse)    │  Arduino Digital Pin (Interrupt)   │
    │  YELLOW        │  COUNTER         │  Optional (for display counter)     │
    └────────────────┴──────────────────┴─────────────────────────────────────┘
```

### 5.2.2 Pulse Output Configuration

The coin acceptor outputs pulses to indicate which coin was accepted. Configure via DIP switches on the unit.

```
    PULSE CONFIGURATION (Recommended):
    ═══════════════════════════════════

    ┌─────────────┬────────────────┬───────────────────────────────────────────┐
    │    Coin     │  Pulses        │  Notes                                    │
    ├─────────────┼────────────────┼───────────────────────────────────────────┤
    │    ₱1       │  1 pulse       │  Base unit                                │
    │    ₱5       │  5 pulses      │  5× base                                  │
    │    ₱10      │  10 pulses     │  10× base                                 │
    │    ₱20      │  20 pulses     │  20× base                                 │
    └─────────────┴────────────────┴───────────────────────────────────────────┘

    Pulse Width: ~30-50ms typically
    Pulse Gap: ~30-50ms typically

    ALTERNATIVE (Unique pulses for easier detection):
    ┌─────────────┬────────────────┐
    │    ₱1       │  1 pulse       │
    │    ₱5       │  2 pulses      │
    │    ₱10      │  3 pulses      │
    │    ₱20      │  4 pulses      │
    └─────────────┴────────────────┘

    Then multiply by denomination value in software.
```

### 5.2.3 Wiring Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    COIN ACCEPTOR WIRING DIAGRAM                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

                           +12V (ATX)
                              │
                              │
                         ┌────┴────┐
                         │  RED    │
                         │  WIRE   │
                         └────┬────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │    COIN ACCEPTOR    │
                    │      (CH-926)       │
                    │                     │
                    │  RED ───── +12V     │
                    │  BLACK ─── GND ─────┼──────────┐
                    │  WHITE ─── COIN ────┼────┐     │
                    │  YELLOW ── COUNTER  │    │     │
                    │           (unused)  │    │     │
                    │                     │    │     │
                    └─────────────────────┘    │     │
                                               │     │
    ═══════════════════════════════════════════╪═════╪════════════════════
                        GND BUS                │     │
                                               │     │
                                               │     │
    ┌──────────────────────────────────────────┼─────┼────────────────────┐
    │                                          │     │                    │
    │                    ARDUINO MEGA          │     │                    │
    │                                          │     │                    │
    │    ┌─────────────────────────────────────┴─────┴────────────────┐   │
    │    │                                                            │   │
    │    │   D18 (Interrupt) ◄───────── COIN Pulse (WHITE wire)      │   │
    │    │                             (Use D18/D19/D20/D21 for INT)  │   │
    │    │                                                            │   │
    │    │   GND ──────────────────── Common Ground                   │   │
    │    │                                                            │   │
    │    └────────────────────────────────────────────────────────────┘   │
    │                                                                      │
    └──────────────────────────────────────────────────────────────────────┘


    NOTE: Use interrupt-capable pin for reliable pulse counting:

    Arduino Mega Interrupt Pins:
    ┌─────────┬───────────┐
    │  Pin    │  Interrupt│
    ├─────────┼───────────┤
    │  D2     │  INT0     │  (May be used for stepper)
    │  D3     │  INT1     │  (May be used for stepper)
    │  D18    │  INT5     │  ◄── RECOMMENDED for coin acceptor
    │  D19    │  INT4     │
    │  D20    │  INT3     │
    │  D21    │  INT2     │
    └─────────┴───────────┘
```

### 5.2.4 Coin Acceptor Arduino Code

```cpp
// Coin Acceptor - Arduino Code

#define COIN_PIN        18      // Interrupt pin
#define PULSE_TIMEOUT   150     // ms - time to wait for more pulses

volatile int pulseCount = 0;
volatile unsigned long lastPulseTime = 0;
unsigned long coinValue = 0;

void setup() {
    Serial.begin(115200);

    pinMode(COIN_PIN, INPUT_PULLUP);

    // Attach interrupt on falling edge
    attachInterrupt(digitalPinToInterrupt(COIN_PIN), coinPulseISR, FALLING);

    Serial.println("Coin Acceptor Ready");
}

// Interrupt Service Routine
void coinPulseISR() {
    pulseCount++;
    lastPulseTime = millis();
}

void loop() {
    // Check if we received pulses and timeout has passed
    if (pulseCount > 0 && (millis() - lastPulseTime > PULSE_TIMEOUT)) {
        // Disable interrupts while reading
        noInterrupts();
        int pulses = pulseCount;
        pulseCount = 0;
        interrupts();

        // Convert pulses to coin value
        int coinDenom = pulsesToDenomination(pulses);

        if (coinDenom > 0) {
            coinValue += coinDenom;

            // Send event to RPi
            Serial.print("{\"event\":\"COIN_IN\",\"denom\":\"PHP_");
            Serial.print(coinDenom);
            Serial.print("\",\"total\":");
            Serial.print(coinValue);
            Serial.println("}");
        }
    }

    // Handle other commands...
}

int pulsesToDenomination(int pulses) {
    // Adjust based on your coin acceptor configuration
    switch (pulses) {
        case 1:  return 1;    // ₱1
        case 5:  return 5;    // ₱5
        case 10: return 10;   // ₱10
        case 20: return 20;   // ₱20
        default: return 0;    // Invalid
    }
}

void resetCoinValue() {
    coinValue = 0;
}
```

---

## 5.3 Coin Dispenser System

### 5.3.1 Overview

The coin dispenser uses servo motors to release coins one at a time from storage tubes.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       COIN DISPENSER MECHANISM                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

    FRONT VIEW (4 Coin Tubes)
    ═════════════════════════

              ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐
              │ ₱1  │  │ ₱5  │  │ ₱10 │  │ ₱20 │
              │     │  │     │  │     │  │     │
              │ ○○○ │  │ ○○○ │  │ ○○○ │  │ ○○○ │   ◄── Coin stack
              │ ○○○ │  │ ○○○ │  │ ○○○ │  │ ○○○ │       (gravity fed)
              │ ○○○ │  │ ○○○ │  │ ○○○ │  │ ○○○ │
              │ ○○○ │  │ ○○○ │  │ ○○○ │  │ ○○○ │
              │ ○○○ │  │ ○○○ │  │ ○○○ │  │ ○○○ │
              └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘
                 │        │        │        │
              ┌──┴──┐  ┌──┴──┐  ┌──┴──┐  ┌──┴──┐
              │SERVO│  │SERVO│  │SERVO│  │SERVO│   ◄── Servo gate
              │  1  │  │  2  │  │  3  │  │  4  │
              └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘
                 │        │        │        │
                 └────────┴────┬───┴────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │  COIN TRAY  │   ◄── Collection tray
                        │  (Output)   │
                        └─────────────┘


    SIDE VIEW (Single Tube)
    ════════════════════════

                    ┌─────────┐
                    │ COIN    │
                    │ TUBE    │
                    │         │
                    │   ○     │  ◄── Coins stacked vertically
                    │   ○     │
                    │   ○     │
                    │   ○     │
                    │   ○     │
                    └────┬────┘
                         │
                    ┌────┴────┐
                    │  GATE   │
                    │ ┌─────┐ │
                    │ │█████│◄┼──── Servo arm (CLOSED position)
                    │ └─────┘ │
                    └────┬────┘
                         │
                         ▼
                    ┌─────────┐
                    │  DROP   │
                    │  CHUTE  │
                    └─────────┘


    GATE MECHANISM (Detail)
    ═══════════════════════

    CLOSED (0°):                      OPEN (90°):

    ┌─────────────┐                   ┌─────────────┐
    │     ○       │                   │     ○       │
    │     ○       │ Coin blocked      │     │       │ Coin falls
    │ ════█████   │                   │     ▼   ════│
    │             │                   │     ○       │
    └─────────────┘                   └─────────────┘

    Servo rotation allows bottom coin to fall through.
    Next coin is held by the gate when it returns to closed.
```

### 5.3.2 Servo Wiring

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       COIN SERVO WIRING DIAGRAM                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

    ┌───────────────────────────────────────────────────────────────────────────┐
    │                         EXTERNAL 5V POWER SUPPLY                          │
    │                            (5V 3A minimum)                                │
    │                                                                           │
    │   +5V ─────┬──────────┬──────────┬──────────┬────────────────────────    │
    │            │          │          │          │                             │
    │            │          │          │          │                             │
    │       ┌────┴───┐ ┌────┴───┐ ┌────┴───┐ ┌────┴───┐                        │
    │       │ Servo  │ │ Servo  │ │ Servo  │ │ Servo  │                        │
    │       │   1    │ │   2    │ │   3    │ │   4    │                        │
    │       │  (₱1)  │ │  (₱5)  │ │  (₱10) │ │  (₱20) │                        │
    │       │        │ │        │ │        │ │        │                        │
    │       │ RED────│ │ RED────│ │ RED────│ │ RED────│ ◄── VCC (Red)         │
    │       │ BRN────│ │ BRN────│ │ BRN────│ │ BRN────│ ◄── GND (Brown/Black) │
    │       │ ORG────│ │ ORG────│ │ ORG────│ │ ORG────│ ◄── Signal (Orange)   │
    │       └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘                        │
    │           │          │          │          │                             │
    │   GND ────┴──────────┴──────────┴──────────┴──────────┐                  │
    │                                                        │                  │
    └────────────────────────────────────────────────────────┼──────────────────┘
                                                             │
    ═════════════════════════════════════════════════════════╪══════════════════
                             GND BUS                         │
                                                             │
    ┌────────────────────────────────────────────────────────┼──────────────────┐
    │                                                        │                  │
    │                      ARDUINO MEGA                      │                  │
    │                                                        │                  │
    │    ┌───────────────────────────────────────────────────┴───────────────┐  │
    │    │                                                                   │  │
    │    │   D44 (PWM) ────────► Servo 1 Signal (₱1)                        │  │
    │    │   D45 (PWM) ────────► Servo 2 Signal (₱5)                        │  │
    │    │   D46 (PWM) ────────► Servo 3 Signal (₱10)                       │  │
    │    │   D2  (PWM) ────────► Servo 4 Signal (₱20)                       │  │
    │    │                       (D2 if stepper uses D3-D5)                  │  │
    │    │                                                                   │  │
    │    │   GND ──────────────► Common Ground (connect to servo GND bus)   │  │
    │    │                                                                   │  │
    │    └───────────────────────────────────────────────────────────────────┘  │
    │                                                                           │
    └───────────────────────────────────────────────────────────────────────────┘


    IMPORTANT NOTES:
    ════════════════

    1. DO NOT power servos from Arduino 5V pin!
       - Arduino can only supply ~500mA total from 5V pin
       - Each servo can draw 200-700mA under load
       - Use external 5V power supply (ATX +5V rail works well)

    2. COMMON GROUND is essential!
       - Connect Arduino GND to servo GND bus
       - Connect external 5V supply GND to same bus

    3. Servo Type Selection:
       - SG90: Small, plastic gears, ~1.8kg·cm torque
         Good for small coins, budget option
       - MG996R: Metal gears, ~10kg·cm torque
         Better for larger coins, more reliable

    4. Signal wire colors vary by manufacturer:
       - Most common: Orange or Yellow = Signal
       - Verify with your specific servo datasheet
```

### 5.3.3 Pin Assignment (Considering Sorting System)

Since the sorting system uses D2-D5, we need alternative PWM pins:

```
    REVISED PIN ASSIGNMENT:
    ═══════════════════════

    Bill Sorting (Stepper):
    - D2: STEP
    - D3: DIR
    - D4: ENABLE
    - D5: Limit Switch

    Coin Dispensing (Servos):
    - D44 (PWM): Servo 1 (₱1)
    - D45 (PWM): Servo 2 (₱5)
    - D46 (PWM): Servo 3 (₱10)
    - D6  (PWM): Servo 4 (₱20)

    Note: Arduino Mega PWM pins: 2-13, 44-46
```

### 5.3.4 Coin Dispenser Arduino Code

```cpp
// Coin Dispenser - Arduino Code

#include <Servo.h>

// Servo objects
Servo servo1;  // ₱1
Servo servo2;  // ₱5
Servo servo3;  // ₱10
Servo servo4;  // ₱20

// Pin definitions
#define SERVO1_PIN  44
#define SERVO2_PIN  45
#define SERVO3_PIN  46
#define SERVO4_PIN  6

// Servo positions
#define SERVO_CLOSED  0
#define SERVO_OPEN    90

// Timing
#define SERVO_OPEN_TIME   150   // ms - time gate stays open
#define SERVO_SETTLE_TIME 100   // ms - time for coin to drop

// Coin dispenser structure
struct CoinDispenser {
    Servo* servo;
    int denomination;
    String name;
};

CoinDispenser coinDispensers[4];

void setupCoinDispensers() {
    // Attach servos to pins
    servo1.attach(SERVO1_PIN);
    servo2.attach(SERVO2_PIN);
    servo3.attach(SERVO3_PIN);
    servo4.attach(SERVO4_PIN);

    // Initialize dispenser array
    coinDispensers[0] = {&servo1, 1,  "PHP_1"};
    coinDispensers[1] = {&servo2, 5,  "PHP_5"};
    coinDispensers[2] = {&servo3, 10, "PHP_10"};
    coinDispensers[3] = {&servo4, 20, "PHP_20"};

    // Set all to closed position
    for (int i = 0; i < 4; i++) {
        coinDispensers[i].servo->write(SERVO_CLOSED);
    }

    delay(500);  // Allow servos to reach position
}
```

### 5.3.5 Dispense Function

```cpp
struct CoinDispenseResult {
    bool success;
    int dispensed;
    String error;
};

// Find dispenser by denomination
int findCoinDispenser(int denomination) {
    for (int i = 0; i < 4; i++) {
        if (coinDispensers[i].denomination == denomination) {
            return i;
        }
    }
    return -1;
}

// Dispense single coin
void dispenseSingleCoin(int dispenserIndex) {
    Servo* servo = coinDispensers[dispenserIndex].servo;

    // Open gate
    servo->write(SERVO_OPEN);
    delay(SERVO_OPEN_TIME);

    // Close gate
    servo->write(SERVO_CLOSED);
    delay(SERVO_SETTLE_TIME);
}

// Dispense multiple coins
CoinDispenseResult dispenseCoins(int denomination, int count) {
    CoinDispenseResult result = {true, 0, ""};

    int dispenserIndex = findCoinDispenser(denomination);

    if (dispenserIndex < 0) {
        result.success = false;
        result.error = "INVALID_DENOM";
        return result;
    }

    for (int i = 0; i < count; i++) {
        dispenseSingleCoin(dispenserIndex);
        result.dispensed++;
    }

    return result;
}

// Calculate optimal coin combination for change
void calculateChange(int amount, int* coins) {
    // coins[0] = ₱20, coins[1] = ₱10, coins[2] = ₱5, coins[3] = ₱1

    coins[0] = amount / 20;
    amount %= 20;

    coins[1] = amount / 10;
    amount %= 10;

    coins[2] = amount / 5;
    amount %= 5;

    coins[3] = amount;
}

// Dispense change amount
CoinDispenseResult dispenseChange(int amount) {
    CoinDispenseResult result = {true, 0, ""};

    int coins[4];
    calculateChange(amount, coins);

    // Dispense ₱20 coins
    for (int i = 0; i < coins[0]; i++) {
        dispenseSingleCoin(3);
        result.dispensed++;
    }

    // Dispense ₱10 coins
    for (int i = 0; i < coins[1]; i++) {
        dispenseSingleCoin(2);
        result.dispensed++;
    }

    // Dispense ₱5 coins
    for (int i = 0; i < coins[2]; i++) {
        dispenseSingleCoin(1);
        result.dispensed++;
    }

    // Dispense ₱1 coins
    for (int i = 0; i < coins[3]; i++) {
        dispenseSingleCoin(0);
        result.dispensed++;
    }

    return result;
}
```

### 5.3.6 Command Handler

```cpp
void handleCoinCommand(String command) {
    if (command.indexOf("COIN_DISP") > 0) {
        // Format: {"cmd":"COIN_DISP","denom":5,"count":3}

        int denomStart = command.indexOf("denom") + 7;
        int denomEnd = command.indexOf(",", denomStart);
        int denom = command.substring(denomStart, denomEnd).toInt();

        int countStart = command.indexOf("count") + 7;
        int countEnd = command.indexOf("}", countStart);
        int count = command.substring(countStart, countEnd).toInt();

        CoinDispenseResult result = dispenseCoins(denom, count);

        if (result.success) {
            Serial.print("{\"status\":\"OK\",\"dispensed\":");
            Serial.print(result.dispensed);
            Serial.println("}");
        } else {
            Serial.print("{\"status\":\"ERROR\",\"code\":\"");
            Serial.print(result.error);
            Serial.println("\"}");
        }
    }
    else if (command.indexOf("COIN_CHANGE") > 0) {
        // Format: {"cmd":"COIN_CHANGE","amount":47}

        int amountStart = command.indexOf("amount") + 8;
        int amountEnd = command.indexOf("}", amountStart);
        int amount = command.substring(amountStart, amountEnd).toInt();

        CoinDispenseResult result = dispenseChange(amount);

        Serial.print("{\"status\":\"OK\",\"dispensed\":");
        Serial.print(result.dispensed);
        Serial.print(",\"amount\":");
        Serial.print(amount);
        Serial.println("}");
    }
}
```

---

## 5.4 Timing Specifications

### Coin Acceptor

| Event                    | Duration | Notes                   |
| ------------------------ | -------- | ----------------------- |
| Coin validation          | ~500ms   | Internal to module      |
| Pulse width              | 30-50ms  | Per pulse               |
| Pulse gap                | 30-50ms  | Between pulses          |
| Timeout after last pulse | 150ms    | To determine coin value |

### Coin Dispenser

| Operation                | Duration         | Notes                       |
| ------------------------ | ---------------- | --------------------------- |
| Servo open               | 150ms            | Gate open time              |
| Servo close + settle     | 100ms            | Coin drop time              |
| **Single coin dispense** | **~250ms**       |                             |
| **47 peso change**       | **~2.5 seconds** | 2×₱20 + 0×₱10 + 1×₱5 + 2×₱1 |

---

## 5.5 Complete Pin Summary (Coin System)

| Pin | Function            | Notes          |
| --- | ------------------- | -------------- |
| D18 | Coin Acceptor Pulse | Interrupt INT5 |
| D44 | Servo 1 (₱1)        | PWM            |
| D45 | Servo 2 (₱5)        | PWM            |
| D46 | Servo 3 (₱10)       | PWM            |
| D6  | Servo 4 (₱20)       | PWM            |

---

_Document 5 of 10 - Coinnect System Architecture_
