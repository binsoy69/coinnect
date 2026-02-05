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
| COIN_DISPENSE, COIN_CHANGE, COIN_RESET          | #2 (Coin & Security) | /dev/ttyACM0     |
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
{"status": "OK", "data": {...}}
{"status": "ERROR", "code": "ERROR_CODE"}
```

### Events (Arduino → RPi, Unsolicited)

```json
{"event": "EVENT_NAME", "data": {...}}
```

---

## 8.3 Command Reference

### 8.3.1 Bill Sorting Commands

| Command     | Request                            | Response                                                 |
| ----------- | ---------------------------------- | -------------------------------------------------------- |
| SORT        | `{"cmd":"SORT","denom":"PHP_100"}` | `{"status":"READY","slot":3}`                            |
| HOME        | `{"cmd":"HOME"}`                   | `{"status":"OK","position":0}`                           |
| SORT_STATUS | `{"cmd":"SORT_STATUS"}`            | `{"status":"OK","position":14600,"slot":3,"homed":true}` |

Valid denominations: PHP_20, PHP_50, PHP_100, PHP_200, PHP_500, PHP_1000, USD_10, USD_50, USD_100, EUR_5, EUR_10, EUR_20

### 8.3.2 Bill Dispensing Commands

| Command         | Request                                          | Response                        |
| --------------- | ------------------------------------------------ | ------------------------------- |
| DISPENSE        | `{"cmd":"DISPENSE","denom":"PHP_100","count":2}` | `{"status":"OK","dispensed":2}` |
| DISPENSE_STATUS | `{"cmd":"DISPENSE_STATUS","denom":"PHP_100"}`    | `{"status":"OK","ready":true}`  |

### 8.3.3 Coin System Commands

| Command       | Request                                       | Response                                           |
| ------------- | --------------------------------------------- | -------------------------------------------------- |
| COIN_DISPENSE | `{"cmd":"COIN_DISPENSE","denom":5,"count":3}` | `{"status":"OK","dispensed":3}`                    |
| COIN_CHANGE   | `{"cmd":"COIN_CHANGE","amount":47}`           | `{"status":"OK","breakdown":{"20":2,"5":1,"1":2}}` |
| COIN_RESET    | `{"cmd":"COIN_RESET"}`                        | `{"status":"OK","previous_total":150}`             |

**Event:** `{"event":"COIN_IN","denom":5,"total":150}`

### 8.3.4 Security Commands

| Command         | Request                     | Response                                         |
| --------------- | --------------------------- | ------------------------------------------------ |
| SECURITY_LOCK   | `{"cmd":"SECURITY_LOCK"}`   | `{"status":"OK","locked":true}`                  |
| SECURITY_UNLOCK | `{"cmd":"SECURITY_UNLOCK"}` | `{"status":"OK","locked":false}`                 |
| SECURITY_STATUS | `{"cmd":"SECURITY_STATUS"}` | `{"status":"OK","locked":true,"tamper_a":false}` |

**Events:**

- `{"event":"TAMPER","sensor":"A"}`
- `{"event":"KEYPAD","key":"5"}`
- `{"event":"DOOR_STATE","locked":true}`

### 8.3.5 System Commands

| Command | Request             | Response                                                |
| ------- | ------------------- | ------------------------------------------------------- |
| PING    | `{"cmd":"PING"}`    | `{"status":"OK","message":"PONG"}`                      |
| VERSION | `{"cmd":"VERSION"}` | `{"status":"OK","version":"2.0.0","controller":"BILL"}` |
| RESET   | `{"cmd":"RESET"}`   | `{"status":"OK"}`                                       |

**Event:** `{"event":"READY","version":"2.0.0","controller":"BILL"}`

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
