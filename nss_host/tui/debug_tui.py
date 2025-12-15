"""
Debug TUI for systematic command/response testing.

A simplified TUI focused on manual command execution with full packet
decoding and error tracking. No auto-polling - you control when commands
are sent.
"""

import logging
from datetime import datetime
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from nss_host.nsp import (
    NspCommand,
    NspFrame,
    ControlMode,
    POLL_BIT,
    ACK_BIT,
    CMD_MASK,
)

logger = logging.getLogger(__name__)

# Command names for display
CMD_NAMES = {
    0x00: "PING",
    0x02: "PEEK",
    0x03: "POKE",
    0x07: "APP-TM",
    0x08: "APP-CMD",
    0x09: "CLEAR-FAULT",
    0x0A: "CONFIG-PROT",
    0x0B: "TRIP-LCL",
}

MODE_NAMES = {
    0x00: "IDLE",
    0x01: "CURRENT",
    0x02: "SPEED",
    0x04: "TORQUE",
    0x08: "PWM",
}

TM_BLOCK_NAMES = {
    0x00: "STANDARD",
    0x01: "TEMP",
    0x02: "VOLT",
    0x03: "CURR",
    0x04: "DIAG",
}


def decode_packet_details(data: bytes, direction: str, tx_context: dict = None) -> dict[str, Any]:
    """
    Decode packet into human-readable fields.

    Args:
        data: Raw packet bytes
        direction: "TX" or "RX"
        tx_context: Context from TX packet for RX decoding (e.g., tm_block_id)

    Returns dict with:
        - raw_hex: Full hex string
        - dest: Destination address
        - src: Source address
        - control: Control byte breakdown
        - cmd_name: Command name
        - is_request: True if POLL bit set
        - is_ack: True if ACK bit set
        - payload_hex: Payload as hex
        - payload_decoded: Decoded payload fields
        - errors: List of any decode errors
    """
    if tx_context is None:
        tx_context = {}

    result = {
        "raw_hex": data.hex().upper(),
        "raw_bytes": data,
        "errors": [],
    }

    if len(data) < 3:
        result["errors"].append(f"Frame too short: {len(data)} bytes (need >= 3)")
        return result

    result["dest"] = data[0]
    result["src"] = data[1]
    result["control"] = data[2]
    result["payload"] = data[3:]
    result["payload_hex"] = data[3:].hex().upper() if len(data) > 3 else ""

    # Decode control byte
    ctrl = data[2]
    result["is_request"] = bool(ctrl & POLL_BIT)
    result["is_ack"] = bool(ctrl & ACK_BIT)
    result["cmd_code"] = ctrl & CMD_MASK
    result["cmd_name"] = CMD_NAMES.get(result["cmd_code"], f"UNKNOWN(0x{result['cmd_code']:02X})")

    # Control byte breakdown (escape brackets for Rich markup)
    poll_str = "POLL=1 (Request)" if result["is_request"] else "POLL=0 (Reply)"
    ack_str = ""
    if not result["is_request"]:
        ack_str = " ACK=1 (Success)" if result["is_ack"] else " ACK=0 (NACK!)"
    result["control_str"] = f"0x{ctrl:02X} \\[{poll_str}{ack_str}]"

    # Decode payload based on command
    result["payload_decoded"] = decode_payload(
        result["cmd_code"],
        result["payload"],
        result["is_request"],
        tx_context
    )

    return result


def decode_payload(cmd: int, payload: bytes, is_request: bool, tx_context: dict = None) -> str:
    """Decode payload fields based on command type."""
    if tx_context is None:
        tx_context = {}

    if not payload:
        return "(empty)"

    try:
        if cmd == NspCommand.PING:
            if not is_request and len(payload) >= 5:
                dev_type = payload[0]
                serial = payload[1]
                ver_maj = payload[2]
                ver_min = payload[3]
                ver_patch = payload[4]
                return f"DevType=0x{dev_type:02X} Serial={serial} Ver={ver_maj}.{ver_min}.{ver_patch}"
            return payload.hex().upper()

        elif cmd == NspCommand.PEEK:
            if is_request and len(payload) >= 1:
                addr = payload[0]
                return f"Addr=0x{addr:02X}"
            elif not is_request and len(payload) >= 4:
                val = int.from_bytes(payload[:4], "little")
                return f"Value=0x{val:08X} ({val})"
            return payload.hex().upper()

        elif cmd == NspCommand.POKE:
            if is_request and len(payload) >= 5:
                addr = payload[0]
                val = int.from_bytes(payload[1:5], "little")
                return f"Addr=0x{addr:02X} Value=0x{val:08X}"
            return payload.hex().upper()

        elif cmd == NspCommand.APP_TM:
            if is_request and len(payload) >= 1:
                block_id = payload[0]
                block_name = TM_BLOCK_NAMES.get(block_id, f"0x{block_id:02X}")
                return f"Block={block_name}"
            elif not is_request:
                # Use block_id from TX context if available
                block_id = tx_context.get("tm_block_id", 0)
                return decode_telemetry_payload(payload, block_id)
            return payload.hex().upper()

        elif cmd == NspCommand.APP_CMD:
            if is_request and len(payload) >= 5:
                mode = payload[0]
                mode_name = MODE_NAMES.get(mode, f"0x{mode:02X}")
                setpoint_raw = int.from_bytes(payload[1:5], "little", signed=True)
                # Decode setpoint based on mode
                if mode == ControlMode.SPEED or mode == ControlMode.CURRENT:
                    # Q14.18
                    setpoint = setpoint_raw / (1 << 18)
                    unit = "RPM" if mode == ControlMode.SPEED else "mA"
                    return f"Mode={mode_name} Setpoint={setpoint:.2f} {unit} (raw=0x{setpoint_raw & 0xFFFFFFFF:08X})"
                elif mode == ControlMode.TORQUE:
                    # Q10.22
                    setpoint = setpoint_raw / (1 << 22)
                    return f"Mode={mode_name} Setpoint={setpoint:.4f} mN-m (raw=0x{setpoint_raw & 0xFFFFFFFF:08X})"
                else:
                    return f"Mode={mode_name} Setpoint=0x{setpoint_raw & 0xFFFFFFFF:08X}"
            return payload.hex().upper()

        elif cmd == NspCommand.CLEAR_FAULT:
            if is_request and len(payload) >= 4:
                mask = int.from_bytes(payload[:4], "little")
                return f"Mask=0x{mask:08X}"
            return payload.hex().upper()

        elif cmd == NspCommand.CONFIG_PROT:
            if is_request and len(payload) >= 4:
                bits = int.from_bytes(payload[:4], "little")
                return f"ProtBits=0x{bits:08X}"
            return payload.hex().upper()

        else:
            return payload.hex().upper()

    except Exception as e:
        return f"DECODE ERROR: {e} | Raw: {payload.hex().upper()}"


def decode_telemetry_payload(payload: bytes, block_id: int = 0) -> str:
    """
    Decode telemetry payload based on block type.

    Block sizes per ICD:
        STANDARD (0x00): 25 bytes
        TEMP (0x01): 8 bytes
        VOLT (0x02): 24 bytes
        CURR (0x03): 24 bytes
        DIAG (0x04): 20 bytes
    """
    BLOCK_SIZES = {0: 25, 1: 8, 2: 24, 3: 24, 4: 20}
    expected_size = BLOCK_SIZES.get(block_id, 0)
    block_name = TM_BLOCK_NAMES.get(block_id, f"0x{block_id:02X}")

    # Show raw data with size info
    size_info = f"[{block_name} {len(payload)}B"
    if expected_size:
        size_info += f" (expect {expected_size}B)"
    size_info += "]"

    try:
        if block_id == 0:  # STANDARD
            if len(payload) < 25:
                return f"{size_info} SHORT | {payload.hex().upper()}"
            # STANDARD telemetry per ICD (25 bytes)
            status = int.from_bytes(payload[0:4], "little")
            fault = int.from_bytes(payload[4:8], "little")
            control_mode = payload[8]
            setpoint = int.from_bytes(payload[9:13], "little", signed=True)
            duty_cycle = int.from_bytes(payload[13:15], "little", signed=True)
            current_target = int.from_bytes(payload[15:17], "little") / 4.0  # Q14.2
            current = int.from_bytes(payload[17:21], "little") / 4096.0  # Q20.12
            speed = int.from_bytes(payload[21:25], "little") / 256.0  # Q24.8

            mode_name = MODE_NAMES.get(control_mode, f"0x{control_mode:02X}")
            return f"{size_info} Mode={mode_name} Speed={speed:.1f}RPM Current={current:.1f}mA Fault=0x{fault:08X}"

        elif block_id == 1:  # TEMP (8 bytes: 4 x uint16)
            if len(payload) < 8:
                return f"{size_info} SHORT | {payload.hex().upper()}"
            dcdc = int.from_bytes(payload[0:2], "little")
            enclosure = int.from_bytes(payload[2:4], "little")
            driver = int.from_bytes(payload[4:6], "little")
            motor = int.from_bytes(payload[6:8], "little")
            return f"{size_info} DCDC={dcdc} Encl={enclosure} Drv={driver} Motor={motor} (raw ADC)"

        elif block_id == 2:  # VOLT (24 bytes: 6 x uint32 UQ16.16)
            if len(payload) < 24:
                return f"{size_info} SHORT | {payload.hex().upper()}"
            v1v5 = int.from_bytes(payload[0:4], "little") / 65536.0
            v3v3 = int.from_bytes(payload[4:8], "little") / 65536.0
            v5v = int.from_bytes(payload[8:12], "little") / 65536.0
            v12v = int.from_bytes(payload[12:16], "little") / 65536.0
            v30v = int.from_bytes(payload[16:20], "little") / 65536.0
            v2v5 = int.from_bytes(payload[20:24], "little") / 65536.0
            return f"{size_info} 1V5={v1v5:.2f}V 3V3={v3v3:.2f}V 5V={v5v:.2f}V 12V={v12v:.2f}V 30V={v30v:.2f}V 2V5={v2v5:.2f}V"

        elif block_id == 3:  # CURR (24 bytes: 6 x uint32 UQ16.16)
            if len(payload) < 24:
                return f"{size_info} SHORT | {payload.hex().upper()}"
            i1v5 = int.from_bytes(payload[0:4], "little") / 65536.0
            i3v3 = int.from_bytes(payload[4:8], "little") / 65536.0
            i5va = int.from_bytes(payload[8:12], "little") / 65536.0
            i5vd = int.from_bytes(payload[12:16], "little") / 65536.0
            i12v = int.from_bytes(payload[16:20], "little") / 65536.0
            i30v = int.from_bytes(payload[20:24], "little") / 65536.0
            return f"{size_info} 1V5={i1v5:.1f}mA 3V3={i3v3:.1f}mA 5VA={i5va:.1f}mA 5VD={i5vd:.1f}mA 12V={i12v:.1f}mA 30V={i30v:.2f}A"

        elif block_id == 4:  # DIAG (20 bytes)
            if len(payload) < 20:
                return f"{size_info} SHORT | {payload.hex().upper()}"
            uptime_raw = int.from_bytes(payload[0:4], "little")
            uptime_s = uptime_raw / 4.0  # Q30.2
            rev_count = int.from_bytes(payload[4:8], "little")
            hall_bad = int.from_bytes(payload[8:12], "little")
            drive_fault = int.from_bytes(payload[12:16], "little")
            over_temp = int.from_bytes(payload[16:20], "little")
            return f"{size_info} Uptime={uptime_s:.1f}s Revs={rev_count} HallBad={hall_bad} DrvFault={drive_fault} OverTemp={over_temp}"

        else:
            return f"{size_info} UNKNOWN BLOCK | {payload.hex().upper()}"

    except Exception as e:
        return f"{size_info} DECODE ERROR: {e} | {payload.hex().upper()}"


class TransactionLog(Static):
    """Widget showing transaction history with decode."""

    DEFAULT_CSS = """
    TransactionLog {
        height: 100%;
        border: solid $primary;
        padding: 0 1;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.transactions: list[dict] = []
        self.max_transactions = 50

    def add_transaction(
        self,
        tx_data: bytes | None,
        rx_data: bytes | None,
        error: str | None = None,
        duration_ms: float = 0,
    ) -> None:
        """Add a transaction (request + response) to the log."""
        tx_details = decode_packet_details(tx_data, "TX") if tx_data else None

        # Extract context from TX for proper RX decoding
        tx_context = {}
        if tx_details and tx_details.get("cmd_code") == NspCommand.APP_TM:
            # Get block_id from TX payload
            payload = tx_details.get("payload", b"")
            if payload:
                tx_context["tm_block_id"] = payload[0]

        rx_details = decode_packet_details(rx_data, "RX", tx_context) if rx_data else None

        txn = {
            "time": datetime.now(),
            "tx": tx_details,
            "rx": rx_details,
            "error": error,
            "duration_ms": duration_ms,
        }
        self.transactions.append(txn)

        # Trim old transactions
        if len(self.transactions) > self.max_transactions:
            self.transactions = self.transactions[-self.max_transactions:]

        self._update_display()

    def clear_log(self) -> None:
        """Clear all transactions."""
        self.transactions = []
        self._update_display()

    def _update_display(self) -> None:
        """Render transactions."""
        if not self.transactions:
            self.update("[dim]No transactions yet. Send a command to begin.[/dim]")
            return

        lines = ["[bold]TRANSACTION LOG[/bold] (newest first)\n"]

        for txn in reversed(self.transactions):
            time_str = txn["time"].strftime("%H:%M:%S.%f")[:-3]

            # Transaction header
            if txn["error"]:
                lines.append(f"[red]━━━ {time_str} ERROR ━━━[/red]")
                lines.append(f"[red]  {txn['error']}[/red]")
            elif txn["rx"] and not txn["rx"].get("is_ack", True):
                lines.append(f"[yellow]━━━ {time_str} NACK ({txn['duration_ms']:.1f}ms) ━━━[/yellow]")
            else:
                lines.append(f"[green]━━━ {time_str} OK ({txn['duration_ms']:.1f}ms) ━━━[/green]")

            # TX details
            if txn["tx"]:
                tx = txn["tx"]
                lines.append(f"  [cyan]TX>[/cyan] {tx['cmd_name']} to 0x{tx.get('dest', 0):02X}")
                lines.append(f"      Raw: {tx['raw_hex']}")
                lines.append(f"      Ctrl: {tx.get('control_str', '?')}")
                if tx.get("payload_decoded"):
                    lines.append(f"      Data: {tx['payload_decoded']}")

            # RX details
            if txn["rx"]:
                rx = txn["rx"]
                ack_str = "[green]ACK[/green]" if rx.get("is_ack") else "[red]NACK[/red]"
                lines.append(f"  [magenta]RX<[/magenta] {rx['cmd_name']} {ack_str}")
                lines.append(f"      Raw: {rx['raw_hex']}")
                lines.append(f"      Ctrl: {rx.get('control_str', '?')}")
                if rx.get("payload_decoded"):
                    lines.append(f"      Data: {rx['payload_decoded']}")
                if rx.get("errors"):
                    for err in rx["errors"]:
                        lines.append(f"      [red]ERROR: {err}[/red]")

            lines.append("")

        self.update("\n".join(lines))
        self.refresh()


class ErrorPanel(Static):
    """Panel tracking errors and NACKs."""

    DEFAULT_CSS = """
    ErrorPanel {
        height: auto;
        min-height: 5;
        max-height: 12;
        border: solid red;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.errors: list[dict] = []
        self.max_errors = 20

    def add_error(self, error_type: str, message: str, details: str = "") -> None:
        """Add an error to the panel."""
        self.errors.append({
            "time": datetime.now(),
            "type": error_type,
            "message": message,
            "details": details,
        })
        if len(self.errors) > self.max_errors:
            self.errors = self.errors[-self.max_errors:]
        self._update_display()

    def clear_errors(self) -> None:
        """Clear all errors."""
        self.errors = []
        self._update_display()

    def _update_display(self) -> None:
        """Render error list."""
        if not self.errors:
            self.update("[bold]ERRORS[/bold]\n[dim]No errors[/dim]")
            return

        lines = [f"[bold red]ERRORS ({len(self.errors)})[/bold red]"]
        for err in reversed(self.errors[-5:]):  # Show last 5
            time_str = err["time"].strftime("%H:%M:%S")
            lines.append(f"  [{time_str}] [yellow]{err['type']}[/yellow]: {err['message']}")
            if err["details"]:
                lines.append(f"           {err['details']}")

        self.update("\n".join(lines))
        self.refresh()


class StatsPanel(Static):
    """Panel showing session statistics."""

    DEFAULT_CSS = """
    StatsPanel {
        height: auto;
        border: solid $accent;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connected = False
        self.stats = {
            "frames_tx": 0,
            "frames_rx": 0,
            "crc_errors": 0,
            "timeouts": 0,
            "nacks": 0,
        }

    def update_stats(self, connected: bool = None, stats: dict = None) -> None:
        if connected is not None:
            self.connected = connected
        if stats:
            self.stats.update(stats)
        self._update_display()

    def _update_display(self) -> None:
        conn_str = "[green]CONNECTED[/green]" if self.connected else "[red]DISCONNECTED[/red]"

        content = f"""[bold]STATUS[/bold]
{conn_str}

TX: {self.stats['frames_tx']:>4}  RX: {self.stats['frames_rx']:>4}
CRC Err: {self.stats['crc_errors']:>3}  Timeouts: {self.stats['timeouts']:>3}
NACKs: {self.stats['nacks']:>3}"""

        self.update(content)
        self.refresh()


class CommandSelectScreen(ModalScreen[str | None]):
    """Modal for selecting a command to send."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    DEFAULT_CSS = """
    CommandSelectScreen {
        align: center middle;
    }

    #cmd-dialog {
        width: 50;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #cmd-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #cmd-list {
        height: auto;
        max-height: 15;
    }

    #cmd-help {
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }
    """

    COMMANDS = [
        ("ping", "PING - Device identification"),
        ("tm0", "APP-TM STANDARD - Main telemetry"),
        ("tm1", "APP-TM TEMP - Temperature telemetry"),
        ("tm2", "APP-TM VOLT - Voltage telemetry"),
        ("tm3", "APP-TM CURR - Current telemetry"),
        ("tm4", "APP-TM DIAG - Diagnostic telemetry"),
        ("idle", "APP-CMD IDLE - Set idle mode"),
        ("speed", "APP-CMD SPEED - Set speed (prompts RPM)"),
        ("peek", "PEEK - Read memory (prompts addr)"),
        ("poke", "POKE - Write memory (prompts addr/val)"),
        ("clear", "CLEAR-FAULT - Clear all faults"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="cmd-dialog"):
            yield Label("Select Command", id="cmd-title")
            yield ListView(
                *[
                    ListItem(Label(f"{cmd[0]:<8} {cmd[1]}"), id=f"cmd-{cmd[0]}")
                    for cmd in self.COMMANDS
                ],
                id="cmd-list",
            )
            yield Label("[Enter] Select  [Esc] Cancel", id="cmd-help")

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.prevent_default()
            event.stop()
            self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id:
            cmd = event.item.id.replace("cmd-", "")
            self.dismiss(cmd)

    def action_cancel(self) -> None:
        self.dismiss(None)


class DebugSession:
    """
    Debug session wrapper that captures raw TX/RX for inspection.
    """

    def __init__(self):
        self.session = None
        self.last_tx: bytes | None = None
        self.last_rx: bytes | None = None
        self.last_error: str | None = None
        self.last_duration_ms: float = 0

    def connect(self, port: str = "/dev/ttyAMA0", baud: int = 460800) -> None:
        """Connect to device."""
        from nss_host.serial_link import SerialLink
        from nss_host.commands import Session

        link = SerialLink(
            port=port,
            baud=baud,
            timeout=0.1,
            de_gpio=18,
            nre_gpio=23,
        )
        self.session = Session(link, timeout_ms=500, retries=0)  # No retries for debug

    def disconnect(self) -> None:
        """Disconnect."""
        if self.session:
            self.session.close()
            self.session = None

    @property
    def is_connected(self) -> bool:
        return self.session is not None

    @property
    def stats(self) -> dict:
        if self.session:
            return self.session.stats
        return {}

    def send_command(self, cmd_type: str, **kwargs) -> bool:
        """
        Send a command and capture TX/RX.

        Returns True on success, False on error.
        """
        import time
        from nss_host import nsp, crc_ccitt, slip
        from nss_host.telemetry import TelemetryBlock

        if not self.session:
            self.last_error = "Not connected"
            return False

        self.last_tx = None
        self.last_rx = None
        self.last_error = None

        try:
            # Build request frame based on command type
            if cmd_type == "ping":
                request = nsp.make_request(nsp.NspCommand.PING)
            elif cmd_type.startswith("tm"):
                block_id = int(cmd_type[2]) if len(cmd_type) > 2 else 0
                request = nsp.make_request(nsp.NspCommand.APP_TM, bytes([block_id]))
            elif cmd_type == "idle":
                from nss_host.icd_fields import encode_q14_18
                payload = bytes([ControlMode.IDLE]) + (0).to_bytes(4, "little")
                request = nsp.make_request(nsp.NspCommand.APP_CMD, payload)
            elif cmd_type == "speed":
                from nss_host.icd_fields import encode_q14_18
                rpm = kwargs.get("rpm", 0)
                setpoint_raw = encode_q14_18(rpm)
                payload = bytes([ControlMode.SPEED]) + setpoint_raw.to_bytes(4, "little")
                request = nsp.make_request(nsp.NspCommand.APP_CMD, payload)
            elif cmd_type == "peek":
                addr = kwargs.get("addr", 0)
                request = nsp.make_request(nsp.NspCommand.PEEK, bytes([addr]))
            elif cmd_type == "poke":
                addr = kwargs.get("addr", 0)
                value = kwargs.get("value", 0)
                payload = bytes([addr]) + value.to_bytes(4, "little")
                request = nsp.make_request(nsp.NspCommand.POKE, payload)
            elif cmd_type == "clear":
                payload = (0xFFFFFFFF).to_bytes(4, "little")
                request = nsp.make_request(nsp.NspCommand.CLEAR_FAULT, payload)
            else:
                self.last_error = f"Unknown command: {cmd_type}"
                return False

            # Capture TX
            self.last_tx = request.to_bytes()

            # Send and receive
            start = time.time()

            # Flush and send
            self.session.link.flush_input()
            nsp_bytes = request.to_bytes()
            with_crc = crc_ccitt.append_crc(nsp_bytes)
            slip_encoded = slip.encode(with_crc)
            self.session.link.write(slip_encoded)
            self.session.stats["frames_tx"] += 1

            # Receive
            reply = self.session._receive_frame(0.5)  # 500ms timeout

            self.last_duration_ms = (time.time() - start) * 1000

            if reply is None:
                self.last_error = "Timeout - no response"
                self.session.stats["timeouts"] += 1
                return False

            # Capture RX
            self.last_rx = reply.to_bytes()

            # Check for NACK
            if reply.is_nack:
                self.last_error = f"NACK received"
                self.session.stats["nacks"] += 1
                return False

            return True

        except Exception as e:
            self.last_error = str(e)
            logger.exception("Command failed")
            return False


class DebugTuiApp(App):
    """Debug TUI for systematic command testing."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        height: 1fr;
        layout: horizontal;
    }

    #left-panel {
        width: 2fr;
        height: 100%;
    }

    #right-panel {
        width: 1fr;
        height: 100%;
        layout: vertical;
    }

    #command-bar {
        height: 3;
        dock: bottom;
        layout: horizontal;
        padding: 0 1;
    }

    #cmd-input {
        width: 1fr;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("c", "connect", "Connect", priority=True),
        Binding("d", "disconnect", "Disconnect", priority=True),
        Binding("space", "select_command", "Command", priority=True),
        Binding("p", "send_ping", "Ping", priority=True),
        Binding("t", "send_telemetry", "Telemetry", priority=True),
        Binding("x", "clear_log", "Clear Log", priority=True),
        Binding("question_mark", "show_help", "Help", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.debug_session = DebugSession()
        self.transaction_log: TransactionLog | None = None
        self.error_panel: ErrorPanel | None = None
        self.stats_panel: StatsPanel | None = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"):
                self.transaction_log = TransactionLog()
                yield self.transaction_log

            with Vertical(id="right-panel"):
                self.stats_panel = StatsPanel()
                yield self.stats_panel

                self.error_panel = ErrorPanel()
                yield self.error_panel

        with Horizontal(id="command-bar"):
            yield Input(placeholder="Press / or i to type | connect, ping, tm0-4, idle, speed <rpm>, peek <addr>", id="cmd-input")
            yield Button("Send", id="send-btn", variant="primary")

        yield Footer()

    def on_mount(self) -> None:
        self.title = "NSS Debug TUI"
        self.sub_title = "Manual command testing | Space=commands c=connect p=ping t=telemetry q=quit"
        self.stats_panel.update_stats(connected=False)
        self.error_panel._update_display()
        # Don't auto-focus input so shortcuts work
        self.set_focus(None)

    def on_key(self, event) -> None:
        """Handle keyboard shortcuts globally."""
        # Check if input is focused
        cmd_input = self.query_one("#cmd-input", Input)
        input_focused = cmd_input.has_focus

        # If input is focused, only intercept Escape
        if input_focused:
            if event.key == "escape":
                event.prevent_default()
                event.stop()
                self.set_focus(None)
            return

        # Global shortcuts when input not focused
        key = event.key
        if key == "q":
            event.prevent_default()
            self.exit()
        elif key == "c":
            event.prevent_default()
            self.action_connect()
        elif key == "d":
            event.prevent_default()
            self.action_disconnect()
        elif key == "p":
            event.prevent_default()
            self.action_send_ping()
        elif key == "t":
            event.prevent_default()
            self.action_send_telemetry()
        elif key == "x":
            event.prevent_default()
            self.action_clear_log()
        elif key == "space":
            event.prevent_default()
            self.action_select_command()
        elif key == "question_mark" or key == "shift+slash":
            event.prevent_default()
            self.action_show_help()
        elif key == "slash" or key == "i":
            event.prevent_default()
            cmd_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            self._send_input_command()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._send_input_command()

    def _send_input_command(self) -> None:
        """Send command from input field."""
        cmd_input = self.query_one("#cmd-input", Input)
        cmd = cmd_input.value.strip().lower()
        cmd_input.value = ""

        if not cmd:
            return

        # Parse command
        parts = cmd.split()
        cmd_type = parts[0]

        # Handle connect/disconnect specially
        if cmd_type == "connect" or cmd_type == "c":
            self.action_connect()
            return
        elif cmd_type == "disconnect" or cmd_type == "d":
            self.action_disconnect()
            return
        elif cmd_type == "help" or cmd_type == "?":
            self.action_show_help()
            return

        kwargs = {}
        if cmd_type == "speed" and len(parts) > 1:
            try:
                kwargs["rpm"] = float(parts[1])
            except ValueError:
                self.notify("Invalid RPM value", severity="error")
                return
        elif cmd_type == "peek" and len(parts) > 1:
            try:
                kwargs["addr"] = int(parts[1], 0)  # Support hex
            except ValueError:
                self.notify("Invalid address", severity="error")
                return
        elif cmd_type == "poke" and len(parts) > 2:
            try:
                kwargs["addr"] = int(parts[1], 0)
                kwargs["value"] = int(parts[2], 0)
            except ValueError:
                self.notify("Invalid address or value", severity="error")
                return

        self._execute_command(cmd_type, **kwargs)

    def _execute_command(self, cmd_type: str, **kwargs) -> None:
        """Execute a command and log results."""
        if not self.debug_session.is_connected:
            self.notify("Not connected - press 'c' to connect", severity="error")
            return

        success = self.debug_session.send_command(cmd_type, **kwargs)

        # Log transaction
        self.transaction_log.add_transaction(
            tx_data=self.debug_session.last_tx,
            rx_data=self.debug_session.last_rx,
            error=self.debug_session.last_error,
            duration_ms=self.debug_session.last_duration_ms,
        )

        # Update stats
        self.stats_panel.update_stats(stats=self.debug_session.stats)

        # Log error if any
        if not success and self.debug_session.last_error:
            error_type = "NACK" if "NACK" in self.debug_session.last_error else "ERROR"
            self.error_panel.add_error(
                error_type,
                self.debug_session.last_error,
                f"Command: {cmd_type}",
            )

        # Notify
        if success:
            self.notify(f"{cmd_type.upper()} OK", severity="information")
        else:
            self.notify(f"{cmd_type.upper()} FAILED: {self.debug_session.last_error}", severity="error")

    def action_connect(self) -> None:
        """Connect to device."""
        if self.debug_session.is_connected:
            self.notify("Already connected", severity="warning")
            return

        try:
            self.debug_session.connect()
            self.stats_panel.update_stats(connected=True)
            self.notify("Connected", severity="information")
        except Exception as e:
            self.notify(f"Connection failed: {e}", severity="error")
            self.error_panel.add_error("CONNECT", str(e))

    def action_disconnect(self) -> None:
        """Disconnect from device."""
        if not self.debug_session.is_connected:
            self.notify("Not connected", severity="warning")
            return

        self.debug_session.disconnect()
        self.stats_panel.update_stats(connected=False)
        self.notify("Disconnected", severity="information")

    def action_select_command(self) -> None:
        """Open command selector."""
        def handle_command(cmd: str | None) -> None:
            if cmd:
                if cmd == "speed":
                    # Prompt for RPM
                    self.query_one("#cmd-input", Input).value = "speed "
                    self.query_one("#cmd-input", Input).focus()
                elif cmd == "peek":
                    self.query_one("#cmd-input", Input).value = "peek 0x"
                    self.query_one("#cmd-input", Input).focus()
                elif cmd == "poke":
                    self.query_one("#cmd-input", Input).value = "poke 0x 0x"
                    self.query_one("#cmd-input", Input).focus()
                else:
                    self._execute_command(cmd)

        self.push_screen(CommandSelectScreen(), handle_command)

    def action_send_ping(self) -> None:
        """Send PING command."""
        self._execute_command("ping")

    def action_send_telemetry(self) -> None:
        """Send STANDARD telemetry request."""
        self._execute_command("tm0")

    def action_clear_log(self) -> None:
        """Clear transaction log and errors."""
        self.transaction_log.clear_log()
        self.error_panel.clear_errors()
        self.notify("Log cleared", severity="information")

    def action_show_help(self) -> None:
        """Show help."""
        help_text = """[bold]Debug TUI Keyboard Shortcuts[/bold]

c - Connect to device
d - Disconnect
Space - Open command selector
p - Send PING
t - Send STANDARD telemetry
x - Clear log and errors
q - Quit
? - This help

[bold]Commands (type in input)[/bold]
ping - Device identification
tm0-tm4 - Telemetry blocks (STANDARD/TEMP/VOLT/CURR/DIAG)
idle - Set IDLE mode
speed <rpm> - Set speed (e.g. speed 1000)
peek <addr> - Read memory (e.g. peek 0x06)
poke <addr> <val> - Write memory
clear - Clear all faults"""
        self.notify(help_text, severity="information", timeout=20)


def main() -> None:
    """Launch debug TUI."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler("debug_tui.log")],
    )

    app = DebugTuiApp()
    app.run()


if __name__ == "__main__":
    main()
