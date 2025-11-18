#!/bin/bash
# Setup udev rules for NSS Host serial port access
# Implements HOST_SPEC_RPi.md section 12: Security & Safety

set -e

echo "Setting up udev rules for NSS Host..."

# Create udev rule for serial port access
UDEV_RULE="/etc/udev/rules.d/99-nss-host.rules"

sudo tee "$UDEV_RULE" > /dev/null <<'EOF'
# NSS Host - Serial port access without root
# Add user to dialout group for access

# Raspberry Pi UART
KERNEL=="ttyAMA[0-9]*", GROUP="dialout", MODE="0660"

# USB-to-serial adapters
KERNEL=="ttyUSB[0-9]*", GROUP="dialout", MODE="0660"

# GPIO access for RS-485 control
SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"
EOF

echo "Created udev rule: $UDEV_RULE"

# Add user to dialout and gpio groups
echo ""
echo "Adding user '$USER' to dialout and gpio groups..."
sudo usermod -a -G dialout "$USER"
sudo usermod -a -G gpio "$USER"

# Reload udev rules
echo ""
echo "Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo ""
echo "Setup complete!"
echo ""
echo "IMPORTANT: You must log out and log back in for group changes to take effect"
echo ""
echo "Verify group membership with:"
echo "  groups"
echo ""
echo "Check serial port permissions with:"
echo "  ls -l /dev/ttyAMA0"
