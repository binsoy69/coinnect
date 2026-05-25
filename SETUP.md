# Coinnect Setup Guide

This guide walks through setting up the development environment for the Coinnect project.

## Prerequisites

- **Python 3.11+** (for backend)
- **Node.js 18+** (for frontend)
- **Git** (version control)

## Backend Setup

### 1. Install Python 3.11+

Download and install Python from [python.org](https://www.python.org/downloads/)

Verify installation:
```bash
python --version  # Should show 3.11 or higher
```

### 2. Create Virtual Environment

**On Linux/macOS:**
```bash
cd backend
./setup_venv.sh
```

**On Windows:**
```cmd
cd backend
setup_venv.bat
```

**Manual Setup (if scripts fail):**
```bash
cd backend
python -m venv venv

# Activate environment:
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies:
pip install -r requirements.txt
```

On a Raspberry Pi using real GPIO hardware, rerun `pip install -r requirements.txt`
inside the activated backend virtualenv after pulling dependency updates. The Pi
GPIO compatibility package is installed only on Linux ARM platforms.

For the Paperang P1 receipt printer, install the Raspberry Pi Bluetooth and image
processing packages before testing the printer:

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  python3-dev \
  python3-venv \
  python3-bluez \
  python3-numpy \
  python3-scipy \
  python3-skimage \
  python3-numba \
  python3-pil \
  python3-pilkit \
  libbluetooth-dev \
  libhidapi-dev
```

Clone the tested Paperang support library near the kiosk checkout:

```bash
mkdir -p vendor
git clone https://github.com/tinyprinter/python-paperang.git vendor/python-paperang
```

For a manual printer check, follow the support repository's test flow from that
checkout after Bluetooth is enabled and the printer is powered on:

```bash
cd vendor/python-paperang
python3 testprint.py
```

If the healthcheck page reports `No module named 'bluetooth'`, install the
healthcheck backend requirements into the same virtualenv used to run uvicorn:

```bash
source venv/bin/activate
pip install -r healthcheck/backend/requirements.txt
python -c "import bluetooth; print('bluetooth module available')"
```

The future backend printer driver should keep printer settings in `backend/.env`.
Use `PAPERANG_MAC_ADDRESS` when the printer MAC address is known, `PAPERANG_ENABLED`
to enable receipt printing, and `PAPERANG_DENSITY` if print density needs tuning.
Do not hardcode the MAC address in source code.

### 3. Configure Environment

Copy the example environment file:
```bash
cp backend/.env.example backend/.env
```

Edit `.env` with your configuration settings.

### 4. Run Backend (FastAPI)

```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn app.main:app --reload
```

Backend will be available at: `http://localhost:8000`
API docs at: `http://localhost:8000/docs`

## Frontend Setup

### 1. Install Node.js

Download and install Node.js from [nodejs.org](https://nodejs.org/)

Verify installation:
```bash
node --version  # Should show 18 or higher
npm --version
```

### 2. Install Dependencies

Frontend dependencies are already installed! If you need to reinstall:
```bash
cd frontend
npm install
```

### 3. Run Frontend (Vite + React)

```bash
cd frontend
npm run dev
```

Frontend will be available at: `http://localhost:5173` (or next available port)

## Verification

### Backend Test
```bash
cd backend
source venv/bin/activate
python --version  # Should be 3.11+
python -c "import fastapi, uvicorn, pyserial, ultralytics; print('✓ All imports successful')"
```

### Frontend Test
```bash
cd frontend
npm run dev
```

Visit `http://localhost:5173` - you should see the Coinnect welcome page with:
- Premium dark theme
- Glassmorphism cards
- Animated components
- Service selection grid

## Project Structure

```
coinnect/
├── backend/              # Python FastAPI backend
│   ├── app/             # Application code
│   ├── tests/           # PyTest test suite
│   ├── requirements.txt # Python dependencies
│   └── setup_venv.*     # Virtual environment setup scripts
├── frontend/            # React + Vite frontend
│   ├── src/            # Source code
│   ├── public/         # Static assets
│   └── package.json    # Node dependencies
├── firmware/           # Arduino firmware
│   ├── mega_bill/              # Bill controller
│   └── mega_coin_security/     # Coin & security controller
└── reference/          # Technical documentation

```

## Development Tools

### Backend
- **FastAPI**: Web framework
- **PySerial**: Arduino communication
- **Ultralytics YOLO**: ML bill authentication
- **PyTest**: Testing framework

### Frontend
- **Vite**: Build tool & dev server
- **React 18**: UI framework
- **TailwindCSS**: Utility-first CSS framework
- **Framer Motion**: Animation library
- **Lucide React**: Icon library

## Next Steps

Refer to [ROADMAP.md](./ROADMAP.md) for the development plan. Phase 0 is complete!

Ready to proceed to:
- **Phase 1**: High-Impact UI/UX (Frontend Priority)
- **Phase 2**: Hardware Drivers & Emulation

## Troubleshooting

### Python not found
- Ensure Python 3.11+ is installed and in your PATH
- Try `python3` instead of `python` on Linux/macOS
- On Windows, use `py` launcher: `py --version`

### npm install fails
- Clear npm cache: `npm cache clean --force`
- Delete `node_modules` and `package-lock.json`, then reinstall

### Port already in use
- Frontend: Vite will automatically use next available port
- Backend: Change port with `uvicorn app.main:app --port 8001`

### `No module named 'RPi'` on Raspberry Pi
This means the backend virtualenv cannot import an `RPi.GPIO` provider while
`USE_MOCK_HARDWARE=false`.

```bash
cd ~/coinnect/backend
source venv/bin/activate
pip install -r requirements.txt
python -c "import RPi.GPIO as GPIO; print('GPIO import ok')"
```

For development without physical GPIO hardware, set `USE_MOCK_HARDWARE=true`
in `backend/.env`.

## Additional Resources

- [CLAUDE.md](./CLAUDE.md) - Claude Code guidance
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [reference/](./reference/) - Technical specifications
