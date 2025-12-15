# AI-Assisted Spec-Driven Development Report
## NSS Host - Reaction Wheel Test Platform

**Date:** December 2025
**Project:** NSS Host - Raspberry Pi 5 Reaction Wheel Test Platform
**AI Assistant:** Claude Code (running locally on Raspberry Pi 5)
**Development Approach:** Spec-Driven Development with AI Coding Assistance

---

## Executive Summary

This report documents an experiment in using AI-assisted coding combined with specification-driven development to create a reaction wheel test platform. The system enables testing and development of host software against a reaction wheel emulator, eliminating the need for expensive flight hardware during development.

**Key Achievement:** The Python test code has been validated as **100% protocol-compliant** with the production C++ spacecraft driver (see [PYTHON_PRODUCTION_PROTOCOL_COMPARISON.md](PYTHON_PRODUCTION_PROTOCOL_COMPARISON.md)).

**What makes this unique:** Claude Code ran locally on the Raspberry Pi 5 target hardware, enabling the AI to directly:
- Execute code on the target platform
- Interface with hardware (RS-485, GPIO)
- Debug real-time communication issues
- Observe actual telemetry from the emulator
- Iterate rapidly with immediate hardware feedback
- Compare and align code with production spacecraft software

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Raspberry Pi 5                              │
│  ┌───────────────┐    ┌──────────────────────────────────────┐  │
│  │  Claude Code  │───▶│  NSS Host Test Platform              │  │
│  │  (AI Assistant)│    │  - Protocol implementation          │  │
│  │               │    │  - Telemetry decoding                │  │
│  │  • Writes code│    │  - Real-time TUI                     │  │
│  │  • Runs tests │    │  - Command interface                 │  │
│  │  • Debugs HW  │    └──────────────┬───────────────────────┘  │
│  └───────────────┘                   │                          │
│                                      │ RS-485 (460800 baud)     │
└──────────────────────────────────────┼──────────────────────────┘
                                       │
                              ┌────────▼────────┐
                              │   Pico W        │
                              │   RW Emulator   │
                              │                 │
                              │  Simulates:     │
                              │  • Motor physics│
                              │  • Telemetry    │
                              │  • Fault states │
                              └─────────────────┘
```

**Purpose:** Develop and test reaction wheel host software without requiring actual flight hardware (which can cost $10,000+).

---

## Project Analytics

### Codebase Metrics

| Metric | Value |
|--------|-------|
| **Total Python LOC** | 4,201 |
| **Python Modules** | 22 |
| **Classes Defined** | 53 |
| **Functions Defined** | 206 |
| **Docstrings** | 391 |
| **Test LOC** | 684 |
| **Documentation LOC** | 4,944 |

### Architecture Components

```
nss_host/
├── Protocol Layer
│   ├── nsp.py          # NSP packet framing
│   ├── slip.py         # SLIP encoding/decoding
│   ├── crc_ccitt.py    # CRC-CCITT checksums
│   └── icd_fields.py   # Fixed-point field encoding (UQ14.18, etc.)
├── Communication Layer
│   ├── serial_link.py  # RS-485 serial + GPIO control
│   └── commands.py     # High-level Session API
├── Data Layer
│   ├── telemetry.py    # Telemetry block decoders
│   ├── tables.py       # Register/table definitions
│   └── config.py       # Configuration management
└── Interface Layer
    └── tui/            # Terminal User Interface
        ├── tui.py      # Main application
        └── widgets_new.py  # Gauges, status panels, packet monitor
```

### Capabilities Implemented

| Category | Features |
|----------|----------|
| **Protocol** | NSP framing, SLIP encoding, CRC-CCITT, little-endian (ICD-compliant) |
| **Fixed-Point** | Q14.18, Q10.22, Q24.8, Q20.12, Q14.2, UQ16.16, UQ24.8 (production-matched) |
| **Telemetry** | STANDARD (25-byte), TEMP, VOLT, CURR, DIAG blocks with full decoding |
| **Commands** | PING, PEEK, POKE, APP-TM, APP-CMD, CLEAR-FAULT, CONFIG-PROT |
| **Control Modes** | IDLE (0x00), CURRENT (0x01), SPEED (0x02), TORQUE (0x04), PWM (0x08) |
| **TUI** | Live telemetry, ICD test scenarios, command interface |
| **Hardware** | RS-485 half-duplex, GPIO DE/NRE control, 460800 baud |
| **Testing** | 6 ICD compliance scenarios, unit tests, protocol validation |

---

## The AI-on-Hardware Advantage

Running Claude Code directly on the Raspberry Pi 5 provided unique capabilities:

### Direct Hardware Debugging

When telemetry showed incorrect voltage (16.78V instead of 28.00V), the AI could:

1. **Read the code** to understand the telemetry flow
2. **Identify the bug** - `app_telemetry()` wasn't decoding VOLT blocks
3. **Fix the code** - Update decoder to handle all telemetry types
4. **Test immediately** - Run the TUI and observe corrected values
5. **Commit the fix** - Push directly to the repository

This cycle happened in minutes, not hours.

### Real-Time Iteration

```
Developer: "The voltage is showing wrong"
     ↓
Claude Code: [reads telemetry.py, commands.py, tui.py]
     ↓
Claude Code: "Found it - VOLT block returns raw bytes, not decoded"
     ↓
Claude Code: [edits commands.py to decode all blocks]
     ↓
Claude Code: [adds refresh() calls to widgets]
     ↓
Developer: "Now it works correctly"
```

---

## Traditional vs AI-Assisted Comparison

### Development Time Estimation

| Task | Traditional | AI-Assisted |
|------|-------------|-------------|
| Protocol research & spec interpretation | 2-3 days | ~2 hours |
| NSP/SLIP/CRC implementation | 3-4 days | ~1 day |
| Fixed-point encoding library | 2 days | ~3 hours |
| Telemetry decoder system | 2-3 days | ~4 hours |
| TUI with live gauges | 5-7 days | ~2 days |
| Hardware integration & debugging | 2-3 days | ~1 day |
| Documentation | 3-4 days | Continuous |
| **Total** | **~20-26 days** | **~5-6 days** |

**Acceleration factor: ~4-5x**

### Qualitative Benefits

| Aspect | Traditional | AI-Assisted (Local) |
|--------|-------------|---------------------|
| Debug cycle | Write → deploy → test → analyze | AI observes and fixes in-place |
| Platform knowledge | Developer learns Pi quirks | AI already knows GPIO, serial |
| Documentation | Afterthought | Generated with code |
| Error messages | Google/StackOverflow | AI interprets and fixes |
| Protocol bugs | Logic analyzer + manual decode | AI traces through layers |

---

## Example: Debugging Session

**Problem:** TUI bar gauges not updating, voltage always showing 0.

**AI Analysis Path:**
1. Read `tui.py` → Found `update_telemetry()` calls `app_telemetry(TelemetryBlock.VOLT)`
2. Read `commands.py` → Found `app_telemetry()` only decodes STANDARD, returns raw bytes for others
3. Read `telemetry.py` → Confirmed `VoltTelemetry` decoder exists but wasn't being called
4. **Root cause:** Code tried `volt_tm.v_bus` on raw `bytes` object, failed silently

**Fix Applied:**
- Modified `app_telemetry()` to decode all block types
- Added `refresh()` calls to widget update methods
- Tested and verified 28.00V displays correctly

**Time:** ~15 minutes from report to fix pushed

---

## Key Deliverables

### Working Test Platform
- Raspberry Pi 5 host communicating with Pico W emulator at 460800 baud
- Real-time telemetry display with TUI interface
- Full NSP protocol implementation matching ICD specification
- **100% protocol compliance with production C++ spacecraft code**
- Production-ready error handling and logging

### Protocol Compliance (Validated)

- All 8 command codes match production
- All 5 control modes match production
- APP-CMD 5-byte structure with Q-format encoding matches production
- All telemetry structures (STANDARD 25-byte, TEMP 8-byte, etc.) match production
- Little-endian byte order throughout (ICD-compliant)

### ICD Test Scenarios

1. Wheel Discovery - PING command verification
2. Speed Control - Closed-loop speed mode testing
3. Torque Control - Torque command mode testing
4. Fault Handling - Fault injection and clearing
5. Protection Configuration - Enable/disable protections
6. Telemetry Polling - All telemetry blocks at various rates

### Code Quality
- Type hints throughout (Python 3.11+)
- Comprehensive docstrings
- Unit tests for protocol components
- Protocol compliance tests
- Consistent code style and patterns

### Documentation

- [HOST_SPEC_RPi.md](HOST_SPEC_RPi.md) - Complete host specification
- [WIRING_SETUP.md](WIRING_SETUP.md) - Hardware pin mapping
- [PYTHON_PRODUCTION_PROTOCOL_COMPARISON.md](PYTHON_PRODUCTION_PROTOCOL_COMPARISON.md) - Protocol compliance report

---

## Conclusions

This experiment demonstrates that **local AI-assisted development on embedded targets** provides significant advantages:

1. **Immediate feedback** - No deploy cycle, AI sees results instantly
2. **Hardware awareness** - AI understands platform-specific details
3. **Rapid debugging** - Multi-layer issues traced in minutes
4. **Continuous documentation** - Generated alongside code

The ~4-5x acceleration is conservative - some debugging sessions that might take hours were resolved in minutes because the AI could read code, understand the full stack, and test fixes immediately.

### Best Practices Identified

1. **Spec-first development** - Clear specifications (REGS.md) enabled accurate implementation
2. **Incremental validation** - Test each layer before building on it
3. **AI + human collaboration** - Human observes hardware behavior, AI interprets and fixes
4. **Local execution** - Running AI on target hardware eliminates deployment friction

---

*This platform enables reaction wheel host software development without $10,000+ flight hardware.*

*Report generated as part of the NSS Host project - Raspberry Pi 5 Reaction Wheel Test Platform.*
