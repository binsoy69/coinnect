# Coinnect System Architecture

## 08 - Communication Protocol

**Document Version:** 2.0  
**Date:** February 2026  
**Interface:** USB Serial (RPi ↔ Arduino)

---

## 8.1 Overview

The Raspberry Pi communicates with **two Arduino Mega controllers** via separate USB Serial connections using JSON-formatted messages.

**Dual-Serial Architecture:**

```
                     RASPBERRY PI
                          │
            ┌─────────────┴─────────────┐
            │                           │
      /dev/ttyUSB0               /dev/ttyACM0
      (115200 baud)              (115200 baud)
            │                           │
            ▼                           ▼
    Arduino Mega #1              Arduino Mega #2
   (Bill Controller)         (Coin & Security)
```

**Connection Details (Both Ports):**

- Interface: USB Serial
- Baud Rate: 115200
- Data Bits: 8, Stop Bits: 1, Parity: None
- Line Ending: Newline (`\n`)

**Command Routing:**

| Commands                                        | Arduino              | Serial Port      |
| ----------------------------------------------- | -------------------- | ---------------- |
| SORT, HOME, SORT_STATUS                         | #1 (Bill)            | /dev/ttyUSB0     |
| DISPENSE, DISPENSE_STATUS                       | #1 (Bill)            | /dev/ttyUSB0     |
| COIN_DISPENSE, COIN_CHANGE, COIN_RESET, COIN_STATUS | #2 (Coin & Security) | /dev/ttyACM0     |
| COIN_ACCEPTOR_ENABLE, COIN_SORTER_POSITION     | #2 (Coin & Security) | /dev/ttyACM0     |
| SECURITY_LOCK, SECURITY_UNLOCK, SECURITY_STATUS | #2 (Coin & Security) | /dev/ttyACM0     |
| PING, VERSION, RESET                            | Both                 | Individual ports |

---

## 8.2 Message Format

### Commands (RPi → Arduino)

```json
{"cmd": "COMMAND_NAME", "param1": "value1", "param2": value2}
```

### Responses (Arduino → RPi)

```json
{"status": "OK", ...}
{"status": "ERROR", "code": "ERROR_CODE"}
```

### Events (Arduino → RPi, Unsolicited)

```json
{"event": "EVENT_NAME", ...}
```

---

## 8.3 Command Reference

### 8.3.1 Bill Sorting Commands

| Command     | Request                            | Response                                                 |
| ----------- | ---------------------------------- | -------------------------------------------------------- |
| SORT        | `{"cmd":"SORT","denom":"PHP_100"}` | `{"status":"READY","slot":3}`                            |
| HOME        | `{"cmd":"HOME"}`                   | `{"status":"OK","position":0}`                           |
| SORT_STATUS | `{"cmd":"SORT_STATUS"}`            | `{"status":"OK","position":60000,"slot":3,"homed":true}` |

Valid denominations: PHP_20, PHP_50, PHP_100, PHP_200, PHP_500, PHP_1000, USD_10, USD_50, EUR_5, EUR_10

### 8.3.2 Bill Dispensing Commands

| Command         | Request                                          | Response                        |
| --------------- | ------------------------------------------------ | ------------------------------- |
| DISPENSE        | `{"cmd":"DISPENSE","denom":"PHP_100","count":2}` | `{"status":"OK","dispensed":2}` |
| DISPENSE_STATUS | `{"cmd":"DISPENSE_STATUS","denom":"PHP_100"}`    | `{"status":"OK","ready":true}`  |
| CONVEYOR        | `{"cmd":"CONVEYOR","target":"PHP"}`              | `{"status":"OK","target":"PHP"}`|

### 8.3.3 Coin System Commands

| Command       | Request                                       | Response                                           |
| ------------- | --------------------------------------------- | -------------------------------------------------- |
| COIN_DISPENSE | `{"cmd":"COIN_DISPENSE","denom":5,"count":3}` | `{"status":"OK","dispensed":3}`                    |
| COIN_CHANGE   | `{"cmd":"COIN_CHANGE","amount":47}`           | `{"status":"OK","breakdown":{"20":2,"5":1,"1":2}}` |
| COIN_RESET    | `{"cmd":"COIN_RESET"}`                        | `{"status":"OK","previous_total":150}`             |
| COIN_ACCEPTOR_ENABLE | `{"cmd":"COIN_ACCEPTOR_ENABLE","enabled":true}` | `{"status":"OK","enabled":true}`          |
| COIN_STATUS   | `{"cmd":"COIN_STATUS"}`                       | `{"status":"OK","acceptor_enabled":false,"sorter_position":"CENTER","sorter_angle":81,"session_total":0}` |
| COIN_SORTER_POSITION | `{"cmd":"COIN_SORTER_POSITION","position":"LEFT"}` | `{"status":"OK","sorter_position":"LEFT","sorter_angle":45}` |

**Event:** `{"event":"COIN_IN","denom":5,"total":150}`

Sorter positions are `CENTER=81`, `LEFT=45`, and `RIGHT=120`. PHP 1 and PHP 5
coins route right; PHP 10 and PHP 20 coins route left. The acceptor enable line
is active HIGH and defaults disabled.

### 8.3.4 Security Commands

| Command         | Request                     | Response                                         |
| --------------- | --------------------------- | ------------------------------------------------ |
| SECURITY_LOCK   | `{"cmd":"SECURITY_LOCK"}`   | `{"status":"OK","locked":true}`                  |
| SECURITY_UNLOCK | `{"cmd":"SECURITY_UNLOCK"}` | `{"status":"OK","locked":false}`                 |
| SECURITY_STATUS | `{"cmd":"SECURITY_STATUS"}` | `{"status":"OK","locked":true,"tamper_a":false}` |

*Note: The `tamper_a` status field is set if either Shock Sensor A or Shock Sensor B is triggered, representing the global latched tamper state.*

**Events:**

- `{"event":"TAMPER","sensor":"A"}`
- `{"event":"RFID","uid":"A1B2C3D4"}`
- `{"event":"DOOR_STATE","locked":true}`

### 8.3.5 System Commands

| Command | Request             | Response                                                |
| ------- | ------------------- | ------------------------------------------------------- |
| PING    | `{"cmd":"PING"}`    | `{"status":"OK","message":"PONG"}`                      |
| VERSION | `{"cmd":"VERSION"}` | `{"status":"OK","version":"2.0.0","controller":"BILL"}` or `{"status":"OK","version":"2.1.0","controller":"COIN_SECURITY"}` |
| RESET   | `{"cmd":"RESET"}`   | `{"status":"OK"}`                                       |

**Event:** `{"event":"READY","version":"2.0.0","controller":"BILL"}` or `{"event":"READY","version":"2.1.0","controller":"COIN_SECURITY"}`

> **Note:** Each Arduino responds with its own controller identifier:
>
> - Arduino #1: `"controller":"BILL"`
> - Arduino #2: `"controller":"COIN_SECURITY"`

---

## 8.4 Error Codes

| Code          | Description             |
| ------------- | ----------------------- |
| PARSE_ERROR   | JSON parsing failed     |
| UNKNOWN_CMD   | Unrecognized command    |
| INVALID_PARAM | Parameter has wrong type or value |
| INVALID_DENOM | Unknown denomination    |
| INVALID_COUNT | Count out of range      |
| NOT_HOMED     | Sorter not homed        |
| JAM           | Bill jam detected       |
| EMPTY         | Dispenser empty         |
| TIMEOUT       | Operation timed out     |
| MOTOR_FAULT   | Motor not responding    |
| LOCKED_OUT    | Security lockout active |

---

## 8.5 Message Flow: Bill Acceptance

```
USER              RASPBERRY PI                    ARDUINO #1
  │                    │                             │
  │  Insert Bill       │                             │
  │───────────────────►│                             │
  │              [Auth & Denom ID]                   │
  │                    │  {"cmd":"SORT",             │
  │                    │   "denom":"PHP_100"}        │
  │                    │───────/dev/ttyUSB0─────────►│
  │                    │                      [Move stepper]
  │                    │  {"status":"READY"}         │
  │                    │◄───────/dev/ttyUSB0─────────│
  │              [Motor forward]                     │
  │  Display Updated   │                             │
  │◄───────────────────│                             │
```

---

_Document 8 of 10 - Coinnect System Architecture_
