# Coinnect 🪙

Coinnect is a premium, self-service financial kiosk designed for cash-in/cash-out transactions, money conversion (PHP cash-to-cash, coin↔bill, bill↔bill), and e-wallet disbursements (GCash, PayMaya via PayMongo). 

This repository contains the full software suite: the FastAPI backend, React+Vite frontend UI, healthcheck diagnostic tools, and Arduino dual-controller firmware.

---

## 🏛️ System Architecture

Coinnect uses a hybrid hardware-software architecture for real-time safety, security, and concurrency:

1. **Raspberry Pi (Main Controller)**:
   - Hosts the Python FastAPI backend, React frontend, and YOLO-based ML models for bill authentication.
   - Manages high-level flows, transaction logs (WAL), and e-wallet API integration.
   - Connects to a Paperang P1 Bluetooth thermal printer, camera, and RFID reader.
2. **Arduino Mega #1 (Bill Controller)**:
   - Handles the high-precision stepper motor, linear rail bill sorting, and the 12-unit dispenser array.
3. **Arduino Mega #2 (Coin & Security Controller)**:
   - Manages coin intake (pulse-based acceptance), coin sorting/dispensing servos, shock sensors (SW-420), solenoid locks, status LEDs, and physical keypad input.

---

## 📁 Repository Structure

```
coinnect/
├── backend/          # FastAPI Python backend (Raspberry Pi / Dev Host)
│   ├── app/          # App code (routers, services, drivers, ML models)
│   ├── tests/        # PyTest test suite (unit and integration tests)
│   └── requirements.txt
├── frontend/         # React + Vite frontend kiosk UI
│   ├── src/          # React components and styling (TailwindCSS)
│   └── package.json  # NPM scripts and dependencies
├── healthcheck/      # Separate maintenance & diagnostic application
│   ├── backend/      # Diagnostics API, PayMongo sandboxing, and sensor logs
│   │   └── tests/    # Diagnostic PyTest test suite
│   └── frontend/     # Diagnostics dashboard UI (Vite + React)
├── firmware/         # Arduino controllers source code
│   ├── mega_bill/            # Arduino Mega #1 firmware (sorting + dispensing)
│   └── mega_coin_security/   # Arduino Mega #2 firmware (coin, keypad + security)
├── scripts/          # Automation scripts (setup_rpi.sh, deploy.sh)
├── systemd/          # Linux service configurations (coinnect.service)
└── reference/        # Technical specifications & documentation (10 documents)
```

---

## 🚀 Raspberry Pi (Linux) Commands

### 📦 Setup & Prerequisites
For a fresh Raspberry Pi installation, use the interactive setup script:
```bash
# Clone the repository (if not already done)
git clone https://github.com/your-username/coinnect.git
cd coinnect

# Run the setup script to install system packages, venv, and services
bash scripts/setup_rpi.sh
```
*Note: Remember to log out and log back in to apply group membership changes (dialout, video, gpio).*

---

### 🟢 Running the Applications (Manual Terminal Mode)

Ensure you have configured your environment files (`backend/.env` and `healthcheck/backend/.env`) prior to running.

#### 1. Main Backend (FastAPI)
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- **API URL**: `http://localhost:8000`
- **Swagger Docs**: `http://localhost:8000/docs`

#### 2. Main Frontend (React + Vite)
```bash
cd frontend
npm install # if running for the first time
npm run dev -- --host 0.0.0.0
```
- **UI URL**: `http://localhost:5173`

#### 3. Healthcheck Backend (Diagnostics API)
```bash
cd healthcheck/backend
source .venv/bin/activate
python -m uvicorn healthcheck_api.main:app --reload --host 0.0.0.0 --port 8010
```
- **Diagnostics API**: `http://localhost:8010`
- **Swagger Docs**: `http://localhost:8010/docs`

#### 4. Healthcheck Frontend (Diagnostics Dashboard)
```bash
cd healthcheck/frontend
npm install # if running for the first time
npm run dev -- --host 0.0.0.0
```
- **Dashboard URL**: `http://localhost:5174` (or `http://<rpi-ip>:5174` on your LAN)

---

### 🧪 Running the Tests

Ensure you run tests inside the corresponding folder and activated virtualenv.

#### 1. Main Backend Tests (PyTest)
```bash
cd backend
source venv/bin/activate
pytest
```

#### 2. Main Frontend Tests (Vitest)
```bash
cd frontend
npm run test
```

#### 3. Healthcheck Backend Tests (PyTest)
```bash
cd healthcheck/backend
source .venv/bin/activate
pytest
```

#### 4. Healthcheck Frontend Tests (Vitest)
```bash
cd healthcheck/frontend
npm run test
```

---

### ⚙️ Managing the systemd Service
In production, the kiosk UI and backend are managed by `systemd`.
```bash
# Check the status of the coinnect kiosk service
sudo systemctl status coinnect.service

# Start the service
sudo systemctl start coinnect.service

# Stop the service
sudo systemctl stop coinnect.service

# Restart the service
sudo systemctl restart coinnect.service

# Follow service logs in real time
sudo journalctl -u coinnect.service -f
```

---

## 💻 Windows PC (Development & Emulation) Commands

### 📦 Setup & Prerequisites
Ensure you have Python 3.11+ and Node.js 18+ installed on your system.

#### 1. Backend Virtual Environment Setup
```powershell
cd backend
.\setup_venv.bat
```

#### 2. Environment Configuration
Ensure `backend/.env` has `USE_MOCK_HARDWARE=true` and `USE_MOCK_SERIAL=true` enabled to bypass physical Raspberry Pi and Arduino connections:
```env
USE_MOCK_HARDWARE=true
USE_MOCK_SERIAL=true
```

---

### 🟢 Running the Applications

#### 1. Main Backend (FastAPI)
```powershell
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload
```
- **API URL**: `http://localhost:8000`
- **Swagger Docs**: `http://localhost:8000/docs`

#### 2. Main Frontend (React + Vite)
```powershell
cd frontend
npm install
npm run dev
```
- **UI URL**: `http://localhost:5173`

#### 3. Healthcheck Backend (Diagnostics API)
```powershell
cd healthcheck/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn healthcheck_api.main:app --reload --port 8010
```
- **Diagnostics API**: `http://localhost:8010`

#### 4. Healthcheck Frontend (Diagnostics Dashboard)
```powershell
cd healthcheck/frontend
npm install
npm run dev
```
- **Dashboard URL**: `http://localhost:5174`

---

### 🧪 Running the Tests

#### 1. Main Backend Tests (PyTest)
```powershell
cd backend
venv\Scripts\activate
pytest
```

#### 2. Main Frontend Tests (Vitest)
```powershell
cd frontend
npm run test
```

#### 3. Healthcheck Backend Tests (PyTest)
```powershell
cd healthcheck/backend
.venv\Scripts\activate
pytest
```

#### 4. Healthcheck Frontend Tests (Vitest)
```powershell
cd healthcheck/frontend
npm run test
```

---

## 🛠️ Arduino Firmware Deployment

Firmware uploading commands and serial port rules:
- **Arduino Mega #1 (Bill)**: Connects to `/dev/ttyUSB0` (or stable udev alias `/dev/coinnect_bill`) at `115200` baud.
- **Arduino Mega #2 (Coin/Security)**: Connects to `/dev/ttyACM0` (or stable udev alias `/dev/coinnect_coin`) at `115200` baud.

Upload firmware using the Arduino IDE or via the command line using `arduino-cli`:
```bash
# Compile and upload Bill Controller
arduino-cli compile --fqbn arduino:avr:mega firmware/mega_bill
arduino-cli upload -p /dev/ttyUSB0 --fqbn arduino:avr:mega firmware/mega_bill

# Compile and upload Coin & Security Controller
arduino-cli compile --fqbn arduino:avr:mega firmware/mega_coin_security
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:mega firmware/mega_coin_security
```

For custom udev rule setup, see [INSTRUCTIONS.md](./INSTRUCTIONS.md#section-4-serial-communication--udev-rules).
