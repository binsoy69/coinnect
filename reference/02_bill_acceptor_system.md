# Coinnect System Architecture

## 02 - Bill Acceptor System

**Document Version:** 2.0  
**Date:** February 2026  
**Controller:** Raspberry Pi 4/5

---

## 2.1 Overview

The bill acceptor system is entirely controlled by the Raspberry Pi to minimize latency during bill authentication. This eliminates serial communication overhead between the Pi and Arduino during the time-critical authentication process.

**Components:**

- 1x DC Motor (12V) - Bill conveyor
- 1x L298N Motor Driver
- 2x IR Obstacle Sensors (FC-51)
- 1x USB Camera (1080p minimum)
- 1x UV LED Strip (365-395nm)
- 1x Single White LED
- 1x 5V Relay Module (for UV LED control)
- 1x N-Channel MOSFET (for White LED control)

---

## 2.2 System Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        BILL ACCEPTOR SYSTEM (RPi Controlled)                     │
└─────────────────────────────────────────────────────────────────────────────────┘

                              RASPBERRY PI 4/5
                         ┌─────────────────────────┐
                         │                         │
      USB Camera ────────┤ USB Port                │
                         │                         │
                         │ GPIO PINS               │
                         │                         │
                         │ GPIO17 ────────────────►│─── L298N IN1 (Motor Dir 1)
                         │ GPIO27 ────────────────►│─── L298N IN2 (Motor Dir 2)
                         │ GPIO22 ────────────────►│─── L298N ENA (PWM Enable)
                         │                         │
                         │ GPIO5  ◄────────────────│─── IR Sensor 1 (Bill Entry)
                         │ GPIO6  ◄────────────────│─── IR Sensor 2 (Position)
                         │                         │
                         │ GPIO23 ────────────────►│─── UV LED (via Relay)
                         │ GPIO24 ────────────────►│─── White LED (via MOSFET)
                         │                         │
                         │ 5V  ───────────────────►│─── Sensor VCC
                         │ GND ───────────────────►│─── Common Ground
                         │                         │
                         └─────────────────────────┘


                         BILL ACCEPTOR PHYSICAL LAYOUT

    ┌──────────────────────────────────────────────────────────────────────────┐
    │                                                                          │
    │   BILL ENTRY                          CAMERA STATION              EXIT   │
    │      SLOT                                                       TO SORT  │
    │                                                                          │
    │      ║                                                            ║      │
    │      ║    ┌────┐                    ┌─────────┐               ┌────┐     │
    │  ════╬════│ IR │════════════════════│ CAMERA  │═══════════════│    │═══► │
    │      ║    │ #1 │    CONVEYOR BELT   │  ABOVE  │               │    │     │
    │      ║    └────┘         ▲          └─────────┘               └────┘     │
    │      ║                   │               │                               │
    │      ║              ┌────┴────┐     ┌────┴────┐                          │
    │      ║              │  MOTOR  │     │UV + LED │                          │
    │      ║              │  ROLLER │     │  PANEL  │                          │
    │      ║              └─────────┘     └─────────┘                          │
    │      ║                                   │                               │
    │      ║                              ┌────┴────┐                          │
    │      ║                              │  IR #2  │                          │
    │      ║                              │(Position│                          │
    │      ║                              └─────────┘                          │
    │                                                                          │
    └──────────────────────────────────────────────────────────────────────────┘
```

---

## 2.3 Wiring Diagrams

### 2.3.1 L298N Motor Driver Connection to RPi

```
                         L298N MOTOR DRIVER
                    ┌─────────────────────────┐
                    │                         │
      DC Motor  ────┤ OUT1              +12V ├───── 12V (ATX +12V Rail)
      (Red)     ────┤ OUT2               GND ├───── Common Ground
                    │                         │
                    │ OUT3        (unused)    │
                    │ OUT4                    │
                    │                         │
  RPi GPIO17 ──────►│ IN1               ENA ├◄──── RPi GPIO22 (PWM)
  RPi GPIO27 ──────►│ IN2               ENB │      (Remove jumper)
                    │ IN3                    │
                    │ IN4                    │
                    │                         │
                    │              +5V (out) ├───── (Do NOT use - power RPi separately)
                    │                         │
                    └─────────────────────────┘

    IMPORTANT NOTES:
    ─────────────────
    • Remove the ENA jumper to enable PWM speed control
    • Connect RPi GND to L298N GND (common ground)
    • Do NOT power RPi from L298N's 5V output
    • Add 100µF capacitor near L298N 12V input
```

### 2.3.2 IR Sensor Connections

```
                    IR OBSTACLE SENSOR

    Sensor #1 (Bill Entry)              Sensor #2 (Bill Position)
    ┌─────────────────────┐             ┌─────────────────────┐
    │                     │             │                     │
    │                     │             │                     │
    │  VCC ───── 5V       │             │  VCC ───── 5V       │
    │  GND ───── GND      │             │  GND ───── GND      │
    │  OUT ───── GPIO5    │             │  OUT ───── GPIO6    │
    │                     │             │                     │
    │   [Sensitivity Pot] │             │   [Sensitivity Pot] │
    │         ◯           │             │         ◯           │
    └─────────────────────┘             └─────────────────────┘


    OUTPUT LOGIC:
    ─────────────
    • HIGH (5V) = No obstacle detected (no bill)
    • LOW  (0V)   = Obstacle detected (bill present)
```

### 2.3.3 LED Control (Relay & MOSFET)

```
    UV LED (RELAY) AND WHITE LED (MOSFET) CONTROL CIRCUIT

    • UV LED: Controlled via a 5V Relay Module to handle the UV Strip.
    • White LED: A single high-brightness LED controlled via N-Channel MOSFET.


                    UV LED CIRCUIT (RELAY)              WHITE LED CIRCUIT (MOSFET)

    +12V ─────────────┐                                +12V ─────────────┐
                      │                                                  │
                 ┌────┴─────┐                                       ┌────┴─────┐
                 │  RELAY   │                                       │ Resistor │
                 │ (COM/NO) │                                       └────┬─────┘
                 └────┬─────┘                                            │
                      │                                             ┌────┴─────┐
                 ┌────┴─────┐                                       │  SINGLE  │
                 │  UV LED  │                                       │ WHITE LED│
                 │  STRIP   │                                       └────┬─────┘
                 └────┬─────┘                                            │
                      │                                             ┌────┴────┐
    GND ──────────────┴───────────┐                                 │ MOSFET  │
                                  │                                 │ IRLZ44N │
                                  │                                 └────┬────┘
    RPi GPIO23 ──► Relay IN       │                                      │
    RPi 5V     ──► Relay VCC      │            RPi GPIO24 ─── 1kΩ ───────┤
    RPi GND    ──► Relay GND      └────────────── GND ───────────────────┴────


    RELAY MODULE CONNECTIONS:              MOSFET PINOUT (IRLZ44N):
    ┌──────────────────────────┐           ┌─────────────┐
    │ VCC ──► RPi 5V           │           │   IRLZ44N   │
    │ GND ──► RPi GND          │           │             │
    │ IN  ──► RPi GPIO23       │           │  G   D   S  │
    │                          │           │  │   │   │  │
    │ COM ──► +12V             │           └──┼───┼───┼──┘
    │ NO  ──► UV LED (+)       │              │   │   │
    └──────────────────────────┘            Gate Drain Source

    Note: Most relay modules are active-LOW. If using typical modules,
    GPIO.LOW will turn the relay ON. Adjust software accordingly.
```

### 2.3.4 USB Camera Connection

```
    USB CAMERA CONNECTION

    ┌─────────────────────┐              ┌─────────────────────┐
    │   RASPBERRY PI      │              │    USB CAMERA       │
    │                     │              │   (1080p, Autofocus)│
    │                     │              │                     │
    │   USB 3.0 Port ─────┼──────────────┤   USB Cable         │
    │   (Blue)            │              │                     │
    │                     │              │   Recommended:      │
    │                     │              │   • Logitech C920   │
    │                     │              │   • Generic 1080p   │
    │                     │              │     with good       │
    │                     │              │     low-light       │
    └─────────────────────┘              └─────────────────────┘

    CAMERA REQUIREMENTS:
    ────────────────────
    • Resolution: 1080p (1920x1080) minimum
    • Autofocus or fixed focus at ~15-20cm distance
    • Good low-light performance (for UV capture)
    • Linux/V4L2 compatible

    MOUNTING POSITION:
    ──────────────────
    • Distance from bill: 15-20cm
    • Angle: Perpendicular to bill surface
    • Ensure entire bill is in frame (170mm x 77mm for PHP)
```

---

## 2.4 Complete Wiring Schematic

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    BILL ACCEPTOR - COMPLETE WIRING DIAGRAM                       │
└─────────────────────────────────────────────────────────────────────────────────┘

                                                         +12V (ATX)
                                                            │
         ┌──────────────────────────────────────────────────┼────────────────┐
         │                                                  │                │
         │    ┌─────────────────────────────────────────────┤                │
         │    │                                             │                │
         │    │         ┌───────────────────────────────────┤                │
         │    │         │                                   │                │
         │    │         │         ┌─────────────────────────┤                │
         │    │         │         │                         │                │
         │    │         │         │                    ┌────┴────┐           │
         │    │         │         │                    │  L298N  │           │
         │    │         │         │                    │         │           │
         │    │         │         │    ┌───────────────┤OUT1     │           │
         │    │         │         │    │    DC MOTOR   │OUT2     │           │
         │    │         │         │    │    ┌─────┐    │         │           │
         │    │         │         │    └────┤  M  ├────┘         │           │
         │    │         │         │         └─────┘              │           │
         │    │         │         │                               │           │
         │    │         │         │                               │           │
         │    │         │    ┌────┴────┐                    ┌────┴────┐      │
         │    │         │    │  RELAY  │                    │Resistor │      │
         │    │         │    │(COM/NO) │                    └────┬────┘      │
         │    │         │    └────┬────┘                         │           │
         │    │         │         │                         ┌────┴─────┐     │
         │    │         │    ┌────┴────┐                    │ SINGLE   │     │
         │    │         │    │ UV LED  │                    │WHITE LED │     │
         │    │         │    │ STRIP   │                    └────┬─────┘     │
         │    │         │    └────┬────┘                         │           │
         │    │         │         │                         ┌────┴────┐      │
         │    │         │         │                         │ MOSFET  │      │
         │    │         │         │                         │   Q2    │      │
         │    │         │         │                         └────┬────┘      │
         │    │         │                                        │           │
    ═════╪════╪═════════╪════════════════════════════════════════╪═══════════╪═════
         │    │         │              GND BUS                   │           │
         │    │         │                                        │           │
         │    │         │                                        │           │
    ┌────┴────┴─────────┴────────────────────────────────────────┴───────────┴────┐
    │                                                                              │
    │                            RASPBERRY PI 4/5                                  │
    │                                                                              │
    │  ┌─────────────────────────────────────────────────────────────────────┐    │
    │  │                          GPIO HEADER                                 │    │
    │  │                                                                      │    │
    │  │   3.3V ────► IR Sensors VCC                                         │    │
    │  │   5V   ────► (Available)                                            │    │
    │  │   GND  ────► Common Ground                                          │    │
    │  │                                                                      │    │
    │  │   GPIO5  ◄── IR Sensor 1 OUT (Bill Entry)                           │    │
    │  │   GPIO6  ◄── IR Sensor 2 OUT (Bill Position)                        │    │
    │  │                                                                      │    │
    │  │   GPIO17 ──► L298N IN1                                              │    │
    │  │   GPIO27 ──► L298N IN2                                              │    │
    │  │   GPIO22 ──► L298N ENA (PWM - Hardware PWM on GPIO18 recommended)   │    │
    │  │                                                                      │    │
    │  │   GPIO23 ──► Relay IN (UV LED)                                      │    │
    │  │   GPIO24 ──► MOSFET Q2 Gate (White LED)                             │    │
    │  │                                                                      │    │
    │  └─────────────────────────────────────────────────────────────────────┘    │
    │                                                                              │
    │  ┌─────────────┐                                                            │
    │  │ USB CAMERA  │◄─── USB 3.0 Port                                          │
    │  └─────────────┘                                                            │
    │                                                                              │
    └──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.5 Software Control Logic

### 2.5.1 GPIO Setup (Python)

```python
import RPi.GPIO as GPIO
import time

# Pin Definitions
MOTOR_IN1 = 17
MOTOR_IN2 = 27
MOTOR_ENA = 22  # PWM pin

IR_ENTRY = 5
IR_POSITION = 6

UV_LED = 23
WHITE_LED = 24

# Setup
GPIO.setmode(GPIO.BCM)

# Motor pins
GPIO.setup(MOTOR_IN1, GPIO.OUT)
GPIO.setup(MOTOR_IN2, GPIO.OUT)
GPIO.setup(MOTOR_ENA, GPIO.OUT)

# IR sensors (input with pull-up)
GPIO.setup(IR_ENTRY, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(IR_POSITION, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# LED control
GPIO.setup(UV_LED, GPIO.OUT)
GPIO.setup(WHITE_LED, GPIO.OUT)

# PWM for motor speed control
motor_pwm = GPIO.PWM(MOTOR_ENA, 1000)  # 1kHz frequency
motor_pwm.start(0)  # Start with motor off
```

### 2.5.2 Motor Control Functions

```python
def motor_forward(speed=80):
    """Run motor forward (pull bill in). Speed: 0-100"""
    GPIO.output(MOTOR_IN1, GPIO.HIGH)
    GPIO.output(MOTOR_IN2, GPIO.LOW)
    motor_pwm.ChangeDutyCycle(speed)

def motor_reverse(speed=80):
    """Run motor reverse (eject bill). Speed: 0-100"""
    GPIO.output(MOTOR_IN1, GPIO.LOW)
    GPIO.output(MOTOR_IN2, GPIO.HIGH)
    motor_pwm.ChangeDutyCycle(speed)

def motor_stop():
    """Stop motor"""
    GPIO.output(MOTOR_IN1, GPIO.LOW)
    GPIO.output(MOTOR_IN2, GPIO.LOW)
    motor_pwm.ChangeDutyCycle(0)

def motor_brake():
    """Active brake"""
    GPIO.output(MOTOR_IN1, GPIO.HIGH)
    GPIO.output(MOTOR_IN2, GPIO.HIGH)
    motor_pwm.ChangeDutyCycle(100)
```

### 2.5.3 LED Control Functions

```python
def uv_led_on():
    GPIO.output(UV_LED, GPIO.HIGH)

def uv_led_off():
    GPIO.output(UV_LED, GPIO.LOW)

def white_led_on():
    GPIO.output(WHITE_LED, GPIO.HIGH)

def white_led_off():
    GPIO.output(WHITE_LED, GPIO.LOW)
```

### 2.5.4 Bill Detection Functions

```python
def is_bill_at_entry():
    """Check if bill is detected at entry slot"""
    return GPIO.input(IR_ENTRY) == GPIO.LOW  # LOW = detected

def is_bill_in_position():
    """Check if bill is in camera position"""
    return GPIO.input(IR_POSITION) == GPIO.LOW
```

### 2.5.5 Main Bill Acceptance Sequence

```python
def accept_bill():
    """
    Main bill acceptance sequence.
    Returns: (success: bool, denomination: str or None, error: str or None)
    """

    # Wait for bill insertion
    print("Waiting for bill...")
    while not is_bill_at_entry():
        time.sleep(0.01)  # 10ms polling

    print("Bill detected at entry")

    # Pull bill into position
    motor_forward(speed=60)

    # Wait for bill to reach camera position
    timeout = time.time() + 5  # 5 second timeout
    while not is_bill_in_position():
        if time.time() > timeout:
            motor_stop()
            return (False, None, "TIMEOUT_POSITION")
        time.sleep(0.01)

    # Stop motor when bill is in position
    motor_stop()
    print("Bill in position")

    # AUTHENTICATION PHASE
    uv_led_on()
    time.sleep(0.2)  # Allow LED to stabilize

    # Capture UV image and run authentication model
    uv_image = capture_image()
    is_genuine = run_auth_model(uv_image)

    uv_led_off()

    if not is_genuine:
        print("Bill rejected - not genuine")
        motor_reverse(speed=80)
        time.sleep(1.5)  # Eject for 1.5 seconds
        motor_stop()
        return (False, None, "NOT_GENUINE")

    # DENOMINATION PHASE
    white_led_on()
    time.sleep(0.2)

    # Capture visible image and run denomination model
    visible_image = capture_image()
    denomination = run_denomination_model(visible_image)

    white_led_off()

    if denomination is None:
        print("Could not identify denomination")
        motor_reverse(speed=80)
        time.sleep(1.5)
        motor_stop()
        return (False, None, "UNKNOWN_DENOMINATION")

    print(f"Denomination identified: {denomination}")

    # Send command to Arduino for sorting
    send_sort_command(denomination)

    # Wait for Arduino to position sorter
    wait_for_sorter_ready()

    # Move bill to storage
    motor_forward(speed=70)
    time.sleep(2)  # Adjust based on conveyor length
    motor_stop()

    return (True, denomination, None)
```

---

## 2.6 Timing Specifications

| Operation                 | Typical Duration | Maximum        |
| ------------------------- | ---------------- | -------------- |
| Bill entry detection      | Instant          | 10ms           |
| Motor pull to position    | 1-2 seconds      | 3 seconds      |
| UV LED stabilization      | 200ms            | 300ms          |
| Camera capture            | 50-100ms         | 200ms          |
| YOLO inference (auth)     | 100-300ms        | 500ms          |
| YOLO inference (denom)    | 100-300ms        | 500ms          |
| Sorter positioning        | 0.5-2 seconds    | 3 seconds      |
| Bill to storage           | 1-2 seconds      | 3 seconds      |
| **Total acceptance time** | **3-6 seconds**  | **10 seconds** |

---

## 2.7 Error Handling

| Error Code             | Description                               | Recovery Action           |
| ---------------------- | ----------------------------------------- | ------------------------- |
| `TIMEOUT_POSITION`     | Bill didn't reach camera position in time | Reverse motor, eject bill |
| `NOT_GENUINE`          | Authentication model rejected bill        | Reverse motor, eject bill |
| `UNKNOWN_DENOMINATION` | Denomination model couldn't identify      | Reverse motor, eject bill |
| `SORTER_TIMEOUT`       | Arduino didn't respond with READY         | Log error, eject bill     |
| `CAMERA_ERROR`         | Camera capture failed                     | Retry once, then eject    |
| `MOTOR_STUCK`          | IR sensor not changing state              | Alert maintenance         |

---

_Document 2 of 10 - Coinnect System Architecture_
