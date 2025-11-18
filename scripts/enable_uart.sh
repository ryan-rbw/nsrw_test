#!/bin/bash
# Enable UART on Raspberry Pi 5 for RS-485 communication
# Implements HOST_SPEC_RPi.md section 2: Hardware Topology & Wiring

set -e

echo "Configuring Raspberry Pi 5 UART for RS-485..."

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Error: This script must run on a Raspberry Pi"
    exit 1
fi

# Backup config.txt
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.backup.$(date +%Y%m%d_%H%M%S)

# Enable UART (disable Bluetooth on primary UART)
echo ""
echo "Adding UART configuration to /boot/firmware/config.txt..."

sudo tee -a /boot/firmware/config.txt > /dev/null <<EOF

# NSS Host RS-485 Configuration
# Enable primary UART (ttyAMA0) for RS-485
dtoverlay=disable-bt
enable_uart=1

# Set UART baud rate to 460800
init_uart_baud=460800
EOF

# Disable Bluetooth service (uses primary UART by default)
echo ""
echo "Disabling Bluetooth service..."
sudo systemctl disable hciuart || true

echo ""
echo "UART configuration complete!"
echo ""
echo "IMPORTANT: You must reboot for changes to take effect"
echo "  sudo reboot"
echo ""
echo "After reboot, verify with:"
echo "  ls -l /dev/ttyAMA0"
echo "  sudo cat /proc/tty/driver/serial"
