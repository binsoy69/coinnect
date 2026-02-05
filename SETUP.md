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

## Additional Resources

- [CLAUDE.md](./CLAUDE.md) - Claude Code guidance
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [reference/](./reference/) - Technical specifications
