#!/bin/bash

# Radxa ROCK 5 ITX Fan Control Installer

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

echo "--- Installing Rock 5 ITX Fan Control ---"

# 1. Copy Script
echo "Installing script to /usr/local/bin/..."
cp rock5-fan-control.py /usr/local/bin/
chmod +x /usr/local/bin/rock5-fan-control.py

# 2. Copy Service
echo "Installing systemd service..."
cp rock5-fan.service /etc/systemd/system/
systemctl daemon-reload

# 3. Enable and Start
echo "Enabling and starting service..."
systemctl enable rock5-fan.service
systemctl restart rock5-fan.service

echo "----------------------------------------"
echo "Installation Complete!"
echo "Check status with: sudo systemctl status rock5-fan.service"
echo "Watch logs with: sudo journalctl -u rock5-fan.service -f"
echo "----------------------------------------"
