# Coinnect System Architecture

## 10 - Bill of Materials

**Document Version:** 2.0  
**Date:** February 2026  
**Currency:** Philippine Peso (₱)

---

## 10.1 Overview

This document lists all electronic and electrical components required for the Coinnect kiosk system. Prices are estimates based on local Philippine suppliers and may vary.

**Categories:**

1. Controllers & Computing
2. Motor Drivers & Motors
3. Sensors
4. Power Supply
5. Coin System
6. Security Components
7. User Interface
8. Connectors & Wiring
9. Miscellaneous

---

## 10.2 Detailed Bill of Materials

### 10.2.1 Controllers & Computing

| Item                   | Specification    | Qty | Unit Price (₱) | Total (₱) | Source       |
| ---------------------- | ---------------- | --- | -------------- | --------- | ------------ |
| Raspberry Pi 4 Model B | 4GB RAM          | 1   | 3,500          | 3,500     | Local/Lazada |
| Arduino Mega 2560      | ATmega2560       | 2   | 800            | 1,600     | Local/Lazada |
| MicroSD Card           | 32GB Class 10    | 1   | 350            | 350       | Local        |
| USB Cable              | Type-A to Type-B | 2   | 100            | 200       | Local        |
| **Subtotal**           |                  |     |                | **5,650** |              |

> **Note:** Two Arduino Megas are used for optimal pin management:
>
> - **Arduino Mega #1 (Bill Controller):** Bill Sorting + Bill Dispensing
> - **Arduino Mega #2 (Coin & Security Controller):** Coin System + Security System

### 10.2.2 Motor Drivers & Motors

| Item               | Specification     | Qty | Unit Price (₱) | Total (₱) | Notes                           |
| ------------------ | ----------------- | --- | -------------- | --------- | ------------------------------- |
| L298N Motor Driver | Dual H-Bridge     | 13  | 150            | 1,950     | 12 dispensers + 1 bill acceptor |
| DC Motor (12V)     | 200-500mA, geared | 25  | 200            | 5,000     | 24 dispensers + 1 acceptor      |
| NEMA 17 Stepper    | 1.8°, 1.5A        | 1   | 450            | 450       | Bill sorter                     |
| A4988 Driver       | Stepper driver    | 1   | 80             | 80        | With heatsink                   |
| GT2 Timing Belt    | 2mm pitch, 1m     | 1   | 150            | 150       | Sorter mechanism                |
| GT2 Pulley         | 20T, 5mm bore     | 2   | 60             | 120       | Motor + idler                   |
| Linear Rail        | 400mm MGN12H      | 1   | 600            | 600       | Sorter carriage                 |
| **Subtotal**       |                   |     |                | **8,350** |                                 |

### 10.2.3 Sensors

| Item               | Specification    | Qty | Unit Price (₱) | Total (₱) | Notes                      |
| ------------------ | ---------------- | --- | -------------- | --------- | -------------------------- |
| IR Obstacle Sensor | FC-51 / KY-032   | 14  | 50             | 700       | 12 dispensers + 2 acceptor |
| USB Camera         | 1080p, autofocus | 1   | 800            | 800       | Bill authentication        |
| Limit Switch       | Micro switch NO  | 1   | 30             | 30        | Sorter home                |
| **Subtotal**       |                  |     |                | **1,530** |                            |

### 10.2.4 Power Supply

| Item                   | Specification    | Qty | Unit Price (₱) | Total (₱) | Notes                   |
| ---------------------- | ---------------- | --- | -------------- | --------- | ----------------------- |
| ATX Power Supply       | 450W, 80+ Bronze | 1   | 1,500          | 1,500     | Main power              |
| ATX Breakout Board     | 24-pin           | 1   | 200            | 200       | Optional, easier wiring |
| Blade Fuse Holder      | 10-position      | 1   | 150            | 150       | Protection              |
| Blade Fuses            | Assorted 3A-10A  | 10  | 10             | 100       | Spares included         |
| Terminal Block         | 12-position      | 3   | 80             | 240       | Power distribution      |
| Electrolytic Capacitor | 100µF 25V        | 15  | 5              | 75        | L298N filtering         |
| Ceramic Capacitor      | 0.1µF            | 15  | 2              | 30        | High-freq filtering     |
| **Subtotal**           |                  |     |                | **2,295** |                         |

### 10.2.5 Coin System

| Item                | Specification     | Qty | Unit Price (₱) | Total (₱) | Notes            |
| ------------------- | ----------------- | --- | -------------- | --------- | ---------------- |
| Multi-Coin Acceptor | CH-926 or similar | 1   | 2,500          | 2,500     | Programmable     |
| Servo Motor         | MG996R or SG90    | 4   | 180            | 720       | Coin dispensers  |
| Coin Storage Tube   | Custom/3D printed | 4   | 100            | 400       | ₱1, ₱5, ₱10, ₱20 |
| **Subtotal**        |                   |     |                | **3,620** |                  |

### 10.2.6 Security Components

| Item          | Specification | Qty | Unit Price (₱) | Total (₱) | Notes              |
| ------------- | ------------- | --- | -------------- | --------- | ------------------ |
| Shock Sensor  | SW-420 module | 2   | 50             | 100       | Tamper detection   |
| Solenoid Lock | 12V DC, 500mA | 1   | 350            | 350       | Door lock          |
| Relay Module  | 5V, 1-channel | 1   | 50             | 50        | Solenoid control   |
| Matrix Keypad | 4x3 membrane  | 1   | 80             | 80        | PIN entry          |
| LED           | 5mm Red       | 2   | 5              | 10        | Status indicator   |
| LED           | 5mm Green     | 2   | 5              | 10        | Status indicator   |
| Resistor      | 220Ω 1/4W     | 10  | 1              | 10        | LED current limit  |
| Diode         | 1N4007        | 5   | 3              | 15        | Flyback protection |
| **Subtotal**  |               |     |                | **625**   |                    |

### 10.2.7 User Interface

| Item                | Specification     | Qty | Unit Price (₱) | Total (₱) | Notes            |
| ------------------- | ----------------- | --- | -------------- | --------- | ---------------- |
| Touchscreen Display | 10" IPS, HDMI+USB | 1   | 4,500          | 4,500     | Main UI          |
| Thermal Printer     | 58mm or 80mm, USB | 1   | 1,500          | 1,500     | Receipt printing |
| Thermal Paper Roll  | 58mm x 30m        | 5   | 30             | 150       | Consumable       |
| **Subtotal**        |                   |     |                | **6,150** |                  |

### 10.2.8 Lighting (Bill Acceptor)

| Item            | Specification         | Qty | Unit Price (₱) | Total (₱) | Notes                |
| --------------- | --------------------- | --- | -------------- | --------- | -------------------- |
| UV LED Strip    | 365-395nm, 12V        | 1   | 300            | 300       | Authentication       |
| White LED Strip | 6000K, 12V            | 1   | 200            | 200       | Denomination capture |
| MOSFET          | IRLZ44N (logic level) | 2   | 40             | 80        | LED switching        |
| Resistor        | 1kΩ 1/4W              | 10  | 1              | 10        | Gate resistors       |
| Resistor        | 10kΩ 1/4W             | 10  | 1              | 10        | Pull-down resistors  |
| **Subtotal**    |                       |     |                | **600**   |                      |

### 10.2.9 Connectors & Wiring

| Item                 | Specification        | Qty | Unit Price (₱) | Total (₱) | Notes                    |
| -------------------- | -------------------- | --- | -------------- | --------- | ------------------------ |
| Wire                 | 16 AWG Red, 5m       | 1   | 150            | 150       | 5V main                  |
| Wire                 | 16 AWG Yellow, 5m    | 1   | 150            | 150       | 12V main                 |
| Wire                 | 16 AWG Black, 10m    | 1   | 250            | 250       | Ground                   |
| Wire                 | 22 AWG Assorted, 10m | 1   | 200            | 200       | Signal wires             |
| Dupont Jumper Wires  | M-M, M-F, F-F set    | 3   | 80             | 240       | Prototyping              |
| JST XH Connector Kit | 2/3/4 pin assorted   | 1   | 200            | 200       | Motor/sensor connections |
| Heat Shrink Tubing   | Assorted sizes       | 1   | 100            | 100       | Insulation               |
| Cable Ties           | 100pcs               | 1   | 50             | 50        | Cable management         |
| **Subtotal**         |                      |     |                | **1,340** |                          |

### 10.2.10 Miscellaneous

| Item                | Specification     | Qty | Unit Price (₱) | Total (₱) | Notes           |
| ------------------- | ----------------- | --- | -------------- | --------- | --------------- |
| Breadboard          | Full-size 830 pts | 2   | 100            | 200       | Prototyping     |
| PCB Prototype Board | 7x9cm             | 5   | 30             | 150       | Custom circuits |
| Standoffs/Spacers   | M3 assorted kit   | 1   | 100            | 100       | Mounting        |
| Screws/Nuts         | M3 assorted kit   | 1   | 100            | 100       | Assembly        |
| Double-sided Tape   | 3M VHB            | 1   | 150            | 150       | Mounting        |
| **Subtotal**        |                   |     |                | **700**   |                 |

---

## 10.3 Cost Summary

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           COST SUMMARY                                           │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────┬─────────────────┬─────────────────────────────┐
│  Category                       │  Subtotal (₱)   │  % of Total                 │
├─────────────────────────────────┼─────────────────┼─────────────────────────────┤
│  Controllers & Computing        │  5,650          │  18.3%                      │
│  Motor Drivers & Motors         │  8,350          │  27.1%                      │
│  Sensors                        │  1,530          │  5.0%                       │
│  Power Supply                   │  2,295          │  7.4%                       │
│  Coin System                    │  3,620          │  11.7%                      │
│  Security Components            │  625            │  2.0%                       │
│  User Interface                 │  6,150          │  19.9%                      │
│  Lighting                       │  600            │  1.9%                       │
│  Connectors & Wiring            │  1,340          │  4.3%                       │
│  Miscellaneous                  │  700            │  2.3%                       │
├─────────────────────────────────┼─────────────────┼─────────────────────────────┤
│  ELECTRONICS SUBTOTAL           │  30,860         │  100%                       │
├─────────────────────────────────┼─────────────────┼─────────────────────────────┤
│  Contingency (15%)              │  4,629          │                             │
├─────────────────────────────────┼─────────────────┼─────────────────────────────┤
│  ELECTRONICS TOTAL              │  35,489         │                             │
└─────────────────────────────────┴─────────────────┴─────────────────────────────┘


NOT INCLUDED IN THIS BOM:
═════════════════════════

• Enclosure/Cabinet (custom fabrication)
• Mechanical components (rails, brackets, custom parts)
• 3D printed parts
• Bill storage boxes
• Labor/Assembly
• Software development
• Testing equipment
• Shipping costs

ESTIMATED ADDITIONAL COSTS:
═══════════════════════════

• Enclosure fabrication: ₱15,000 - ₱30,000
• Mechanical parts: ₱5,000 - ₱10,000
• 3D printing: ₱2,000 - ₱5,000
• Assembly labor: ₱5,000 - ₱10,000

TOTAL PROJECT ESTIMATE: ₱60,000 - ₱90,000
```

---

## 10.4 Supplier Recommendations (Philippines)

| Supplier             | Products                  | Location               | Contact                  |
| -------------------- | ------------------------- | ---------------------- | ------------------------ |
| Alexan               | Electronics, components   | Makati, QC             | alexan.com.ph            |
| E-Gizmo              | Arduino, sensors, modules | QC                     | e-gizmo.net              |
| Makerlab Electronics | Robotics, 3D printing     | Multiple               | makerlab-electronics.com |
| Lazada/Shopee        | Various                   | Online                 | Multiple sellers         |
| Cytron               | Motors, drivers           | Malaysia (ships to PH) | cytron.io                |

---

## 10.5 Development Phases & Budget Allocation

### Phase 1: Prototype (₱15,900)

- Raspberry Pi + 2x Arduino Mega
- 2 dispenser units for testing
- Basic sensors
- Breadboard prototyping

### Phase 2: Bill System (₱10,000)

- Remaining dispenser motors/drivers
- Bill acceptor motor
- Camera + lighting
- Sorting mechanism

### Phase 3: Coin System (₱4,000)

- Coin acceptor
- Servo motors
- Coin storage tubes

### Phase 4: Integration (₱5,000)

- Security components
- User interface
- Power supply
- Final wiring

---

## 10.6 Spare Parts Recommendation

| Item                  | Quantity | Reason                 |
| --------------------- | -------- | ---------------------- |
| DC Motor 12V          | 3        | High wear item         |
| L298N Driver          | 2        | Heat-related failure   |
| IR Sensor             | 3        | Alignment issues       |
| Servo Motor           | 1        | Mechanical wear        |
| Fuses (assorted)      | 10       | Blown fuse replacement |
| Capacitors (assorted) | 20       | Filtering/failure      |
| USB Cable             | 2        | Connection wear        |
| Thermal Paper         | 10 rolls | Consumable             |

---

_Document 10 of 10 - Coinnect System Architecture_
