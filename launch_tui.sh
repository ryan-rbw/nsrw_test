#!/bin/bash
# Quick launcher for NSS Host TUI

echo "╔════════════════════════════════════════════════════════╗"
echo "║   NSS Host TUI - NRWA-T6 Reaction Wheel Controller    ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

echo "Launching TUI..."
echo ""
echo "Controls:"
echo "  c - Connect to emulator"
echo "  p - Ping"
echo "  t - Telemetry"
echo "  q - Quit"
echo ""
echo "Commands: speed <rpm>, ping, telemetry, connect, disconnect"
echo ""
echo "Press Enter to continue..."
read

nss-tui
