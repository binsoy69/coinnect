#!/bin/bash

# Coinnect Raspberry Pi Setup Script
# This script automates the initial setup of the Coinnect system on a Raspberry Pi
#
# Usage:
#   1. Clone the repository: git clone https://github.com/<your-username>/coinnect.git
#   2. Run this script: cd coinnect && bash scripts/setup_rpi.sh
#
# This script will:
# - Install system dependencies
# - Set up Python virtual environment
# - Install Python dependencies
# - Configure user permissions
# - Install systemd service
# - Set up udev rules (with guidance)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

header() {
    echo
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    error "Please do not run this script as root or with sudo"
    error "The script will ask for sudo password when needed"
    exit 1
fi

# Welcome message
header "Coinnect Raspberry Pi Setup Script"
info "This script will set up the Coinnect system on your Raspberry Pi"
info "Repository: $(pwd)"
echo
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    info "Setup cancelled"
    exit 0
fi

# Step 1: Update system
header "Step 1: Updating System Packages"
info "This may take several minutes..."
sudo apt update
sudo apt upgrade -y

# Step 2: Install system dependencies
header "Step 2: Installing System Dependencies"

info "Installing Python and development tools..."
sudo apt install -y python3.11 python3-pip python3-venv git

info "Installing OpenCV and ML dependencies (for YOLO)..."
sudo apt install -y python3-opencv libatlas-base-dev

info "Installing Arduino CLI for firmware uploading..."
sudo apt install -y arduino arduino-cli

info "Installing system utilities..."
sudo apt install -y screen v4l-utils usbutils htop

# Step 3: Set up Python virtual environment
header "Step 3: Setting Up Python Virtual Environment"

VENV_PATH="$(pwd)/venv"

if [ -d "$VENV_PATH" ]; then
    warn "Virtual environment already exists at $VENV_PATH"
    read -p "Remove and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "Removing old virtual environment..."
        rm -rf "$VENV_PATH"
    fi
fi

if [ ! -d "$VENV_PATH" ]; then
    info "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
fi

info "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

info "Upgrading pip..."
pip install --upgrade pip

info "Installing Python dependencies..."
info "This may take 15-30 minutes (ultralytics and dependencies are large)..."
pip install -r backend/requirements.txt

info "Python environment set up successfully!"

# Step 4: Configure user permissions
header "Step 4: Configuring User Permissions"

info "Adding user to dialout group (for serial port access)..."
sudo usermod -a -G dialout "$USER"

info "Adding user to video group (for camera access)..."
sudo usermod -a -G video "$USER"

info "Adding user to gpio group (for GPIO access)..."
sudo usermod -a -G gpio "$USER" || warn "GPIO group not found (this is okay)"

warn "You will need to log out and back in for group changes to take effect"

# Step 5: Set up environment file
header "Step 5: Setting Up Environment Configuration"

ENV_FILE="$(pwd)/backend/.env"

if [ -f "$ENV_FILE" ]; then
    warn "Environment file already exists at $ENV_FILE"
else
    info "Creating .env file from template..."
    cp backend/.env.example "$ENV_FILE"
    info "Created $ENV_FILE"
    warn "⚠️  Remember to edit $ENV_FILE with your actual configuration!"
fi

# Step 6: Install systemd service
header "Step 6: Installing systemd Service"

info "Copying systemd service file..."
sudo cp systemd/coinnect.service /etc/systemd/system/

info "Reloading systemd daemon..."
sudo systemctl daemon-reload

info "Enabling service to start on boot..."
sudo systemctl enable coinnect.service

info "Service installed successfully!"
warn "Service will be started later after configuration is complete"

# Step 7: Set up udev rules
header "Step 7: Setting Up udev Rules for USB Devices"

info "Udev rules ensure consistent device naming for Arduino controllers"
echo

warn "Connect your Arduino Mega controllers now and press Enter..."
read -r

info "Detecting USB devices..."
echo
lsusb
echo

info "Listing serial devices..."
ls -l /dev/tty{USB,ACM}* 2>/dev/null || warn "No USB serial devices found yet"
echo

warn "You need to manually create udev rules based on your device IDs"
info "Follow the instructions in INSTRUCTIONS.md Section 4.3-4.4"
info "Example udev rules file location: /etc/udev/rules.d/99-coinnect-serial.rules"

# Step 8: Make scripts executable
header "Step 8: Setting Script Permissions"

info "Making deployment script executable..."
chmod +x scripts/deploy.sh

info "Script permissions set!"

# Step 9: Create necessary directories
header "Step 9: Creating Required Directories"

info "Creating data directory for database..."
mkdir -p data

info "Creating ML models directory..."
mkdir -p backend/app/ml/models

info "Creating logs directory..."
mkdir -p logs

info "Directories created!"

# Setup complete!
header "Setup Complete!"

echo
info "Coinnect has been set up successfully!"
echo
info "Next steps:"
echo "  1. Edit backend/.env with your configuration"
echo "  2. Set up udev rules for USB devices (see INSTRUCTIONS.md Section 4)"
echo "  3. Upload Arduino firmware (see INSTRUCTIONS.md Section 6)"
echo "  4. Log out and back in (for group permissions to take effect)"
echo "  5. Start the service: sudo systemctl start coinnect.service"
echo "  6. Check status: sudo systemctl status coinnect.service"
echo "  7. View logs: sudo journalctl -u coinnect.service -f"
echo
warn "⚠️  IMPORTANT: Log out and back in before starting the service!"
echo
info "For detailed instructions, see INSTRUCTIONS.md"
info "For troubleshooting help, see INSTRUCTIONS.md Section 10"
echo
