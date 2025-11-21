# Setup Progress - Session Notes

## Current Status (2025-11-20)

### ✅ Completed Steps

1. **UART Enabled**
   - Modified `/boot/firmware/config.txt` to enable UART0
   - Added `enable_uart=1` and `init_uart_baud=460800`
   - Device `/dev/ttyAMA0` is now available
   - Rebooted successfully

2. **Dependencies Installed**
   - Installed project with `pip install -e .` in venv
   - Installed GPIO support:
     - System packages: `swig`, `liblgpio-dev`
     - Python package: `rpi-lgpio`
   - All dependencies working correctly

3. **GPIO Control Working**
   - DE (Driver Enable) on GPIO18 - initialized successfully
   - nRE (Receiver Enable) on GPIO23 - initialized successfully
   - RS-485 control pins functioning

4. **Hardware Connected**
   - Pico W is powered
   - Jumper wires installed per WIRING_SETUP.md
   - Reaction wheel emulator app running on Pico
   - RS-485 transceiver connected

### 🔧 Issue Found & Fixed

**Problem:** Serial console (`agetty`) was holding `/dev/ttyAMA0` open, preventing our application from using it.

**Solution Applied:**
```bash
# Stopped and disabled serial console service
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service

# Removed console from kernel command line
sudo sed -i 's/console=serial0,115200 //' /boot/firmware/cmdline.txt
```

### ⏭️ Next Steps After Reboot

1. **Verify serial port is free:**
   ```bash
   sudo lsof /dev/ttyAMA0  # Should show nothing
   ```

2. **Test PING command:**
   ```bash
   source venv/bin/activate
   python3 << 'EOF'
   from nss_host.commands import Session
   import logging

   logging.basicConfig(level=logging.INFO)

   print("Opening RS-485 connection...")
   with Session.open(
       port='/dev/ttyAMA0',
       baud=460800,
       rs485={'de': 18, 'nre': 23},
       timeout_ms=100,
       retries=3
   ) as session:
       print("Sending PING...")
       session.ping()
       print("\n✅ SUCCESS! Pico emulator is responding!")
       print(f"Stats: {session.stats}")
   EOF
   ```

3. **If PING succeeds, launch TUI:**
   ```bash
   nss-tui
   ```

4. **If PING fails, check Pico serial table:**
   - Look for bytes received count
   - Should see SLIP-encoded PING frame

---

## Configuration Summary

- **Serial Port:** `/dev/ttyAMA0`
- **Baud Rate:** 460800
- **GPIO Pins:**
  - GPIO14 (Pin 8): UART TX
  - GPIO15 (Pin 10): UART RX
  - GPIO18 (Pin 12): RS-485 DE (Driver Enable)
  - GPIO23 (Pin 16): RS-485 nRE (Receiver Enable)
  - GPIO24 (Pin 18): PORT_SELECT (optional)
  - GPIO25 (Pin 22): FAULT_IN (optional)
  - GPIO12 (Pin 32): RESET_OUT (optional)

## Test Results

- ✅ UART device exists
- ✅ GPIO library installed and working
- ✅ RS-485 control pins initialized
- ⏳ **Awaiting reboot to test serial communication**

---

**Last Updated:** Before reboot to apply cmdline.txt changes
**Reboot Required:** YES - to disable serial console on ttyAMA0
