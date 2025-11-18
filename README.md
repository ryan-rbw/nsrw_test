# NSS Host - NRWA-T6 Reaction Wheel Host Driver

Python host driver for Raspberry Pi 5 to control and test the NRWA-T6-compatible reaction wheel emulator over RS-485 with SLIP + NSP framing.

## Features

- **NSP Protocol**: Full implementation of NSP (control byte, ACK/NACK, CRC-CCITT, SLIP framing)
- **ICD Commands**: All telecommands (PING, PEEK, POKE, APP-CMD, CLEAR-FAULT, CONFIG-PROT, TRIP-LCL)
- **Telemetry**: Decode all telemetry blocks (STANDARD, TEMP, VOLT, CURR, DIAG)
- **Terminal UI**: Interactive TUI with live dashboards, table browser, and command palette
- **Testing**: Unit tests, hardware-in-the-loop tests, fuzzers, and regression test suite
- **Redundancy**: Line redundancy (A/B), multi-drop support with tri-state TX
- **Raspberry Pi 5**: Optimized for Pi 5 with ttyAMA0 UART and GPIO control

## Hardware Requirements

- Raspberry Pi 5 running Raspberry Pi OS 64-bit
- RS-485 transceiver (MAX3485 or SN65HVD compatible)
- NRWA-T6 reaction wheel emulator (Pico-based)
- Proper wiring harness (see [Wiring Guide](docs/wiring.md))

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/nsrw_test.git
cd nsrw_test

# Install in development mode
pip install -e ".[dev]"

# Or install from PyPI (when available)
pip install nss-host
```

### First Connection

1. **Configure UART** (Raspberry Pi 5):
   ```bash
   sudo ./scripts/enable_uart.sh
   ```

2. **Set up udev rules** (optional, for non-root access):
   ```bash
   sudo ./scripts/setup_udev.sh
   ```

3. **Connect to emulator**:
   ```bash
   # Launch TUI
   nss-tui

   # Or use Python API
   python3 -c "
   from nss_host.session import Session
   with Session.open('/dev/ttyAMA0', baud=460800) as s:
       s.ping()
       print('Connected!')
   "
   ```

### Running Tests

```bash
# Run unit tests
pytest -m unit

# Run hardware-in-the-loop tests (requires connected emulator)
pytest -m hil

# Run all tests with coverage
pytest --cov=nss_host --cov-report=html
```

## Configuration

Configuration file: `~/.config/nss_host/config.toml`

```toml
[serial]
port = "/dev/ttyAMA0"
baud = 460800
timeout_ms = 10
retries = 2
port_select_gpio = 24
de_gpio = 18
nre_gpio = 23

[logging]
level = "INFO"
frame_dump = true
log_dir = "~/nss_logs"

[defaults_bundle]
path = "~/nss_bundles/nrwa_t6_defaults_v1.toml"
```

## Python API

```python
from nss_host.session import Session

# Open session
with Session.open('/dev/ttyAMA0', baud=460800, rs485={'de':18, 'nre':23}) as s:
    # Ping device
    s.ping()

    # Read registers
    regs = s.peek(addr=0x1000, length=16)

    # Write registers
    s.poke(addr=0x1020, data=b'\x01\x00\x00\x00')

    # Get telemetry
    tm = s.app_telemetry(block='STANDARD')
    print(f"Speed: {tm.speed_rpm} RPM")
    print(f"Current: {tm.current_a} A")

    # Send command
    s.app_command(mode='SPEED', setpoint_rpm=1500)

    # Clear faults
    s.clear_fault(mask=0xFFFFFFFF)

    # Configure protection
    s.config_protection(overspeed_limit_rpm=5000)
```

## Command-Line Tools

- `nss-tui`: Terminal UI for interactive control and monitoring
- `nss-send`: Send raw NSP frames
- `nss-dump`: Dump telemetry to console or file
- `nss-bench`: Benchmark round-trip time and throughput
- `nss-fuzz`: Fuzzing tool for robustness testing
- `nss-record`: Record/replay NSP traffic (pcap-like)

## Documentation

- [HOST_SPEC_RPi.md](HOST_SPEC_RPi.md) - Complete host specification
- [Wiring Guide](docs/wiring.md) - Hardware setup and harness
- [NSP Protocol](docs/nsp.md) - Protocol details
- [ICD Mapping](docs/icd.md) - Command and telemetry reference
- [TUI Guide](docs/tui.md) - Terminal UI user guide
- [Testing Guide](docs/testing.md) - Test suite and HIL setup

## Performance Targets

- 1 kHz STANDARD telemetry polling sustained
- Frame logger ≥ 5 MB/s to disk
- CPU < 10% average during 100 Hz polling
- Reply latency ≤ 5 ms (99th percentile)

## Project Structure

```
nsrw_test/
├── pyproject.toml
├── README.md
├── LICENSE
├── HOST_SPEC_RPi.md
├── nss_host/
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   ├── serial_link.py      # RS-485 serial interface
│   ├── slip.py             # SLIP encoder/decoder
│   ├── crc_ccitt.py        # CRC-CCITT implementation
│   ├── nsp.py              # NSP protocol handler
│   ├── icd_fields.py       # Field definitions and codecs
│   ├── telemetry.py        # Telemetry block decoders
│   ├── commands.py         # High-level command API
│   ├── tables.py           # Table definitions
│   ├── session.py          # Session management
│   ├── tui/                # Terminal UI
│   ├── scenarios/          # Scenario orchestration
│   └── tests/              # Test suite
├── tools/                  # Command-line tools
└── scripts/                # Setup scripts
```

## Contributing

Contributions welcome! Please ensure:
- All code passes `black` formatting and `ruff` linting
- Type hints on all public functions
- Unit tests for new features
- Update documentation as needed

## License

MIT License - See [LICENSE](LICENSE) file for details

## Specification Compliance

This implementation follows [HOST_SPEC_RPi.md](HOST_SPEC_RPi.md) sections 1-24, ensuring:
- Exact NSP protocol compliance
- Full ICD command/telemetry support
- Type-safe field encoding/decoding
- Comprehensive test coverage
- Hardware redundancy support
- Timing contract adherence

## Support

For issues, questions, or feature requests, please open an issue on GitHub.
