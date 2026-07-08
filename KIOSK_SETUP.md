# Coinnect Kiosk Mode Setup Guide

This guide describes how to configure the Coinnect touchscreen interface on a Raspberry Pi running the latest **Debian Trixie OS (Wayland)** to boot directly into a secure, full-screen kiosk mode.

Trixie OS utilizes Wayland by default. This guide uses **Cage**, a lightweight Wayland kiosk compositor, to launch a single, full-screen instance of Chromium. This configuration bypasses the standard desktop environment entirely, saving system resources and preventing user tampering.

---

## Table of Contents

1. [Frontend Hosting Setup](#1-frontend-hosting-setup)
2. [Kiosk Compositor Installation](#2-kiosk-compositor-installation)
3. [Kiosk Service Configuration (systemd)](#3-kiosk-service-configuration-systemd)
4. [Pre-Production Testing & Verification](#4-pre-production-testing--verification)
5. [Touchscreen & Display Tuning (Wayland/Trixie)](#5-touchscreen--display-tuning-waylandtrixie)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Frontend Hosting Setup

To display the React + Vite frontend UI, you must compile it and run a lightweight static web server on the Pi.

### 1.1 Install Node.js and NPM
If Node.js and NPM are not already installed on the Pi, install them using the NodeSource repository:
```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg

# Add Trixie/Debian 13 NodeSource repo (using current LTS node v20 or v22)
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list

sudo apt update
sudo apt install nodejs -y
```

### 1.2 Build the React App
Navigate to the frontend directory, install dependencies, and build:
```bash
cd /home/pi/coinnect/frontend
npm install
npm run build
```

### 1.3 Configure Frontend Systemd Service
To ensure the UI is always served on boot, configure a lightweight Node.js server (`serve`) as a systemd service.

1. **Install `serve` globally:**
   ```bash
   sudo npm install -g serve
   ```

2. **Create the frontend service file:**
   ```bash
   sudo nano /etc/systemd/system/coinnect-frontend.service
   ```

3. **Paste the following configuration:**
   ```ini
   [Unit]
   Description=Coinnect Kiosk Frontend Server
   After=network.target

   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi/coinnect/frontend
   ExecStart=/usr/bin/serve -s dist -l 3000
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

4. **Enable and start the service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable coinnect-frontend.service
   sudo systemctl start coinnect-frontend.service
   ```

---

## 2. Kiosk Compositor Installation

Install **Cage** (the Wayland kiosk compositor) and **Chromium Browser**:
```bash
sudo apt update
sudo apt install -y cage chromium-browser
```

---

## 3. Kiosk Service Configuration (systemd)

To launch the display compositor at startup, create a dedicated systemd service.

1. **Create the service file:**
   ```bash
   sudo nano /etc/systemd/system/coinnect-ui.service
   ```

2. **Paste the following configuration:**
   ```ini
   [Unit]
   Description=Coinnect Touchscreen Kiosk UI (Wayland Cage)
   After=network.target systemd-user-sessions.service coinnect-frontend.service coinnect.service
   Wants=coinnect-frontend.service coinnect.service

   [Service]
   User=pi
   Type=simple
   Environment=XDG_RUNTIME_DIR=/run/user/1000
   ExecStart=/usr/bin/cage chromium-browser --kiosk --noerrdialogs --disable-infobars --disable-pinch --overscroll-history-navigation=0 http://localhost:3000
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=graphical.target
   ```

---

## 4. Pre-Production Testing & Verification

Before configuring the services to boot automatically, you should test the configurations manually to verify screen dimensions, touchscreen responsiveness, and overall layout.

### 4.1 Running a Manual Test (Desktop Active)
If the Pi is currently running a desktop environment:
1. Open a terminal on the Pi (directly or via SSH).
2. Run Chromium in kiosk mode directly inside the user session:
   ```bash
   chromium-browser --kiosk --noerrdialogs --disable-pinch --overscroll-history-navigation=0 http://localhost:3000
   ```
3. **How to Exit:** Press **`Alt + F4`** or **`Ctrl + W`** on a connected keyboard to close the browser and return to the desktop.

### 4.2 Running a Manual Kiosk Compositor Test
To test the actual Wayland `Cage` behavior without systemd:
1. Stop any display managers if running (e.g., `sudo systemctl stop lightdm` or `gdm`).
2. Run Cage directly from the command terminal:
   ```bash
   cage chromium-browser --kiosk --noerrdialogs --disable-pinch --overscroll-history-navigation=0 http://localhost:3000
   ```
3. **How to Exit:** Press **`Ctrl + C`** in your SSH terminal or keyboard window to stop the `cage` compositor process and close the screen.

### 4.3 Testing and Disabling Systemd Services
If you want to test the entire systemd startup flow before sealing the kiosk:

1. **Start both services manually:**
   ```bash
   sudo systemctl start coinnect-frontend.service
   sudo systemctl start coinnect-ui.service
   ```
2. **Verify touchscreen operations:** Tap the screen, initiate transactions, and verify that the interface fills the monitor properly without browser address bars.
3. **Disable/Stop after testing:** Once satisfied, disable and stop the services so that they do not boot into kiosk mode during configuration or debugging:
   ```bash
   sudo systemctl stop coinnect-ui.service
   sudo systemctl disable coinnect-ui.service
   ```

---

## 5. Touchscreen & Display Tuning (Wayland/Trixie)

Wayland handles display rotation and input calibration differently than traditional X11 window systems.

### 5.1 Display Rotation (wlr-randr)
To rotate your display in a Wayland environment, you must query your output device and set its transformation.

1. **Identify the screen connector name:**
   ```bash
   # Run this inside the Wayland session or look at log output
   wlr-randr
   ```
   *Usually outputs a name like `HDMI-A-1` or `DSI-1`.*

2. **Test rotation (e.g., rotating 90 degrees clockwise):**
   ```bash
   wlr-randr --output HDMI-A-1 --transform 90
   ```
   *Available rotations: `normal`, `90`, `180`, `270`, `flipped`, `flipped-90`, `flipped-180`, `flipped-270`.*

3. **Make rotation persistent in Cage:**
   Add rotation parameters directly into the environment variable configuration of your `/etc/systemd/system/coinnect-ui.service`:
   ```ini
   [Service]
   ...
   Environment=WLR_DRM_NO_MODIFIERS=1
   # Sets rotation for DRM outputs:
   Environment=WLR_X11_OUTPUTS=HDMI-A-1
   # (For Cage/wlroots, rotation configuration is set via the environment or launcher script)
   ```

### 5.2 Touchscreen Input Calibration (libinput)
If you rotate the display, the touch coordinates must also be rotated to match the visual display. Under Trixie's `libinput`, this is controlled via a **Calibration Matrix** in a `udev` rule.

1. **Find your Touchscreen Device:**
   ```bash
   cat /proc/bus/input/devices | grep -i touch
   ```
   *Identify the exact name string, e.g., "Raspberry Pi Touchscreen" or "USB Touchscreen".*

2. **Create a Udev Rules file for input:**
   ```bash
   sudo nano /etc/udev/rules.d/99-touchscreen.rules
   ```

3. **Add the mapping matrix:**
   Define the `LIBINPUT_CALIBRATION_MATRIX` according to your screen rotation:
   * **90° Rotation (Clockwise):**
     ```udev
     ACTION=="add|change", KERNELS=="input*", ENV{ID_INPUT_TOUCHSCREEN}=="1", ENV{LIBINPUT_CALIBRATION_MATRIX}="0 1 0 -1 0 1 0 0 1"
     ```
   * **180° Rotation (Upside Down):**
     ```udev
     ACTION=="add|change", KERNELS=="input*", ENV{ID_INPUT_TOUCHSCREEN}=="1", ENV{LIBINPUT_CALIBRATION_MATRIX}="-1 0 1 0 -1 1 0 0 1"
     ```
   * **270° Rotation (Counter-Clockwise):**
     ```udev
     ACTION=="add|change", KERNELS=="input*", ENV{ID_INPUT_TOUCHSCREEN}=="1", ENV{LIBINPUT_CALIBRATION_MATRIX}="0 -1 1 1 0 0 0 0 1"
     ```

4. **Reload Udev Rules:**
   ```bash
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```

### 5.3 Disabling Screen Blanking (Sleep Mode)
By default, Wayland displays turn off after 10 minutes of inactivity. To prevent this, ensure that no power management daemon (such as `swayidle`) is loaded.
Additionally, you can run the following to prevent general system power blanking in Trixie:
```bash
sudo raspi-config
```
Go to **Display Options** -> **Screen Blanking** -> Choose **No** (Disabled).

---

## 6. Troubleshooting

* **Black Screen / No Display:**
  Ensure the `XDG_RUNTIME_DIR` environment variable is defined in the systemd service. Verify the output of `systemctl status coinnect-ui.service`.
* **Touch Coordinates Inverted:**
  Double-check the calibration matrix udev rules. The values represent the standard affine transformation matrix. Ensure the touchscreen name or generic check (`ENV{ID_INPUT_TOUCHSCREEN}=="1"`) is triggering correctly.
* **White Cursor Visible:**
  Add the `--hide-cursor` flag to the Cage command line, or install `unclutter-xfixes` if running under Xwayland compatibilities.
