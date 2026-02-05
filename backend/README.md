# Coinnect Backend

Python backend for the Coinnect Kiosk.

## Tech Stack

- **Python 3.11+**
- **FastAPI**: REST API for Frontend communication
- **PySerial**: Serial communication with Arduino controllers
- **Ultralytics YOLO**: Bill authentication
- **PyTest**: Testing framework

## Project Structure

- **`app/api/`**: **Web Endpoints**. Contains FastAPI routers (e.g., `/transaction`, `/status`). This is where the Frontend talks to the Backend.
- **`app/core/`**: **App Plumbing**. Configuration (env vars), logging setup, and error handling.
- **`app/drivers/`**: **Hardware Layer**. Low-level code that talks to devices (Serial protocols for Arduino, Camera drivers). This isolates the hardware details from the rest of the app.
- **`app/services/`**: **Business Logic**. The "brains" of the kiosk. Contains the Transaction Manager, Payment Gateway logic (GCash/Maya), and Exchange Rate calculations.
- **`app/ml/`**: **Machine Learning**. Code related to loading and running the YOLO models for bill authentication.
- **`tests/`**: **Automated Tests**. Unit and Integration tests to ensure code quality.
