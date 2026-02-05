#!/bin/bash

# Coinnect Deployment Script
# This script pulls the latest code from GitHub and restarts the service
# Usage: ./scripts/deploy.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REPO_DIR="/home/pi/coinnect"
SERVICE_NAME="coinnect.service"
VENV_PATH="$REPO_DIR/venv"

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

# Check if running on Raspberry Pi
if [ ! -d "$REPO_DIR" ]; then
    error "Repository directory not found: $REPO_DIR"
    error "Please run this script on the Raspberry Pi with Coinnect installed"
    exit 1
fi

# Change to repository directory
cd "$REPO_DIR" || exit 1
info "Changed to directory: $REPO_DIR"

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    warn "You have uncommitted local changes!"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Deployment cancelled"
        exit 0
    fi
fi

# Fetch latest changes
info "Fetching latest changes from GitHub..."
git fetch origin

# Show what will be updated
COMMITS_BEHIND=$(git rev-list HEAD..origin/main --count)
if [ "$COMMITS_BEHIND" -eq 0 ]; then
    info "Already up to date! No new commits to pull."
    read -p "Restart service anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Deployment cancelled"
        exit 0
    fi
else
    info "There are $COMMITS_BEHIND new commit(s) to pull"
    echo
    git log HEAD..origin/main --oneline --no-decorate
    echo
fi

# Pull latest changes
info "Pulling latest code from GitHub..."
git pull origin main

# Check if requirements.txt changed
REQUIREMENTS_CHANGED=false
if git diff HEAD@{1} HEAD --name-only | grep -q "backend/requirements.txt"; then
    REQUIREMENTS_CHANGED=true
    warn "requirements.txt has changed - will update dependencies"
fi

# Activate virtual environment and update dependencies if needed
if [ "$REQUIREMENTS_CHANGED" = true ]; then
    info "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"

    info "Updating Python dependencies..."
    pip install --upgrade -r backend/requirements.txt

    info "Dependencies updated successfully"
else
    info "No dependency changes detected - skipping pip install"
fi

# Check if firmware changed
FIRMWARE_CHANGED=false
if git diff HEAD@{1} HEAD --name-only | grep -q "firmware/"; then
    FIRMWARE_CHANGED=true
    warn "Firmware has changed!"
    warn "You need to manually upload new firmware to Arduino controllers"
    warn "Run: sudo systemctl stop $SERVICE_NAME"
    warn "Then upload firmware as described in INSTRUCTIONS.md"
    warn "Then run: sudo systemctl start $SERVICE_NAME"
    echo
fi

# Restart service
info "Restarting $SERVICE_NAME..."
sudo systemctl restart "$SERVICE_NAME"

# Wait a moment for service to start
sleep 2

# Check service status
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    info "Service restarted successfully!"

    # Show recent logs
    info "Recent logs:"
    echo "─────────────────────────────────────────────────────────"
    sudo journalctl -u "$SERVICE_NAME" -n 10 --no-pager
    echo "─────────────────────────────────────────────────────────"

    echo
    info "Deployment completed successfully!"
    info "To follow logs in real-time, run:"
    echo "  sudo journalctl -u $SERVICE_NAME -f"
else
    error "Service failed to start!"
    error "Check logs with: sudo journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# Reminder for firmware update if needed
if [ "$FIRMWARE_CHANGED" = true ]; then
    echo
    warn "⚠️  REMINDER: Firmware has changed - don't forget to upload it!"
fi
