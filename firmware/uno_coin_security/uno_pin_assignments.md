# Coinnect Uno Pin Assignments Guide

This document defines the hardware pin assignments and installation specifications for the Arduino Uno (ATmega328P) version of the Coin & Security Controller (`uno_coin_security.ino`).

---

## 1. Pin Mapping Reference (Mega 2560 vs. Uno)

The Arduino Uno offers 20 usable GPIO pins (Digital 0–13 and Analog A0–A5 configured as digital I/O). The following table shows how to map connections from the original Arduino Mega 2560 configuration to the Arduino Uno.

| Peripheral / Interface | Signal Name | Original Mega Pin | Proposed Uno Pin | Pin Configuration & Migration Notes |
| :--- | :--- | :---: | :---: | :--- |
| **Serial Communication** | Serial RX | D0 | **D0** | Hardware Serial (USB connection to Raspberry Pi) |
| | Serial TX | D1 | **D1** | Hardware Serial (USB connection to Raspberry Pi) |
| **MFRC522 RFID Reader** | MOSI | D51 | **D11** | Hardware SPI MOSI (Fixed on Uno) |
| | MISO | D50 | **D12** | Hardware SPI MISO (Fixed on Uno) |
| | SCK | D52 | **D13** | Hardware SPI SCK (Fixed on Uno) |
| | SDA (SS) | D53 | **D10** | Digital Output (Chip Select, keeps SPI in Master mode) |
| | RST | D5 | **A1** *(D15)* | Digital Output (Reset, Analog A1 configured as Digital Out) |
| **Coin Intake** | COIN Pulse | D18 | **D2** | External Interrupt (`INT0`) |
| | COIN Enable | D24 | **D4** | Digital Output (Active HIGH) |
| **Coin Sorting** | Sorter Servo | D7 | **D7** | Servo Output |
| **Coin Dispensers** | Servo PHP 1 | D44 | **D8** | Servo Output |
| | Servo PHP 5 | D45 | **D9** | Servo Output |
| | Servo PHP 10 | D46 | **D5** | Servo Output |
| | Servo PHP 20 | D6 | **D6** | Servo Output |
| **Security & Alarms** | Shock Sensor A | D19 | **D3** | External Interrupt (`INT1`) |
| | Shock Sensor B | D20 | **A0** *(D14)* | **Pin Change Interrupt (PCINT8)** |
| | Solenoid Lock | D21 | **A5** *(D19)* | Digital Output (Lock Relay control) |
| | Status Red LED | D22 | **A3** *(D17)* | Digital Output |
| | Status Green LED | D23 | **A4** *(D18)* | Digital Output |
| **Spare / Available** | Unused | - | **A2** *(D16)* | Free Pin |

---

## 2. Software Requirements: PinChangeInterrupt

Because the Arduino Uno only has two native external hardware interrupt pins (`D2`/`INT0` and `D3`/`INT1`), we utilize the NicoHood **PinChangeInterrupt** library to listen for rising-edge trigger events from Shock Sensor B on analog pin `A0`.

### Installation
In the Arduino IDE Library Manager or PlatformIO project dependencies, search for and install:
`PinChangeInterrupt` by NicoHood (v1.2.9 or newer).

### Firmware Implementation Note
The Pin Change Interrupt operates on the rising edge of pin `A0` (PCINT8) and routes directly to the existing `shockBISR` interrupt service routine:

```cpp
#include <PinChangeInterrupt.h>

// setup
void setup() {
  ...
  // Attach PinChangeInterrupt to SHOCK_B_PIN using NicoHood's library
  attachPinChangeInterrupt(digitalPinToPinChangeInterrupt(SHOCK_B_PIN), shockBISR, RISING);
}
```

---

## 3. Important Hardware Considerations

> [!CAUTION]
> **RFID Reader 3.3V Logic Level:**
> The MFRC522 RFID reader operates strictly on **3.3V**. Connecting the module's VCC to the Uno's 5V rail will destroy the RFID chip. Wire the VCC of the RFID reader to the 3.3V pin on the Arduino Uno.

> [!WARNING]
> **Servo Power Budget:**
> Do **NOT** power the five SG90 servo motors (Sorter + 4 Dispensers) directly from the Arduino Uno's onboard 5V regulator. Servo surge currents will cause voltage drops, causing the Arduino to reset under load.
> *   Provide power (+5V) to the servos directly from the kiosk's regulated ATX 5V power supply rail.
> *   Ensure the ATX power supply Ground (GND) is tied to the Arduino Uno's Ground (GND) pin to maintain a common signal ground reference.
