# HOST_SPEC.md — Raspberry Pi 5 Host Driver for NRWA‑T6 Reaction Wheel Emulator

## 1. Purpose

Build a Python host stack that runs on Raspberry Pi 5 to control and test the NRWA‑T6‑compatible reaction wheel emulator over RS‑485 with SLIP + NSP framing. The host must:
- Speak NSP exactly (control byte, ACK/NACK, CRC‑CCITT, SLIP).
- Issue all ICD telecommands and decode telemetry blocks bit‑for‑bit.
- Provide an operator TUI (terminal) that mirrors the emulator’s tables and fields, plus a command palette.
- Offer a regression test suite, fuzzers, and scripted runs to validate integration with real hardware or the emulator.
- Support line redundancy A/B, multi‑drop safe TX (tri‑state when idle), and robust error handling.
- Run on Raspberry Pi OS 64‑bit, Python 3.11+.

## 2. Hardware Topology & Wiring (Raspberry Pi 5)

**Interface choice:** Use the Pi 5’s `ttyAMA0` UART for RS‑485 via an external half/full‑duplex transceiver; we operate full‑duplex with separate TXD/RXD pairs to match emulator wiring, and a DE/RE direction pin for completeness. USB‑serial is also supported for bring‑up.

- UART: `/dev/ttyAMA0` (Pi 5 default high‑performance UART)
- Baud: 460800 8‑N‑1 (tolerate 455.6–465.7 kbps)
- RS‑485 Transceiver: e.g., MAX3485‑class or SN65HVD. Use full‑duplex variant when available.
- GPIO assignment (BCM numbering):
  - TXD: GPIO14 (UART TX)
  - RXD: GPIO15 (UART RX)
  - DE (Driver Enable): GPIO18 (active‑high)
  - nRE (Receiver Enable): GPIO23 (active‑low, tie to DE in software for full‑duplex always‑enabled RX)
  - PORT_SELECT (A/B): GPIO24 (0=A, 1=B) to drive external relays/mux if you wire redundancy
  - FAULT_IN: GPIO25 (from emulator FAULT line, optional)
  - RESET_OUT: GPIO12 (to emulator RESET, open‑drain preferred via transistor if needed)

> If you prefer USB‑to‑RS485, set `serial_port=/dev/ttyUSB0` in config and ignore GPIO except FAULT/RESET.

**Termination & bias:** Fit 120 Ω across each differential pair at only the ends of the bus. Provide bias resistors on RX lines if running multi‑drop. The emulator tri‑states TX when idle; the host TX should remain driven only when sending frames.

## 3. Software Stack & Layout

```
host-driver/
├─ pyproject.toml
├─ README.md
├─ HOST_SPEC.md
├─ nss_host/
│  ├─ __init__.py
│  ├─ config.py            # load/save .toml, serial params, pins
│  ├─ serial_link.py       # pyserial + RS-485 DE/nRE control via gpiozero/RPi.GPIO
│  ├─ slip.py              # SLIP codec
│  ├─ crc_ccitt.py         # CCITT (0xFFFF init, LSB first on wire)
│  ├─ nsp.py               # NSP pack/unpack, control byte, ACK/NACK, router
│  ├─ icd_fields.py        # field defs, fixed-point enc/dec (UQ formats)
│  ├─ telemetry.py         # decode STANDARD/TEMP/VOLT/CURR/DIAG blocks
│  ├─ commands.py          # high-level API (ping, peek, poke, app_cmd, clear_fault, etc.)
│  ├─ tables.py            # host-side mirror of emulator tables (IDs/names/types)
│  ├─ tui/
│  │  ├─ __init__.py
│  │  ├─ tui.py            # textual/urwid-based menu UI with command palette
│  │  └─ palette.py
│  ├─ scenarios/
│  │  ├─ runner.py         # drive emulator scenarios from host (optional)
│  │  └─ examples/*.json
│  └─ tests/
│     ├─ test_crc.py
│     ├─ test_slip.py
│     ├─ test_nsp.py
│     ├─ test_icd_fields.py
│     ├─ test_loopback.py  # hardware-in-the-loop smoke tests
│     └─ data/frames/*.bin
├─ tools/
│  ├─ nsp_send.py          # raw NSP frame sender
│  ├─ dump_telemetry.py
│  ├─ bench_rtt.py         # latency/throughput
│  ├─ fuzz_cmds.py
│  └─ record.py            # pcap-like capture to .nsplog
└─ scripts/
   ├─ setup_udev.sh
   └─ enable_uart.sh
```

## 4. Dependencies

- Python 3.11+
- `pyserial`, `gpiozero` (or `RPi.GPIO`), `textual` (or `urwid`) for TUI, `pydantic` for config and schema, `pytest` for tests, `rich` for logging.
- Optional: `numpy` for vectorized telemetry transforms; `matplotlib` for offline plots.

## 5. Protocol Details (Host View)

- **SLIP**: END=0xC0, ESC=0xDB with ESC_END=0xDC, ESC_ESC=0xDD. Encode payload after CRC; outermost bytes are framed with END boundaries.
- **CRC**: CCITT 0xFFFF init; append LSB then MSB.
- **NSP Control Byte**: bits `[POLL|B|A|cmd4..0]`. Host sets `POLL=1` for request/response; sets `A=0` (ACK bit is set by the device in reply). `B` ununsed by host.
- **Command Set**: 0x00 PING, 0x02 PEEK, 0x03 POKE, 0x07 APP‑TM, 0x08 APP‑CMD, 0x09 CLEAR‑FAULT, 0x0A CONFIG‑PROT, 0x0B TRIP‑LCL.
- **Timing**: default reply timeout 10 ms; retry 2x on CRC or SLIP errors; backoff with jitter for bus sharing.

## 6. High-Level Python API (commands.py)

```python
from nss_host.session import Session

with Session.open('/dev/ttyAMA0', baud=460800, rs485={'de':18, 'nre':23}) as s:
    s.ping()
    regs = s.peek(addr=0x1000, length=16)
    s.poke(addr=0x1020, data=b'\x01\x00\x00\x00')
    tm = s.app_telemetry(block='STANDARD')
    s.app_command(mode='SPEED', setpoint_rpm=1500)
    s.clear_fault(mask=0xFFFFFFFF)
    s.config_protection(overspeed_limit_rpm=5000)
```

`Session` handles SLIP, CRC, NSP, retries, port A/B selection, and logs every frame with timestamps.

## 7. TUI Design (textual/urwid)

The TUI mirrors the emulator’s **Tables** and also includes a command palette. Keyboard shortcuts aim for speed on a bench.

### 7.1 Main Views

- **Dash**: live gauges for speed, torque, current, power, mode, flags.
- **Tables**: browsable list of tables as a “database.” Selecting opens a field view.
- **Link**: serial/RS‑485 health, SLIP/CRC counts, port A/B, baud.
- **NSP**: recent telecommands and replies, ACK/NACK counters.
- **Scenarios**: list/load/status for emulator JSON scenarios.
- **Logs**: rolling log with filter by module/level.

### 7.2 Command Palette

Commands are identical to the emulator (plus host‑only items) and can be typed or selected. Abbreviations in parentheses.

- `help`, `?`
- `connect <port>` / `disconnect`
- `tables` (list tables from host mirror or live query)
- `describe <table>`
- `get <table>.<field>`
- `set <table>.<field> <value>`
- `peek <addr> <len>` / `poke <addr> <hex>`
- `defaults list` / `defaults restore [scope]` (host will map to device PEEK/POKE/CONFIG under the hood)
- `scenario list|load|status`
- `nsp stats`, `serial stats`
- `fault clear [all|mask]`
- `save profile <name>` / `load profile <name>` (host‑side presets for lab runs)
- `quit` (exit TUI)
- `record start/stop <file.nsplog>`

### 7.3 Non‑Default Tracking

The host maintains a **shadow map** of compiled defaults loaded from a versioned YAML/TOML bundle matching the emulator build, and a live map queried at connect time. It can display diffs and drive `defaults restore` at table or field granularity.

- On connect: pull STANDARD telemetry, PEEK default range, and identify device firmware hash.
- Render “*” next to non‑default fields; show a “Restore” action in the field view.

## 8. Config Files

`~/.config/nss_host/config.toml`

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
# path to versioned defaults used for diffing
path = "~/nss_bundles/nrwa_t6_defaults_v1.toml"
```

## 9. Testing & Validation

### 9.1 Unit Tests (pytest)
- `test_crc.py`: golden vectors for CCITT.
- `test_slip.py`: END/ESC edges, zero‑length, concatenation.
- `test_nsp.py`: control byte, ACK/NACK, command codec.
- `test_icd_fields.py`: UQ enc/dec and bounds.
- `test_commands.py`: Session with loopback transport.

### 9.2 Hardware‑in‑the‑Loop (HIL)
- **Loopback smoke**: Ping, standard telemetry, set mode/speed, verify ramps and limits.
- **Timing**: RTT distribution, reply ≤ 5 ms 99p.
- **Reliability**: CRC/drop/NACK injections via emulator scenarios; assert retries and error classes.
- **Protections**: Overspeed/overcurrent trips; verify live vs latched flags and CLEAR‑FAULT.

### 9.3 Fuzzing
- Random APP‑CMD sequences within safe bounds; measure device fault rate and host exception safety.
- SLIP/CRC mutators to ensure decoder robustness.

### 9.4 Regression
- Record .nsplog sessions and replay; compare decoded fields to baselines in CI.

## 10. Performance Targets

- 1 kHz STANDARD telemetry polling sustained on Pi 5.
- Frame logger ≥ 5 MB/s to disk when `frame_dump=true`.
- CPU < 10% average during 100 Hz polling.

## 11. Error Handling & Telemetry

Separate counters for transport vs protocol vs device faults. Expose in TUI Link/NSP views:
`frames_tx`, `frames_rx`, `crc_err`, `slip_err`, `timeouts`, `nack`, per‑command counts.

## 12. Security & Safety

No root required; add user to `dialout`. GPIO via udev permissions. Confirmation prompts before writes to critical regions; `--force` to override.

## 13. Deliverables

- Pip‑installable package and wheel
- CLI tools and TUI
- Unit/HIL tests with fixtures
- Wiring guide
- Example profiles and scenarios
- Developer docs

## 14. Open Items

- Confirm FAULT/RESET electrical levels.
- Confirm whether multi‑drop is required in your bench topology.
- Verify any additional inter‑frame delay constraints from the flight ICD.


## 15. Bench Topology and Harness

Describe the complete bench wiring between Raspberry Pi, RS 485 transceivers, and the Pico based emulator.

- Show a simple block diagram in the document intro that captures:
  - Raspberry Pi 5
  - One or two RS 485 transceivers
  - Emulator board with Pico
  - Optional relays or mux for redundant ports A and B

- Define a harness mapping table:

### Raspberry Pi Pico W Emulator Pin Configuration

**RS-485 Communication (UART1):**
| Pin  | Function    | Direction | Description                        |
|------|-------------|-----------|-------------------------------------|
| GP4  | UART1_TX    | Output    | RS-485 transmit data                |
| GP5  | UART1_RX    | Input     | RS-485 receive data                 |
| GP6  | RS485_DE    | Output    | Driver Enable (high = TX mode)      |
| GP7  | RS485_RE    | Output    | Receiver Enable (low = RX mode)     |

Configuration: 460.8 kbps, 8-N-1, no flow control

**Device Address Selection:**
| Pin  | Function | Direction              | Description           |
|------|----------|------------------------|-----------------------|
| GP10 | ADDR0    | Input (pull-up/down)   | Address bit 0 (LSB)   |
| GP11 | ADDR1    | Input (pull-up/down)   | Address bit 1         |
| GP12 | ADDR2    | Input (pull-up/down)   | Address bit 2 (MSB)   |

Address Range: 0-7 (3-bit binary selection)

**Status and Control:**
| Pin  | Function | Direction         | Description                           |
|------|----------|-------------------|---------------------------------------|
| GP13 | FAULT    | Output (open-drain)| Fault indicator (active low)          |
| GP14 | RESET    | Input             | Hardware reset (active low)           |
| GP25 | LED      | Output            | Onboard LED (heartbeat @ 1 Hz)        |

**Optional External LEDs (disabled by default):**
| Pin  | Function       | Description                          |
|------|----------------|--------------------------------------|
| GP15 | RS485_ACTIVE   | RS-485 activity indicator (optional) |
| GP16 | FAULT_LED      | External fault LED (optional)        |
| GP17 | MODE_LED       | Control mode indicator (optional)    |

**Summary:** 8 active pins (TX, RX, DE, RE, ADDR0-2, FAULT, RESET) + 1 heartbeat LED

### Complete Harness Mapping Table

| Signal Name        | Raspberry Pi 5 GPIO   | RS-485 Transceiver | Pico W Emulator Pin | Notes                        |
|--------------------|-----------------------|--------------------|---------------------|------------------------------|
| UART TX (host)     | GPIO14 (ttyAMA0 TX)   | DI                 | GP5 (UART1_RX)      | Pi transmits → Pico receives |
| UART RX (host)     | GPIO15 (ttyAMA0 RX)   | RO                 | GP4 (UART1_TX)      | Pico transmits → Pi receives |
| RS-485 DE (host)   | GPIO18                | DE                 | GP6 (RS485_DE)      | Driver Enable (active-high)  |
| RS-485 nRE (host)  | GPIO23                | RE̅                 | GP7 (RS485_RE)      | Receiver Enable (active-low) |
| PORT SELECT A/B    | GPIO24                | Relay/mux control  | (Port switching)    | Optional redundancy          |
| FAULT IN           | GPIO25                | Direct/opto        | GP13 (FAULT)        | Emulator → Host (active-low) |
| RESET OUT          | GPIO12                | Direct/open-drain  | GP14 (RESET)        | Host → Emulator (active-low) |

- Specify power rails and grounding:
  - RS 485 transceivers are powered from the Pi 3v3 or 5v rail as required by part choice.
  - Grounds for Pi, transceivers, and emulator are tied together at a single bench reference.
  - Termination resistors of 120 ohm are at the physical ends of each RS 485 pair.
  - Bias resistors are placed on the receive lines if multi drop is used.

State that the harness drawing and mapping table are part of the release and must be kept in sync with the host configuration defaults.


## 16. NSP and ICD Mapping

Define a clear mapping between NSP commands, telemetry blocks, and the emulator ICD from the host point of view.

- List all supported commands with code, request payload, expected reply payload, and error conditions.
- For each telemetry block type, provide:
  - Block identifier
  - Length in bytes
  - Nominal production rate
  - Summary of fields and their fixed point formats and range
- Require that `icd_fields.py` encodes and decodes all fields exactly as specified, including saturation, clipping, and any special NaN or invalid encodings.
- Provide at least a small set of golden example payloads and decoded values in a test data directory so unit tests can validate full encode and decode behaviour.


## 17. Addressing, Redundancy, and Multi Drop

Clarify how the host interacts with address pins and redundant links on the emulator.

- Document how ADDR0, ADDR1, and ADDR2 are strapped on the emulator board for the default device address.
- State whether the bench normally uses only port A or both ports A and B, and how PORT_SELECT on the Raspberry Pi controls any relay or mux.
- Define how many emulator nodes may share the same RS 485 bus during multi drop operation, and how addresses are configured.
- Specify how the host discovers or selects which node it is talking to when more than one emulator is present.
- If multi drop is supported, define safe bus access behaviour:
  - Poll intervals and backoff rules
  - Maximum outstanding request count per node
  - How the host reacts to address conflicts or duplicate replies.


## 18. TUI Views and Emulator Table Catalog

Align the host TUI with the emulator table and status catalog so the same mental model is used at the bench.

- Introduce a mapping between emulator tables and host TUI views, for example:
  - Dynamics and setpoints tables feed the Dash view and selected Tables view.
  - Serial and link status tables feed the Link and NSP views.
  - Protection and fault tables feed the Dash and Logs views.
- Require that every field in the emulator table catalog can be viewed in the host Tables browser, with clear read or write indication and units where appropriate.
- State that the table schema used by `icd_fields.py` also drives TUI field labels, units, and limits, so that adding or changing a field only requires updating a shared schema file rather than hard coded UI logic.
- For writable fields, the TUI must present safe input widgets, input validation, and confirmation prompts for fields that affect protections or safety.


## 19. Scenario Orchestration and Error Injection

Describe how the host discovers, runs, and monitors emulator scenarios and deliberate error injections.

- Define how scenarios are stored and identified on the emulator, for example by name and version string.
- Provide host commands and TUI actions for:
  - Listing available scenarios
  - Loading or arming a scenario
  - Starting, pausing, resuming, and stopping a scenario
  - Querying scenario state and elapsed time
- Require that every recorded frame in `.nsplog` can be tagged with the active scenario name and its time offset so that playback can correlate commands, telemetry, and injected events.
- State that host fuzzing tools must respect emulator safety limits and avoid conflicts with active scenarios unless explicitly in destructive test mode.


## 20. Behaviour Tests Based on Physics Model

Extend host tests beyond protocol and transport to verify that emulator dynamics and protections match the specification.

- Define a set of behaviour test cases that the host test suite must implement, for example:
  - Speed step response tests at several setpoints in speed mode with pass and fail tolerance on overshoot and settling time.
  - Current mode tests that verify the torque versus current relationship within expected bounds.
  - Power limit tests that confirm clipping behaviour when the commanded profile exceeds configured power limits.
  - Protection tests that confirm overspeed and overcurrent trips and validate that CLEAR_FAULT is required before re enabling drive.
- Each test case description should include:
  - Initial conditions and configuration
  - Sequence of host commands
  - Expected telemetry signatures and limits
  - Clear numeric acceptance criteria


## 21. Timing Contract Between Host and Emulator

Make timing expectations explicit so both host and emulator can be tuned and stress tested consistently.

- Restate emulator timing promises and tolerances as seen from the host, for example:
  - Typical reply latency for normal commands
  - Maximum tolerated latency in stress or scenario modes
  - Minimum supported interval between successive commands
- Define host polling modes, such as:
  - Normal bench mode with 100 Hz STANDARD telemetry polling
  - High rate mode with up to 1 kHz polling for short bench stress tests
- Specify how the host differentiates between timeouts caused by link issues and deliberate timing effects from scenarios, and how it reports each kind of event in the TUI and logs.
- Set clear limits for backoff, retry counts, and when the host declares a link down condition.


## 22. Host Operating Modes

Describe how the host is used in different integration contexts so tools and logs are configured correctly.

Typical modes include:

- Direct control mode  
  Host behaves like the eventual OBC and sends all commands, reads all telemetry, and runs full regression tests against the emulator.

- Hardware in the loop mode  
  Real flight or proto flight hardware is connected to the emulator while the host primarily sniffs, logs, and performs limited non intrusive checks or scripted sequences.

- Regression replay mode  
  Host replays previously captured `.nsplog` sessions to validate new emulator firmware builds and compares decoded fields against stored baselines.

For each mode, describe:
- Which tools and scripts are in use
- What logging detail is expected
- Which safety checks are active or disabled


## 23. Tooling Alignment With Emulator Repository

Avoid drift between tools that ship with the emulator firmware repository and the Raspberry Pi host package.

- Designate the Raspberry Pi host package as the primary reference host implementation.
- Where possible, re implement simple helper scripts that live in the emulator repository as thin wrappers around the host Python API to keep all protocol logic in one place.
- Require that any scenario generator or error injection tools produce JSON or other data that the host validates against a shared schema before sending to the emulator.
- Document how the two repositories are versioned together so that a host release can be matched with a compatible emulator firmware tag.


## 24. Spec Driven Development Constraints

Capture expectations that are important when using this specification with AI assisted coding tools or automated generation.

- Coding guidelines
  - Require use of type hints for public functions and classes.
  - Prefer data classes or pydantic models for configuration and for ICD field definitions where validation and bounds checking are important.
  - Keep protocol logic pure and side effect free where possible to simplify unit testing.

- Testing guidelines
  - Every encoder and decoder must have golden vector tests derived from the NSP and ICD mapping section.
  - Hardware in the loop tests must be clearly marked and skipped when hardware is not detected, so that continuous integration can still run unit tests on a normal host.
  - Behaviour tests must emit numeric metrics to logs so that regressions can be detected automatically.

- Documentation guidelines
  - Each module should contain a brief docstring that states its role in terms of the numbered sections of HOST_SPEC and, where relevant, the emulator SPEC.
  - The top level README must explain how to run basic tests, perform a first connection to the emulator, and where to find harness and wiring documentation.

These additions complete the Raspberry Pi host specification so it can act as the single source of truth for host tooling, test automation, and AI based code generation.

