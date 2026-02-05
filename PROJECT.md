# Coinnect Project

**Single Source of Truth**

## Project Identity

**Coinnect** is a unified, self-service financial kiosk designed to provide secure and efficient cash interactions for the general public. It integrates advanced bill verification, sorting, and dispensing mechanisms with a robust coin handling and security system.

## Goals

- **Physical Hardware Implementation**: Deliver a real, working kiosk using physical hardware components (sensors, motors, controllers), not just a simulation.
- **Financial Services Integration**: Support **GCash** and **Maya** for seamless cash-in and cash-out transactions.
- **Money Conversion**: Enable versatile currency exchange functionalities:
  - Coin ↔ Bill
  - Bill ↔ Bill
- **Offline Operation**: Ensure core functionality operates offline, requiring internet connectivity _only_ for external API transactions.
- **Security**: Ensure high-level security for physical cash and transaction data.
- **Reliability**: Provide a robust hardware control system using independent controllers for critical subsystems.
- **User Experience**: Offer a seamless, intuitive touchscreen interface for the general public.

## Non-Goals

- **No Credit Card Support**: The system accepts and dispenses cash only.
- **Not a Mobile App**: This is a physical kiosk ecosystem, not a mobile application.

## Operational Constraints (Prototype Phase)

- **Transaction Limits**: None. Inventory availability is the only constraint.
- **Regulatory Compliance**: Deferred. BSP registration and AML/KYC requirements will be addressed before production deployment.
- **Deployment Environment**: Indoor climate-controlled locations only (20-25°C, low humidity). Examples: malls, offices, retail stores with AC.

## Localization

- **Languages**: Filipino (Tagalog) and English.
- **Scope**: All user-facing text, prompts, error messages, and receipts.
- **Implementation**: i18n framework with language selection at session start.

## Core Features

1.  **Bill Acceptance & Verification**
    - Uses a Raspberry Pi 4/5-controlled camera with YOLO Machine Learning models for authenticating bills and identifying denominations.
    - Integrated UV and White LED systems for visual verification.
    - Automatic bill rejection mechanism for counterfeit or unrecognized notes.

2.  **Bill Sorting & Storage**
    - Precise stepper motor-driven sorting mechanism (Arduino Mega #1).
    - Categorizes bills into 8 distinct storage slots (PHP, USD, EUR).

3.  **Bill Dispensing**
    - High-capacity dispensing system (Arduino Mega #1).
    - 12 independent dispenser units with IR validation sensors.

4.  **Coin Operations**
    - Multi-coin acceptance (Arduino Mega #2) supporting various denominations.
    - Servo-controlled coin dispensing for exact change.

5.  **Security System**
    - Integrated shock sensors, solenoid locks, and keypad access (Arduino Mega #2).
    - Fault-tolerant design ensures security functions remain active even if the bill system is down.

6.  **User Interface**
    - Interactive touchscreen display.
    - Thermal printer for transaction receipts.

## Current Status

- **Phase**: Documentation-First (Planning Complete, Implementation Not Started)
- **Completed**:
  - YOLO Models for Bill Authentication and Denomination.
  - UI Mockups.
  - System architecture documentation.
  - Hardware reference specifications.
- **In Progress**: Finalizing operational policies and development roadmap.
- **Next**: Environment setup (Python backend, React frontend, PlatformIO firmware).

## Success Criteria (Definition of Done)

- **End-to-End Test**: A successful, error-free transaction cycle (Accept Cash -> Verify -> Sort -> Dispense Change/Receipt).
- **System Stability**: All subsystems (Bill, Coin, Security) operating in parallel without pin conflicts or communication errors.

## Related Documents

Detailed technical specifications can be found in the `reference/` directory:

| Component    | Document                                                                                                                                                 |
| :----------- | :------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Overview** | [System Architecture](reference/01_system_overview.md)                                                                                                   |
| **Bills**    | [Acceptor](reference/02_bill_acceptor_system.md) • [Sorting](reference/03_bill_sorting_system.md) • [Dispensing](reference/04_bill_dispensing_system.md) |
| **Coins**    | [Coin System](reference/05_coin_system.md)                                                                                                               |
| **Security** | [Security System](reference/06_security_system.md)                                                                                                       |
| **Hardware** | [Pin Assignments](reference/09_pin_assignments.md) • [Power](reference/07_power_distribution.md) • [BOM](reference/10_bill_of_materials.md)              |
| **Software** | [Comms Protocol](reference/08_communication_protocol.md)                                                                                                 |
