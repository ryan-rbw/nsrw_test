# Pi 5 ↔ Pico W Wiring Setup

## Complete Pin Mapping

### UART Communication (via RS-485 Transceiver)
```
Raspberry Pi 5          RS-485          Pico W Emulator
══════════════          ══════          ═══════════════
GPIO14 (Pin 8)  ──TX──> DI
                        │
                        A/B ────────> GP5 (UART1_RX)
                        │
GPIO15 (Pin 10) <─RX──  RO
                        │
                        A/B <────────  GP4 (UART1_TX)
```

### RS-485 Control (Host Side)
```
Pi GPIO18 (Pin 12) ────> DE  (Driver Enable, active-HIGH)
Pi GPIO23 (Pin 16) ────> RE̅  (Receiver Enable, active-LOW)
```

### Additional Control Signals
```
Pi GPIO24 (Pin 18) ────> PORT_SELECT (A/B redundancy)
Pi GPIO25 (Pin 22) <──── FAULT_IN     (from Pico GP13, active-LOW)
Pi GPIO12 (Pin 32) ────> RESET_OUT    (to Pico GP14, active-LOW)
```

### Power
```
Pi 3.3V (Pin 1)    ────> Pico VSYS or 3V3_EN
Pi GND (Pin 6,9)   ────> Pico GND
```

---

## Current Status

### Raspberry Pi 5
- **UART Device**: `/dev/ttyAMA0` (not yet available - UART disabled)
- **Current Device**: `/dev/ttyAMA10` (console only)
- **User Groups**: ✅ `dialout`, `gpio` (permissions OK)
- **GPIO Library**: ✅ gpiozero 2.0.1 installed

### Pico W Emulator
- **Status**: Not detected via USB
- **Connection**: Via RS-485 (jumper wires ready)

---

## Setup Steps

### 1. Enable UART on Pi 5

The UART needs to be enabled in the boot configuration:

```bash
# Option A: Run the provided script
sudo ./scripts/enable_uart.sh
sudo reboot

# Option B: Manual configuration
sudo nano /boot/firmware/config.txt
```

Add these lines to `/boot/firmware/config.txt`:
```ini
# Enable UART0 (ttyAMA0) for RS-485
dtoverlay=uart0
enable_uart=1

# Disable console on UART (if present)
# Remove console=serial0,115200 from cmdline.txt if needed
```

Then reboot:
```bash
sudo reboot
```

### 2. Verify UART After Reboot

```bash
# Check that ttyAMA0 now exists
ls -la /dev/ttyAMA0

# Verify you have permission
groups | grep dialout
```

### 3. Test GPIO Control

Before connecting the Pico, test the GPIO pins:

```bash
source venv/bin/activate

python3 << 'EOF'
from gpiozero import OutputDevice
import time

print("Testing GPIO control pins...")

# Test DE (Driver Enable)
de = OutputDevice(18, initial_value=False)
print("GPIO18 (DE) initialized")

# Test nRE (Receiver Enable)
nre = OutputDevice(23, initial_value=False)  # Active-low, so LOW = enabled
print("GPIO23 (nRE) initialized")

# Pulse DE to verify
print("Pulsing DE (GPIO18) HIGH for 1 second...")
de.on()
time.sleep(1)
de.off()
print("DE pulse complete")

# Test RESET_OUT
reset = OutputDevice(12, initial_value=True)  # Active-low, so HIGH = not reset
print("GPIO12 (RESET_OUT) initialized")

print("\n✅ GPIO control test passed!")
print("You can measure these pins with a multimeter while running this test")

de.close()
nre.close()
reset.close()
EOF
```

### 4. Connect Pico W

Once UART is enabled and GPIO test passes:

1. **Power off the Pi**: `sudo poweroff`
2. **Connect all jumper wires** per the table above
3. **Double-check connections** (wrong wiring can damage hardware!)
4. **Power on the Pi**
5. **Power on the Pico** (or connect USB if it draws power from Pi)

### 5. Test Communication

```bash
source venv/bin/activate

# Quick ping test
python3 << 'EOF'
from nss_host.commands import Session
import logging

logging.basicConfig(level=logging.INFO)

print("Opening RS-485 connection...")
try:
    with Session.open(
        port='/dev/ttyAMA0',
        baud=460800,
        rs485={'de': 18, 'nre': 23},
        timeout_ms=100,  # Longer timeout for first connection
        retries=3
    ) as session:
        print("Sending PING...")
        session.ping()
        print("\n✅ SUCCESS! Pico emulator is responding!")
        print(f"Stats: {session.stats}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nTroubleshooting:")
    print("- Check all wire connections")
    print("- Verify Pico is powered and running emulator firmware")
    print("- Check baud rate matches (460800)")
    print("- Verify RS-485 transceiver has power")
EOF
```

### 6. Launch TUI

If ping succeeds:

```bash
nss-tui
```

---

## Hardware Checklist

Before powering on:

- [ ] **UART enabled** in `/boot/firmware/config.txt`
- [ ] **GPIO18** (DE) → RS-485 DE
- [ ] **GPIO23** (nRE) → RS-485 RE̅
- [ ] **GPIO14** (TX) → RS-485 DI
- [ ] **GPIO15** (RX) → RS-485 RO
- [ ] **RS-485 A/B** → Pico UART1 (GP4/GP5)
- [ ] **3.3V & GND** connected properly
- [ ] **Optional**: GPIO12 (RESET), GPIO24 (PORT_SELECT), GPIO25 (FAULT_IN)
- [ ] **120Ω termination** on RS-485 lines (if using long cables)

---

## Expected Behavior

### Successful Connection
```
Opening RS-485 connection...
Sending PING...

✅ SUCCESS! Pico emulator is responding!
Stats: {'frames_tx': 1, 'frames_rx': 1, 'crc_errors': 0, ...}
```

### Common Issues

#### "FileNotFoundError: /dev/ttyAMA0"
- UART not enabled → Run `enable_uart.sh` and reboot

#### "Permission denied: /dev/ttyAMA0"
- Not in dialout group → Run `sudo usermod -a -G dialout $USER` and re-login

#### "NspTimeoutError"
- Pico not powered or not running emulator firmware
- Wrong baud rate (should be 460800)
- RS-485 wiring incorrect (A/B swapped?)
- RS-485 transceiver not powered

#### "NspCrcError"
- Electrical noise on RS-485 lines
- Missing termination resistors
- Baud rate mismatch

#### "GPIO errors"
- Wrong BCM pin numbers
- Already in use by another process
- Not enough permissions (need to be in `gpio` group)

---

## Next Steps After Successful Connection

1. **Get telemetry**: `session.app_telemetry('STANDARD')`
2. **Control the wheel**: `session.app_command(mode='SPEED', setpoint_rpm=1000)`
3. **Browse tables**: Use TUI to inspect emulator state
4. **Run benchmarks**: `nss-bench` to measure latency
5. **Run HIL tests**: `pytest -m hil` for hardware validation

---

## Reference

- **Spec**: `HOST_SPEC_RPi.md` Section 2
- **Code**: `nss_host/serial_link.py` (GPIO control)
- **Commands**: `nss_host/commands.py` (Session class)
- **Config**: `config.example.toml` (serial settings)
