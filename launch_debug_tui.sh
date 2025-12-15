#!/bin/bash
# Quick launcher for NSS Host Debug TUI

echo "╔════════════════════════════════════════════════════════╗"
echo "║   NSS Debug TUI - Manual Command Testing               ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

echo "Launching Debug TUI..."
echo ""
echo "Keyboard Shortcuts:"
echo "  c - Connect to emulator"
echo "  d - Disconnect"
echo "  p - Send PING"
echo "  t - Send STANDARD telemetry"
echo "  Space - Command selector"
echo "  x - Clear log"
echo "  q - Quit"
echo ""
echo "Commands (type in input field):"
echo "  ping, tm0-tm4, idle, speed <rpm>, peek <addr>, clear"
echo ""
echo "Press Enter to continue..."
read

python -m nss_host.tui.debug_tui
