# Coinnect System Architecture

## 06 - Security System

**Document Version:** 2.1  
**Date:** February 2026  
**Controller:** Arduino Mega #2 (Coin & Security Controller) via `/dev/ttyACM0`

---

## 6.1 Overview

The security system protects the kiosk from unauthorized access and tampering.

**Components:**

- 2x Shock/Vibration Sensors (SW-420)
- 1x Solenoid Lock (12V DC)
- 1x 5V Relay Module
- 1x Flyback Diode (1N4007)
- 2x LED Indicators (Red, Green)
- 1x USB RFID Reader (Connected to RPi)
- 1x Bill Storage Lid Motor (TBD - to be determined)

**Security Features:**

- **RFID-based maintenance access** (Authentication handled by RPi)
- Tamper detection via shock sensors
- Automatic lockdown on tamper event
- LED status indicators
- Event logging to Raspberry Pi

---

## 6.2 System Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          SECURITY SYSTEM OVERVIEW                                │
└─────────────────────────────────────────────────────────────────────────────────┘

                                KIOSK ENCLOSURE
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                                                                          │
    │     ┌─────────────┐                           ┌─────────────┐           │
    │     │  SHOCK      │                           │  SHOCK      │           │
    │     │  SENSOR A   │                           │  SENSOR B   │           │
    │     │  (Door)     │                           │  (Cabinet)  │           │
    │     └──────┬──────┘                           └──────┬──────┘           │
    │            │                                         │                  │
    │            │         BILL STORAGE AREA               │                  │
    │            │    ┌─────────────────────────┐         │                  │
    │            │    │  ╔═════════════════╗    │         │                  │
    │            │    │  ║   BILL BOXES    ║    │         │                  │
    │            │    │  ║   [SECURED]     ║    │         │                  │
    │            │    │  ╚═════════════════╝    │         │                  │
    │            │    │          │              │         │                  │
    │            │    │    ┌─────┴─────┐        │         │                  │
    │            │    │    │ LID MOTOR │        │         │                  │
    │            │    │    │   (TBD)   │        │         │                  │
    │            │    │    └───────────┘        │         │                  │
    │            │    └─────────────────────────┘         │                  │
    │            │                                         │                  │
    │            └─────────────────┬───────────────────────┘                  │
    │                              │                                          │
    │                              ▼                                          │
    │                       ┌─────────────┐                                   │
    │                       │   ARDUINO   │                                   │
    │                       │    MEGA     │                                   │
    │                       └──────┬──────┘                                   │
    │                              │                                          │
    │      ┌───────────────────────┼───────────────────────┐                  │
    │      │                       │                       │                  │
    │      ▼                       ▼                       ▼                  │
    │ ┌─────────┐            ┌──────────┐            ┌─────────┐             │
    │ │ RFID(RPi)            │ SOLENOID │            │  LEDs   │             │
    │ │CONTROLLED            │  LOCK    │            │ RED/GRN │             │
    │ └─────────┘            └──────────┘            └─────────┘             │
    │                              │                                          │
    │                        ┌─────┴─────┐                                    │
    │                        │   DOOR    │                                    │
    │                        │  ACCESS   │                                    │
    │                        └───────────┘                                    │
    │                                                                          │
    │      (RFID Reader connects DIRECTLY to Raspberry Pi via USB)             │
    └──────────────────────────────────────────────────────────────────────────┘
```

---

## 6.3 Shock Sensor Circuit

### 6.3.1 SW-420 Vibration Sensor

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       SHOCK SENSOR (SW-420) DETAILS                              │
└─────────────────────────────────────────────────────────────────────────────────┘

    SW-420 MODULE PINOUT:
    ═════════════════════

    ┌───────────────────────────────────┐
    │         SW-420 Module             │
    │                                   │
    │   ┌─────────────────────────┐    │
    │   │    ┌─────┐              │    │
    │   │    │     │ Sensitivity  │    │   Adjust for desired
    │   │    │  ◯  │ Potentiometer│    │   trigger threshold
    │   │    │     │              │    │
    │   │    └─────┘              │    │
    │   │                         │    │
    │   │   ┌───┐                 │    │
    │   │   │ L │ LED Indicator   │    │   Lights when triggered
    │   │   └───┘                 │    │
    │   │                         │    │
    │   └─────────────────────────┘    │
    │                                   │
    │     VCC   GND   DO                │
    │      │     │     │                │
    │      ●     ●     ●                │
    └──────┼─────┼─────┼────────────────┘
           │     │     │
           │     │     │
           │     │     └───────────────► Digital Output
           │     │                       (HIGH = no vibration)
           │     │                       (LOW = vibration detected)
           │     │
           │     └─────────────────────► GND
           │
           └───────────────────────────► +5V (3.3V-5V)


    OPERATING PRINCIPLE:
    ════════════════════

    The SW-420 contains a spring-loaded conductive element
    that makes/breaks contact when vibration occurs.

    Normal State:      Triggered:
    ┌─────────┐       ┌─────────┐
    │    │    │       │    /    │
    │    │    │  ──►  │   /     │
    │    ●    │       │  ●      │
    └─────────┘       └─────────┘
     Contact           Contact
     Closed            Open
```

### 6.3.2 Shock Sensor Wiring

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       SHOCK SENSOR WIRING DIAGRAM                                │
└─────────────────────────────────────────────────────────────────────────────────┘

                            +5V (Arduino/ATX)
                               │
                 ┌─────────────┼─────────────┐
                 │             │             │
                 │             │             │
           ┌─────┴─────┐ ┌─────┴─────┐      │
           │  SW-420   │ │  SW-420   │      │
           │ SENSOR A  │ │ SENSOR B  │      │
           │  (Door)   │ │ (Cabinet) │      │
           │           │ │           │      │
           │  VCC  ────│ │  VCC  ────│      │
           │  GND  ────│ │  GND  ────│      │
           │  DO   ────│ │  DO   ────│      │
           └───────┬───┘ └───────┬───┘      │
                   │             │          │
                   │             │          │
    ═══════════════╪═════════════╪══════════╪════════════════════
                   │             │          │
               GND BUS           │          │
                                 │          │
    ┌────────────────────────────┼──────────┼────────────────────┐
    │                            │          │                    │
    │         ARDUINO MEGA       │          │                    │
    │                            │          │                    │
    │   ┌────────────────────────┴──────────┴─────────────────┐  │
    │   │                                                     │  │
    │   │   D19 ◄────────────────────── Sensor A DO           │  │
    │   │                               (Use interrupt INT4)  │  │
    │   │                                                     │  │
    │   │   D20 ◄────────────────────── Sensor B DO           │  │
    │   │                               (Use interrupt INT3)  │  │
    │   │                                                     │  │
    │   │   GND ───────────────────────  Common Ground        │  │
    │   │                                                     │  │
    │   │   5V  ───────────────────────  Sensor VCC           │  │
    │   │                                                     │  │
    │   └─────────────────────────────────────────────────────┘  │
    │                                                            │
    └────────────────────────────────────────────────────────────┘


    PLACEMENT RECOMMENDATIONS:
    ══════════════════════════

    Sensor A: Mount on access door frame
              - Detects door forced open
              - Detects impacts on door

    Sensor B: Mount on main cabinet interior
              - Detects drilling attempts
              - Detects prying/levering
              - Detects kiosk being moved
```

---

## 6.4 Solenoid Lock Circuit

### 6.4.1 Overview

The solenoid lock secures the maintenance access door. It requires a relay to switch the 12V supply since Arduino GPIO cannot handle the current.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       SOLENOID LOCK CIRCUIT                                      │
└─────────────────────────────────────────────────────────────────────────────────┘

                                 +12V (ATX)
                                    │
                                    │
                              ┌─────┴─────┐
                              │  SOLENOID │
                              │   LOCK    │
                              │           │
                              │  ┌─────┐  │
                              │  │     │  │
                              │  │ ▓▓▓ │  │ ◄── Plunger (retracts when powered)
                              │  │     │  │
                              │  └─────┘  │
                              │           │
                              │  (+) (-) │
                              └───┬───┬───┘
                                  │   │
                                  │   │
         ┌────────────────────────┤   │
         │                        │   │
         │   ┌────────────────────┘   │
         │   │                        │
         │   │      FLYBACK DIODE     │
         │   │      ┌─────────┐       │
         │   │      │  1N4007 │       │
         │   └──────┤ ◄───────├───────┘
         │          │    K  A │
         │          └─────────┘
         │                │
         │                │
         │          ┌─────┴─────┐
         │          │   RELAY   │
         │          │  MODULE   │
         │          │           │
         │          │  ┌─────┐  │
         │          │  │ COM ├──┼──────► +12V
         │          │  │     │  │
         │          │  │ NO  ├──┼──────► Solenoid (+)
         │          │  │     │  │
         │          │  │ NC  │  │        (Not used)
         │          │  └─────┘  │
         │          │           │
         │          │  VCC  ────┼──────► +5V
         │          │  GND  ────┼──────► GND
         │          │  IN   ────┼──────► Arduino D21
         │          │           │
         │          └───────────┘
         │
    ═════╪════════════════════════════════════════════════════════
         │
       GND BUS


    OPERATION:
    ══════════

    Arduino D21 = LOW  → Relay OFF → Solenoid unpowered → Door LOCKED
    Arduino D21 = HIGH → Relay ON  → Solenoid powered   → Door UNLOCKED


    FLYBACK DIODE PURPOSE:
    ══════════════════════

    When the relay turns OFF, the solenoid's magnetic field collapses,
    generating a high-voltage spike (back-EMF) that can damage components.

    The flyback diode (1N4007) provides a safe path for this energy:

    Normal:                      Relay OFF:
    ┌─────┐                      ┌─────┐
    │     │                      │     │
    │  ↓  │ Current flows        │  ↑  │ Back-EMF
    │     │ through solenoid     │     │ absorbed by diode
    └─────┘                      └─────┘

    IMPORTANT: Install diode with cathode (K) toward +12V
```

### 6.4.2 Solenoid Lock Wiring Detail

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SOLENOID LOCK COMPLETE WIRING                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

                                        +12V (ATX Yellow Wire)
                                             │
                                             │
                                        ┌────┴────┐
                                        │         │
                                        │   COM   │
                                        │    ●    │
                                   ┌────┤  RELAY  ├────┐
                                   │    │ MODULE  │    │
                               NC   │    │    ●    │    │   NO
                           (unused)│    │   IN    │    │
                                   │    └────┬────┘    │
                                   │         │        │
                                   │         │        │
                                   │    To Arduino    │
                                   │       D21        │
                                   │                  │
                                   │                  │
                                   │    ┌─────────────┘
                                   │    │
                                   │    │        ┌───────────────┐
                                   │    │        │   SOLENOID    │
                                   │    │        │     LOCK      │
                                   │    │        │               │
                                   │    └────────┤ (+) Terminal  │
                                   │             │               │
                                   │    ┌────────┤ (-) Terminal  │
                                   │    │        │               │
                                   │    │        └───────────────┘
                                   │    │               │
                                   │    │               │
                                   │    │    ┌──────────┘
                                   │    │    │
                                   │    │    │   1N4007
                                   │    │    │  ┌─────┐
                                   │    └────┼──┤  ◄──├─────────┐
                                   │         │  └─────┘         │
                                   │         │    K   A         │
                                   │         │                  │
    ═══════════════════════════════╪═════════╪══════════════════╪═════
                                   │         │                  │
                                 GND       GND              (to +12V)


    RELAY MODULE CONNECTIONS:
    ═════════════════════════

    ┌────────────────────────────────────────────────────────────────────┐
    │  Relay Pin    │  Connection                                        │
    ├───────────────┼────────────────────────────────────────────────────┤
    │  VCC          │  +5V (Arduino 5V or ATX 5V)                        │
    │  GND          │  Common Ground                                      │
    │  IN           │  Arduino D21 (control signal)                      │
    │  COM          │  +12V (ATX Yellow wire)                            │
    │  NO           │  Solenoid (+) terminal                             │
    │  NC           │  Not connected                                      │
    └───────────────┴────────────────────────────────────────────────────┘
```

---

## 6.5 LED Indicators

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       LED INDICATOR WIRING                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

                                 Arduino
                               ┌─────────┐
                               │         │
                               │   D22 ──┼────────┐
                               │         │        │
                               │   D23 ──┼────┐   │
                               │         │    │   │
                               │   GND ──┼──┐ │   │
                               │         │  │ │   │
                               └─────────┘  │ │   │
                                            │ │   │
                                            │ │   │
                                       ┌────┼─┼───┴─────────────┐
                                       │    │ │                 │
    GND Bus ═══════════════════════════╪════╪═╪═════════════════╪════
                                       │    │ │                 │
                                       │    │ │    ┌───────┐    │
                                       │    │ └────┤  220Ω ├────┘
                                       │    │      └───────┘
                                       │    │          │
                                       │    │          │
                                       │    │     ┌────┴────┐
                                       │    │     │   RED   │
                                       │    │     │   LED   │
                                       │    │     │    ▼    │
                                       │    │     └────┬────┘
                                       │    │          │
                                       │    │          │
                                       ├────┼──────────┘
                                       │    │
                                       │    │      ┌───────┐
                                       │    └──────┤  220Ω ├────┐
                                       │           └───────┘    │
                                       │               │        │
                                       │               │        │
                                       │          ┌────┴────┐   │
                                       │          │  GREEN  │   │
                                       │          │   LED   │   │
                                       │          │    ▼    │   │
                                       │          └────┬────┘   │
                                       │               │        │
                                       │               │        │
                                       └───────────────┴────────┘


    LED STATES:
    ═══════════

    ┌─────────────────────┬─────────────┬────────────────────────────────────┐
    │  System State       │  Red  Green │  Description                       │
    ├─────────────────────┼─────────────┼────────────────────────────────────┤
    │  Normal/Locked      │  ON    OFF  │  Door secured                      │
    │  Unlocked           │  OFF   ON   │  Access granted (by RPi)           │
    │  Tamper Alert       │  BLINK OFF  │  Security breach detected          │
    └─────────────────────┴─────────────┴────────────────────────────────────┘
```

---

## 6.6 Bill Storage Lid Motor (TBD)

The bill storage lid motor provides an additional layer of security by physically blocking access to stored bills during tamper events.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    BILL STORAGE LID MOTOR (To Be Determined)                     │
└─────────────────────────────────────────────────────────────────────────────────┘

    OPTION A: DC Motor with Limit Switches
    ═══════════════════════════════════════

    Pros:
    - Simple control (L298N)
    - Fast operation
    - Good torque

    Cons:
    - Needs limit switches for position
    - Can overshoot
    - Requires more wiring

    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │   [LIMIT A]──────────────────────────────────[LIMIT B]         │
    │       │                LID                       │              │
    │       │     ╔═══════════════════════════╗       │              │
    │       ●─────║▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓║───────●              │
    │             ╚═══════════════════════════╝                       │
    │                         │                                       │
    │                    [DC MOTOR]                                   │
    │                         │                                       │
    │                    ┌────┴────┐                                  │
    │                    │  L298N  │                                  │
    │                    └─────────┘                                  │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘


    OPTION B: Servo Motor
    ═════════════════════

    Pros:
    - Built-in position control
    - No limit switches needed
    - Precise movement

    Cons:
    - Limited rotation (180° standard)
    - May need high-torque servo
    - Slower than DC motor

    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │                         LID                                     │
    │             ╔═══════════════════════════╗                       │
    │      ┌──────║▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓║                       │
    │      │      ╚═══════════════════════════╝                       │
    │  ┌───┴───┐                                                      │
    │  │ SERVO │                                                      │
    │  │(MG996R│                                                      │
    │  └───────┘                                                      │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘


    OPTION C: Linear Actuator
    ═════════════════════════

    Pros:
    - Strong linear force
    - Good for sliding lid
    - Self-locking when stopped

    Cons:
    - More expensive
    - Bulkier
    - Slower operation

    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │      ╔═══════════════════════════╗                              │
    │      ║         LID               ║◄──────────┐                  │
    │      ╚═══════════════════════════╝           │                  │
    │                                    ┌─────────┴─────────┐        │
    │                                    │  LINEAR ACTUATOR  │        │
    │                                    │  ═══════════●     │        │
    │                                    └───────────────────┘        │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘


    RECOMMENDATION:
    ═══════════════
    For simplicity and reliability, Option B (Servo Motor) is recommended
    for a prototype. Use MG996R or similar high-torque metal gear servo.

    Final decision pending mechanical design review.
```

---

## 6.7 Arduino Security Code

### 6.7.1 Setup and Pin Definitions

```cpp
// Security System - Arduino Code

// Pin Definitions
#define SHOCK_A_PIN     19    // INT4
#define SHOCK_B_PIN     20    // INT3
#define SOLENOID_PIN    21
#define LED_RED_PIN     22
#define LED_GREEN_PIN   23

// Security state
volatile bool tamperDetected = false;
bool doorUnlocked = false;

void setup() {
    Serial.begin(115200);

    // Pin modes
    pinMode(SHOCK_A_PIN, INPUT_PULLUP);
    pinMode(SHOCK_B_PIN, INPUT_PULLUP);
    pinMode(SOLENOID_PIN, OUTPUT);
    pinMode(LED_RED_PIN, OUTPUT);
    pinMode(LED_GREEN_PIN, OUTPUT);

    // Initial state
    digitalWrite(SOLENOID_PIN, LOW);   // Locked
    digitalWrite(LED_RED_PIN, HIGH);   // Red ON
    digitalWrite(LED_GREEN_PIN, LOW);  // Green OFF

    // Attach interrupts for shock sensors
    attachInterrupt(digitalPinToInterrupt(SHOCK_A_PIN), shockISR_A, FALLING);
    attachInterrupt(digitalPinToInterrupt(SHOCK_B_PIN), shockISR_B, FALLING);

    Serial.println("Security System Ready");
}
```

### 6.7.2 Interrupt Handlers

```cpp
void shockISR_A() {
    tamperDetected = true;
}

void shockISR_B() {
    tamperDetected = true;
}
```

### 6.7.3 Security Functions

```cpp
void lockDoor() {
    digitalWrite(SOLENOID_PIN, LOW);
    doorUnlocked = false;
    digitalWrite(LED_RED_PIN, HIGH);
    digitalWrite(LED_GREEN_PIN, LOW);
    Serial.println("{\"event\":\"DOOR_LOCKED\"}");
}

void unlockDoor() {
    digitalWrite(SOLENOID_PIN, HIGH);
    doorUnlocked = true;
    digitalWrite(LED_RED_PIN, LOW);
    digitalWrite(LED_GREEN_PIN, HIGH);
    Serial.println("{\"event\":\"DOOR_UNLOCKED\"}");
}

void handleTamper(String sensor) {
    // Log tamper event
    Serial.print("{\"event\":\"TAMPER\",\"sensor\":\"");
    Serial.print(sensor);
    Serial.println("\"}");

    // Immediately lock door if open
    lockDoor();

    // Activate bill storage lid (if implemented)
    // closeBillStorageLid();

    // Flash red LED rapidly
    for (int i = 0; i < 10; i++) {
        digitalWrite(LED_RED_PIN, HIGH);
        delay(100);
        digitalWrite(LED_RED_PIN, LOW);
        delay(100);
    }
    digitalWrite(LED_RED_PIN, HIGH);

    tamperDetected = false;
}

// NOTE: checkPIN() removed; Access control is now handled by RPi via Serial commands.
```

### 6.7.4 Main Loop

```cpp
// Main loop processes serial commands from RPi for locking/unlocking
// and checks for tamper events.

void loop() {
    // Check for tamper
    if (tamperDetected) {
        handleTamper("SHOCK");
    }

    // Serial command processing (Simplified)
    // if serial available -> read JSON -> if cmd == "SECURITY_UNLOCK" -> unlockDoor()
}
```
