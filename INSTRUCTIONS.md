# Coinnect Raspberry Pi Setup Instructions

This guide provides step-by-step instructions for deploying the Coinnect kiosk system from your Windows development machine to a Raspberry Pi in production.

**Development Workflow**: Windows (Development) → GitHub (Version Control) → Raspberry Pi (Production)

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Windows Development Environment Setup](#2-windows-development-environment-setup)
3. [Raspberry Pi Initial Setup](#3-raspberry-pi-initial-setup)
4. [Hardware Configuration](#4-hardware-configuration)
5. [Backend Deployment](#5-backend-deployment)
6. [Firmware Deployment (Arduino)](#6-firmware-deployment-arduino)
7. [System Services Setup (systemd)](#7-system-services-setup-systemd)
8. [Testing & Verification](#8-testing--verification)
9. [Development Workflow](#9-development-workflow)
10. [Troubleshooting](#10-troubleshooting)
11. [Maintenance & Updates](#11-maintenance--updates)

---

## 1. Prerequisites

### Hardware Requirements

- **Raspberry Pi 4 or 5** (4GB+ RAM recommended)
- **2× Arduino Mega 2560** boards
  - Arduino #1: Bill Controller (sorting + dispensing)
  - Arduino #2: Coin & Security Controller
- **3× USB cables** (2× USB-A to USB-B for Arduinos, 1× for camera)
- **USB Camera** (1080p recommended for bill authentication)
- **MicroSD Card** (32GB+ recommended)
- **Power Supply** (ATX PSU or 5V 3A+ for Raspberry Pi)
- **Ethernet cable** (for initial setup) or Wi-Fi credentials

### Software Requirements

**On Windows:**
- Git for Windows
- Python 3.11 or higher
- Visual Studio Code (recommended) with Python extensions
- GitHub account with repository access

**On Raspberry Pi (will be installed during setup):**
- Raspberry Pi OS Lite (64-bit)
- Python 3.11+
- Arduino CLI
- Git

---

## 2. Windows Development Environment Setup

### 2.1 Install Git for Windows

1. Download Git from [https://git-scm.com/download/win](https://git-scm.com/download/win)
2. Run installer with default options
3. Verify installation:
   ```cmd
   git --version
   ```

### 2.2 Install Python 3.11+

1. Download Python from [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"
3. Verify installation:
   ```cmd
   python --version
   ```

### 2.3 Clone Repository

1. Open Command Prompt or PowerShell
2. Navigate to your projects directory:
   ```cmd
   cd D:\projects
   ```
3. Clone the repository:
   ```cmd
   git clone https://github.com/<your-username>/coinnect.git
   cd coinnect
   ```

### 2.4 Setup Python Virtual Environment

1. Create virtual environment:
   ```cmd
   python -m venv venv
   ```
2. Activate virtual environment:
   ```cmd
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```cmd
   pip install -r backend\requirements.txt
   ```

### 2.5 Configure Environment Variables

1. Copy the environment template:
   ```cmd
   copy backend\.env.example backend\.env
   ```
2. Edit `backend\.env` and configure settings for your environment
   - For local development, you can use mock serial ports
   - API keys are only needed for online payment features

---

## 3. Raspberry Pi Initial Setup

### 3.1 Flash Raspberry Pi OS

1. Download **Raspberry Pi Imager** from [https://www.raspberrypi.com/software/](https://www.raspberrypi.com/software/)
2. Insert microSD card into your computer
3. In Raspberry Pi Imager:
   - **OS**: Choose "Raspberry Pi OS Lite (64-bit)" - recommended
   - **Storage**: Select your microSD card
   - Click **Settings** (gear icon):
     - Set hostname: `coinnect-kiosk`
     - Enable SSH (use password authentication)
     - Set username: `pi` and password
     - Configure Wi-Fi (optional)
     - Set timezone
4. Click **Write** and wait for completion

### 3.2 Boot and Connect

1. Insert microSD card into Raspberry Pi
2. Connect Ethernet cable (or ensure Wi-Fi is configured)
3. Power on the Raspberry Pi
4. Wait 1-2 minutes for first boot
5. Find Raspberry Pi IP address:
   - Use `arp -a` on Windows
   - Or use hostname: `coinnect-kiosk.local`

### 3.3 SSH Connection

1. Open PowerShell or Command Prompt:
   ```cmd
   ssh pi@coinnect-kiosk.local
   ```
   Or use IP address:
   ```cmd
   ssh pi@192.168.1.xxx
   ```
2. Accept fingerprint (type `yes`)
3. Enter password

### 3.4 Update System

```bash
sudo apt update
sudo apt upgrade -y
```

This may take 5-15 minutes depending on your internet connection.

### 3.5 Install Dependencies

**Install Python and development tools:**
```bash
sudo apt install -y python3.11 python3-pip python3-venv git
sudo apt install -y python3-opencv libatlas-base-dev  # For YOLO ML
```

**Install Arduino CLI for firmware uploading:**
```bash
sudo apt install -y arduino arduino-cli
```

**Install system utilities:**
```bash
sudo apt install -y screen v4l-utils usbutils  # For testing and debugging
```

### 3.6 Configure System Settings

**Set timezone (if not done during imaging):**
```bash
sudo raspi-config
# Navigate to: Localisation Options → Timezone
```

**Expand filesystem (if needed):**
```bash
sudo raspi-config
# Navigate to: Advanced Options → Expand Filesystem
```

**Reboot to apply changes:**
```bash
sudo reboot
```

---

## 4. Hardware Configuration

### 4.1 Connect Hardware

1. **Arduino Mega #1 (Bill Controller)**
   - Connect via USB to Raspberry Pi
   - Should appear as `/dev/ttyUSB0`

2. **Arduino Mega #2 (Coin/Security Controller)**
   - Connect via USB to Raspberry Pi
   - Should appear as `/dev/ttyACM0`

3. **USB Camera**
   - Connect to Raspberry Pi USB port
   - Should appear as `/dev/video0`

### 4.2 Verify USB Devices

**Check serial ports:**
```bash
ls -l /dev/tty{USB,ACM}*
```
Expected output:
```
crw-rw---- 1 root dialout ... /dev/ttyUSB0
crw-rw---- 1 root dialout ... /dev/ttyACM0
```

**Check USB devices:**
```bash
lsusb
```
You should see entries for:
- QinHeng Electronics CH340 (or similar USB-to-Serial)
- Arduino SA Mega 2560

**Check camera:**
```bash
ls -l /dev/video*
v4l2-ctl --list-devices
```

### 4.3 Identify USB Device IDs

To create reliable udev rules, identify the exact vendor and product IDs:

**For Arduino #1:**
```bash
udevadm info --name=/dev/ttyUSB0 --attribute-walk | grep -E "idVendor|idProduct"
```

**For Arduino #2:**
```bash
udevadm info --name=/dev/ttyACM0 --attribute-walk | grep -E "idVendor|idProduct"
```

Note these IDs for the next step.

### 4.4 Create udev Rules

Create a udev rules file for persistent device naming:

```bash
sudo nano /etc/udev/rules.d/99-coinnect-serial.rules
```

Add the following content (adjust vendor/product IDs based on your devices):

```
# Arduino Mega #1 (Bill Controller) - CH340 USB-to-Serial adapter
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="coinnect_bill", MODE="0666", GROUP="dialout"

# Arduino Mega #2 (Coin/Security Controller) - Genuine Arduino
SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", ATTRS{idProduct}=="0042", SYMLINK+="coinnect_coin", MODE="0666", GROUP="dialout"
```

**Reload udev rules:**
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

**Verify symlinks were created:**
```bash
ls -l /dev/coinnect_*
```
Expected output:
```
lrwxrwxrwx 1 root root ... /dev/coinnect_bill -> ttyUSB0
lrwxrwxrwx 1 root root ... /dev/coinnect_coin -> ttyACM0
```

### 4.5 Grant User Permissions

Add your user to required groups:

```bash
# Serial port access
sudo usermod -a -G dialout $USER

# Camera access
sudo usermod -a -G video $USER

# GPIO access (if needed for RPi-controlled hardware)
sudo usermod -a -G gpio $USER
```

**Apply group changes** (choose one):
- Option 1: Log out and back in
- Option 2: Run `newgrp dialout` (temporary for current session)
- Option 3: Reboot: `sudo reboot`

---

## 5. Backend Deployment

### 5.1 Clone Repository on Raspberry Pi

```bash
cd /home/pi
git clone https://github.com/<your-username>/coinnect.git
cd coinnect
```

### 5.2 Create Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

This will install:
- FastAPI (REST API framework)
- uvicorn (ASGI server)
- pyserial (Arduino communication)
- ultralytics (YOLO ML models)
- pytest (testing framework)
- Other dependencies

**Note**: Installing `ultralytics` and its dependencies may take 10-20 minutes on Raspberry Pi.

### 5.3 Configure Environment Variables

Create the production environment file:

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Configure the following settings:

```env
# Serial Port Configuration (use symlinks for reliability)
SERIAL_PORT_BILL=/dev/coinnect_bill
SERIAL_PORT_COIN=/dev/coinnect_coin
# Fallback to direct paths if symlinks not working:
# SERIAL_PORT_BILL=/dev/ttyUSB0
# SERIAL_PORT_COIN=/dev/ttyACM0

BAUD_RATE=115200

# Camera Configuration
CAMERA_INDEX=0

# ML Model Path
YOLO_MODEL_PATH=/home/pi/coinnect/backend/app/ml/models/bill_auth.pt

# Payment Provider API Keys (for online mode)
GCASH_API_KEY=your_gcash_api_key_here
MAYA_API_KEY=your_maya_api_key_here

# Application Settings
LOG_LEVEL=INFO
ENABLE_OFFLINE_MODE=true

# Server Configuration
HOST=0.0.0.0
PORT=8000
```

Save and exit (Ctrl+X, then Y, then Enter).

### 5.4 Test Backend Manually

Before setting up systemd, test the backend manually:

```bash
cd /home/pi/coinnect/backend
source ../venv/bin/activate
python main.py
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Press Ctrl+C to stop the server.

If you encounter errors, see [Section 10: Troubleshooting](#10-troubleshooting).

---

## 6. Firmware Deployment (Arduino)

### 6.1 Install Arduino Libraries

Install required libraries for both Arduino controllers:

```bash
arduino-cli lib install ArduinoJson
arduino-cli lib install Servo
```

### 6.2 Compile and Upload Firmware

**Arduino Mega #1 (Bill Controller):**

```bash
cd /home/pi/coinnect/firmware/mega_bill

# Compile
arduino-cli compile --fqbn arduino:avr:mega .

# Upload to Bill Controller
arduino-cli upload --port /dev/ttyUSB0 --fqbn arduino:avr:mega .
```

**Arduino Mega #2 (Coin/Security Controller):**

```bash
cd /home/pi/coinnect/firmware/mega_coin_security

# Compile
arduino-cli compile --fqbn arduino:avr:mega .

# Upload to Coin/Security Controller
arduino-cli upload --port /dev/ttyACM0 --fqbn arduino:avr:mega .
```

### 6.3 Verify Firmware Communication

Test basic communication with both Arduinos:

**Test Arduino #1 (Bill Controller):**
```bash
# Send PING command
echo '{"cmd":"PING"}' > /dev/ttyUSB0

# Read response (use screen or cat with timeout)
timeout 2 cat /dev/ttyUSB0
```

Expected response:
```json
{"status":"OK","message":"PONG"}
```
or
```json
{"status":"OK","controller":"BILL"}
```

**Test Arduino #2 (Coin/Security Controller):**
```bash
# Send PING command
echo '{"cmd":"PING"}' > /dev/ttyACM0

# Read response
timeout 2 cat /dev/ttyACM0
```

Expected response:
```json
{"status":"OK","message":"PONG"}
```
or
```json
{"status":"OK","controller":"COIN_SECURITY"}
```

**Test VERSION command for detailed info:**
```bash
echo '{"cmd":"VERSION"}' > /dev/ttyUSB0
timeout 2 cat /dev/ttyUSB0
```

Expected response:
```json
{"status":"OK","version":"2.0.0","controller":"BILL"}
```

**Note:** If responses are garbled or not received:
- Verify baud rate is 115200 in both firmware and backend
- Check that firmware uploaded successfully
- Press the reset button on Arduino and try again
- See [Troubleshooting](#10-troubleshooting) for more help

---

## 7. System Services Setup (systemd)

### 7.1 Create systemd Service File

Create a systemd service to run the backend automatically on boot:

```bash
sudo nano /etc/systemd/system/coinnect.service
```

Add the following content:

```ini
[Unit]
Description=Coinnect Kiosk Backend Service
Documentation=https://github.com/<your-username>/coinnect
After=network.target multi-user.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/coinnect/backend
Environment="PATH=/home/pi/coinnect/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/pi/coinnect/venv/bin/python main.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=coinnect

# Security hardening (optional)
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Save and exit (Ctrl+X, then Y, then Enter).

### 7.2 Enable and Start Service

**Reload systemd to recognize the new service:**
```bash
sudo systemctl daemon-reload
```

**Enable service to start on boot:**
```bash
sudo systemctl enable coinnect.service
```

**Start the service:**
```bash
sudo systemctl start coinnect.service
```

**Check service status:**
```bash
sudo systemctl status coinnect.service
```

Expected output:
```
● coinnect.service - Coinnect Kiosk Backend Service
     Loaded: loaded (/etc/systemd/system/coinnect.service; enabled)
     Active: active (running) since ...
```

### 7.3 View Service Logs

**Real-time log monitoring:**
```bash
sudo journalctl -u coinnect.service -f
```
Press Ctrl+C to stop following logs.

**View recent logs:**
```bash
sudo journalctl -u coinnect.service -n 50
```

**View logs since last boot:**
```bash
sudo journalctl -u coinnect.service -b
```

### 7.4 Service Management Commands

**Stop the service:**
```bash
sudo systemctl stop coinnect.service
```

**Restart the service:**
```bash
sudo systemctl restart coinnect.service
```

**Disable autostart:**
```bash
sudo systemctl disable coinnect.service
```

**Re-enable autostart:**
```bash
sudo systemctl enable coinnect.service
```

---

## 8. Testing & Verification

### 8.1 End-to-End System Test

1. **Verify all services are running:**
   ```bash
   sudo systemctl status coinnect.service
   ```

2. **Test API endpoints:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/status
   ```

3. **Test serial communication:**
   - Backend should automatically connect to both Arduinos on startup
   - Check logs for connection confirmations:
     ```bash
     sudo journalctl -u coinnect.service | grep -i "arduino\|serial"
     ```

### 8.2 Hardware Tests

**Bill Sorting Test:**
- Send HOME command to initialize sorting mechanism
- Send SORT command for each denomination
- Verify carriage moves to correct positions

**Bill Dispensing Test:**
- Send DISPENSE_STATUS to check each dispenser unit
- Send DISPENSE command to test each denomination
- Verify bills are dispensed correctly

**Coin System Test:**
- Insert coins into acceptor
- Verify backend receives COIN_IN events
- Test COIN_DISPENSE commands for each denomination

**Security System Test:**
- Trigger shock sensor (gentle tap on case)
- Verify TAMPER event received
- Test SECURITY_LOCK and SECURITY_UNLOCK commands

### 8.3 Camera and ML Test

1. **Check camera access:**
   ```bash
   v4l2-ctl --list-devices
   ls -l /dev/video*
   ```

2. **Test bill authentication:**
   - Insert test bills
   - Check ML inference logs
   - Verify correct denomination detected

---

## 9. Development Workflow

### 9.1 Daily Development Cycle

**On Windows (Development):**

1. Make code changes
2. Test locally (optional)
3. Commit changes:
   ```cmd
   git add .
   git commit -m "Implement feature X"
   ```
4. Push to GitHub:
   ```cmd
   git push origin main
   ```

**On Raspberry Pi (Deployment):**

1. SSH into Raspberry Pi:
   ```cmd
   ssh pi@coinnect-kiosk.local
   ```

2. Pull latest changes:
   ```bash
   cd /home/pi/coinnect
   git pull origin main
   ```

3. If dependencies changed:
   ```bash
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```

4. Restart service:
   ```bash
   sudo systemctl restart coinnect.service
   ```

5. Monitor logs for issues:
   ```bash
   sudo journalctl -u coinnect.service -f
   ```

### 9.2 Quick Deployment Script

You can use the included deployment script for faster updates:

```bash
cd /home/pi/coinnect
./scripts/deploy.sh
```

This script will:
- Pull latest code from GitHub
- Install any new dependencies
- Restart the service
- Show logs

### 9.3 Firmware Updates

When you update Arduino firmware:

1. Push firmware changes to GitHub
2. Pull on Raspberry Pi
3. Stop the backend service:
   ```bash
   sudo systemctl stop coinnect.service
   ```
4. Upload new firmware (see [Section 6](#6-firmware-deployment-arduino))
5. Start the backend service:
   ```bash
   sudo systemctl start coinnect.service
   ```

---

## 10. Troubleshooting

### Serial Communication Issues

#### Serial ports not detected

**Problem:** `/dev/ttyUSB0` or `/dev/ttyACM0` not found

**Solutions:**
- Check USB connections are secure
- Run `dmesg | tail` to see kernel messages about USB devices
- Verify Arduino boards are powered (LED should be on)
- Try different USB ports on Raspberry Pi
- Check USB cable quality (some cables are power-only)

**Diagnostic commands:**
```bash
lsusb                    # List all USB devices
dmesg | grep -i tty      # Check for serial device messages
ls -l /dev/tty*          # List all tty devices
```

#### Permission denied on serial ports

**Problem:** `Permission denied: '/dev/ttyUSB0'`

**Solutions:**
- Add user to dialout group:
  ```bash
  sudo usermod -a -G dialout $USER
  ```
- Log out and back in, or run:
  ```bash
  newgrp dialout
  ```
- Check permissions:
  ```bash
  ls -l /dev/ttyUSB0 /dev/ttyACM0
  ```
- Temporarily test with elevated permissions:
  ```bash
  sudo chmod 666 /dev/ttyUSB0 /dev/ttyACM0
  ```

#### Arduino not responding

**Problem:** No response to PING or other commands

**Solutions:**
- Verify baud rate matches (115200) in both firmware and backend
- Test manually with screen:
  ```bash
  screen /dev/ttyUSB0 115200
  ```
  Type: `{"cmd":"PING"}` and press Enter

- Press reset button on Arduino and check for startup message
- Re-flash firmware with correct settings
- Check if Arduino is running correct program:
  ```bash
  echo '{"cmd":"VERSION"}' > /dev/ttyUSB0
  timeout 2 cat /dev/ttyUSB0
  ```

#### Wrong device assigned to port

**Problem:** Bill controller on `/dev/ttyACM0` instead of `/dev/ttyUSB0`

**Solutions:**
- Check which Arduino is which:
  ```bash
  echo '{"cmd":"VERSION"}' > /dev/ttyUSB0
  timeout 2 cat /dev/ttyUSB0
  ```
  Response will include `"controller":"BILL"` or `"controller":"COIN_SECURITY"`

- Update udev rules with correct vendor/product IDs
- Swap USB ports if needed
- Update `.env` file to match actual ports

### Backend Issues

#### Backend won't start

**Problem:** Service fails to start or crashes immediately

**Solutions:**
- Check logs for errors:
  ```bash
  sudo journalctl -u coinnect.service -n 50
  ```
- Verify Python virtual environment is correctly set in systemd unit
- Check `.env` file exists and has correct paths:
  ```bash
  cat /home/pi/coinnect/backend/.env
  ```
- Test manually to see full error output:
  ```bash
  cd /home/pi/coinnect/backend
  source ../venv/bin/activate
  python main.py
  ```

#### Import errors

**Problem:** `ModuleNotFoundError` or `ImportError`

**Solutions:**
- Verify dependencies are installed:
  ```bash
  source /home/pi/coinnect/venv/bin/activate
  pip list | grep fastapi
  pip list | grep pyserial
  ```
- Reinstall requirements:
  ```bash
  pip install --upgrade -r backend/requirements.txt
  ```
- Check Python version:
  ```bash
  python --version  # Should be 3.11+
  ```

### Hardware Issues

#### YOLO model not loading

**Problem:** ML model fails to load or gives errors

**Solutions:**
- Check model file exists:
  ```bash
  ls -l /home/pi/coinnect/backend/app/ml/models/
  ```
- Verify path in `.env` file matches actual location
- Check ultralytics installation:
  ```bash
  pip show ultralytics
  ```
- Test model loading in Python:
  ```python
  from ultralytics import YOLO
  model = YOLO('/path/to/model.pt')
  ```

#### Camera not working

**Problem:** Camera not detected or cannot capture images

**Solutions:**
- List video devices:
  ```bash
  ls -l /dev/video*
  v4l2-ctl --list-devices
  ```
- Check camera permissions:
  ```bash
  sudo usermod -a -G video $USER
  newgrp video
  ```
- Try different CAMERA_INDEX values in `.env` (0, 1, 2)
- Test camera with:
  ```bash
  v4l2-ctl --device=/dev/video0 --list-formats-ext
  ```
- Check USB power (some cameras need more power)

### Service Issues

#### Service crashes on boot

**Problem:** Service starts but crashes shortly after

**Solutions:**
- Increase restart delay in systemd unit:
  ```ini
  RestartSec=30
  ```
- Add dependency on multi-user target:
  ```ini
  After=multi-user.target network-online.target
  ```
- Check if USB devices take time to enumerate
- Monitor startup logs:
  ```bash
  sudo journalctl -u coinnect.service -b
  ```

#### Service works manually but not as systemd

**Problem:** Backend runs fine manually but fails under systemd

**Solutions:**
- Verify `WorkingDirectory` is correct
- Check `Environment` PATH includes venv/bin
- Ensure user has permissions for all devices
- Test with same user:
  ```bash
  sudo -u pi /home/pi/coinnect/venv/bin/python /home/pi/coinnect/backend/main.py
  ```

### Firmware Issues

#### Upload fails

**Problem:** `arduino-cli upload` fails or times out

**Solutions:**
- Verify port is correct:
  ```bash
  arduino-cli board list
  ```
- Check board FQBN: `arduino:avr:mega`
- Try manual reset during upload:
  - Hold reset button
  - Start upload command
  - Release reset when "Uploading..." appears

- Check serial port is not in use:
  ```bash
  sudo lsof /dev/ttyUSB0
  ```
- Stop backend service before uploading:
  ```bash
  sudo systemctl stop coinnect.service
  ```

#### Garbled serial output

**Problem:** Random characters or corrupted JSON responses

**Solutions:**
- Verify 115200 baud rate in `Serial.begin(115200)`
- Check for baud rate mismatch between firmware and backend
- Ensure both sides use same line terminator (`\n`)
- Check for hardware issues (cable quality, loose connections)
- Test with simple echo program first

### System Issues

#### Raspberry Pi won't boot

**Problem:** No display output, no SSH access

**Solutions:**
- Check SD card integrity:
  - Re-flash SD card
  - Try different SD card
- Verify power supply is adequate (5V 3A minimum for Pi 4)
- Check for undervoltage warning:
  - Rainbow square icon on screen
  - Lightning bolt icon on screen
- Remove all USB devices and test
- Check HDMI connection if using display

#### Disk space full

**Problem:** `/dev/root` at 100% usage

**Solutions:**
- Check space usage:
  ```bash
  df -h
  du -sh /home/pi/* /var/*
  ```
- Clean old logs:
  ```bash
  sudo journalctl --vacuum-time=7d
  sudo journalctl --vacuum-size=100M
  ```
- Clear pip cache:
  ```bash
  pip cache purge
  ```
- Remove old YOLO training data if present:
  ```bash
  rm -rf ~/coinnect/backend/app/ml/runs/
  ```
- Check for large log files:
  ```bash
  find /var/log -type f -size +10M
  ```

---

## 11. Maintenance & Updates

### 11.1 Regular Maintenance Tasks

**Weekly:**
- Check service logs for errors
- Verify disk space: `df -h`
- Monitor system temperature: `vcgencmd measure_temp`

**Monthly:**
- Update system packages:
  ```bash
  sudo apt update
  sudo apt upgrade -y
  sudo reboot
  ```
- Update Python dependencies:
  ```bash
  source /home/pi/coinnect/venv/bin/activate
  pip install --upgrade -r backend/requirements.txt
  ```
- Clean old logs:
  ```bash
  sudo journalctl --vacuum-time=30d
  ```

**Quarterly:**
- Backup configuration files:
  ```bash
  # Backup .env file
  cp /home/pi/coinnect/backend/.env ~/backup/.env.backup

  # Backup systemd unit
  sudo cp /etc/systemd/system/coinnect.service ~/backup/

  # Backup udev rules
  sudo cp /etc/udev/rules.d/99-coinnect-serial.rules ~/backup/
  ```
- Test hardware components (bill dispenser, coin acceptor, security sensors)
- Check for firmware updates

### 11.2 Update Python Dependencies

When new dependencies are added:

```bash
cd /home/pi/coinnect
source venv/bin/activate
pip install --upgrade -r backend/requirements.txt
sudo systemctl restart coinnect.service
```

### 11.3 Flash New Firmware

When firmware is updated:

```bash
# Stop backend service
sudo systemctl stop coinnect.service

# Upload new firmware
cd /home/pi/coinnect/firmware/mega_bill
arduino-cli upload --port /dev/ttyUSB0 --fqbn arduino:avr:mega .

cd /home/pi/coinnect/firmware/mega_coin_security
arduino-cli upload --port /dev/ttyACM0 --fqbn arduino:avr:mega .

# Start backend service
sudo systemctl start coinnect.service

# Monitor logs
sudo journalctl -u coinnect.service -f
```

### 11.4 Backup Strategy

**Configuration files to backup:**
- `/home/pi/coinnect/backend/.env`
- `/etc/systemd/system/coinnect.service`
- `/etc/udev/rules.d/99-coinnect-serial.rules`

**Database/logs to backup (if applicable):**
- Transaction logs
- Inventory records
- YOLO model files (if custom trained)

**Create backup script:**
```bash
#!/bin/bash
BACKUP_DIR=~/coinnect_backups/$(date +%Y%m%d)
mkdir -p $BACKUP_DIR
cp /home/pi/coinnect/backend/.env $BACKUP_DIR/
sudo cp /etc/systemd/system/coinnect.service $BACKUP_DIR/
sudo cp /etc/udev/rules.d/99-coinnect-serial.rules $BACKUP_DIR/
echo "Backup completed: $BACKUP_DIR"
```

### 11.5 Monitor System Health

**Check system status:**
```bash
# Service health
sudo systemctl status coinnect.service

# System resources
htop

# Disk usage
df -h

# Temperature
vcgencmd measure_temp

# Memory
free -h

# Uptime
uptime
```

**Set up alerts (optional):**
- Configure email alerts for service failures
- Set up monitoring with Prometheus/Grafana
- Use systemd email notifications on service failure

---

## Additional Resources

- **Coinnect Documentation**: See `CLAUDE.md`, `ARCHITECTURE.md`, `PROJECT.md` in repository
- **Reference Documents**: See `reference/` directory for detailed technical specifications
- **GitHub Issues**: Report bugs and request features at your repository's Issues page
- **Raspberry Pi Documentation**: [https://www.raspberrypi.com/documentation/](https://www.raspberrypi.com/documentation/)
- **Arduino CLI Documentation**: [https://arduino.github.io/arduino-cli/](https://arduino.github.io/arduino-cli/)

---

## Quick Reference Commands

```bash
# Service Management
sudo systemctl status coinnect.service    # Check status
sudo systemctl restart coinnect.service   # Restart service
sudo journalctl -u coinnect.service -f    # View logs

# Deployment
cd /home/pi/coinnect
git pull origin main                      # Pull latest code
sudo systemctl restart coinnect.service   # Restart service

# Testing
echo '{"cmd":"PING"}' > /dev/ttyUSB0      # Test Arduino #1
timeout 2 cat /dev/ttyUSB0                # Read response
curl http://localhost:8000/health         # Test API

# Debugging
dmesg | tail                              # Check kernel messages
lsusb                                     # List USB devices
ls -l /dev/tty*                          # List serial ports
```

---

**Document Version**: 1.0
**Last Updated**: 2026-02-04
**Maintained by**: Coinnect Development Team
