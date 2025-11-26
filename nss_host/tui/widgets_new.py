"""
Redesigned TUI widgets using Textual's native features.

Uses Textual's built-in widgets and layout instead of manual ASCII art.
This provides automatic alignment, better rendering, and easier maintenance.
"""

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, Label, DataTable


class SpeedGauge(Static):
    """
    Speed gauge using Textual's built-in styling.
    """

    DEFAULT_CSS = """
    SpeedGauge {
        border: solid green;
        height: 7;
        padding: 1;
    }
    """

    def __init__(self, max_rpm: float = 6000.0, **kwargs):
        super().__init__(**kwargs)
        self.max_rpm = max_rpm
        self.current_rpm = 0.0

    def update_rpm(self, rpm: float) -> None:
        """Update gauge with new RPM value."""
        self.current_rpm = rpm

        # Calculate bar percentage
        ratio = min(abs(rpm) / self.max_rpm, 1.0)
        bar_width = 30
        filled = int(ratio * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Direction indicator
        direction = "→" if rpm >= 0 else "←"

        content = f"""[bold]SPEED (RPM)[/bold]

{direction} {abs(rpm):>7.1f} RPM

{bar}

Max: ±{self.max_rpm:.0f} RPM"""

        self.update(content)
        self.refresh()

    def on_mount(self) -> None:
        """Initialize display."""
        self.update_rpm(0.0)


class WheelAnimation(Static):
    """
    Reaction wheel animation using Textual widgets.
    """

    DEFAULT_CSS = """
    WheelAnimation {
        border: solid cyan;
        height: 10;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.angle = 0
        self.rpm = 0.0
        self.mode = "UNKNOWN"
        self.frames = ["│", "╱", "─", "╲"]

    def update_rpm(self, rpm: float, mode: str = None) -> None:
        """Update animation based on RPM and mode."""
        self.rpm = rpm
        if mode is not None:
            self.mode = mode
        if abs(rpm) > 10:
            self.angle = (self.angle + 1) % len(self.frames)

        frame = self.frames[self.angle]
        direction = "CW ↻" if rpm > 0 else "CCW ↺" if rpm < 0 else "IDLE"

        content = f"""[bold]REACTION WHEEL[/bold]

    ╭────────╮
   │    {frame}    │
    ╰────────╯

  MODE: {self.mode:<8} DIR: {direction}
       {abs(rpm):>6.1f} RPM"""

        self.update(content)
        self.refresh()

    def on_mount(self) -> None:
        """Initialize display."""
        self.update_rpm(0.0)


class BarGauge(Static):
    """
    Horizontal bar gauge using Textual's rendering.
    """

    DEFAULT_CSS = """
    BarGauge {
        height: 1;
        padding: 0 1;
    }
    """

    def __init__(self, label: str, min_val: float, max_val: float,
                 unit: str, width: int = 25, **kwargs):
        super().__init__(**kwargs)
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        self.width = width
        self.current_value = 0.0

    def update_value(self, value: float) -> None:
        """Update gauge value."""
        self.current_value = value

        # Calculate bar fill
        ratio = (value - self.min_val) / (self.max_val - self.min_val)
        ratio = max(0.0, min(1.0, ratio))
        filled = int(ratio * self.width)
        bar = "█" * filled + "░" * (self.width - filled)

        self.update(f"{self.label:10} [{bar}] {value:7.2f} {self.unit}")
        self.refresh()

    def on_mount(self) -> None:
        """Initialize display."""
        self.update_value(0.0)


class StatusPanel(Static):
    """
    Status panel using Textual's DataTable for perfect alignment.
    """

    DEFAULT_CSS = """
    StatusPanel {
        border: solid yellow;
        height: auto;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connected = False
        self.mode = "UNKNOWN"
        self.faults = 0x00000000
        self.stats = {
            "frames_tx": 0,
            "frames_rx": 0,
            "crc_errors": 0,
            "timeouts": 0,
            "nacks": 0
        }
        # Extended dynamics
        self.torque_nm = 0.0
        self.momentum_nms = 0.0
        self.omega_rad_s = 0.0

    def update_status(self, connected: bool = None, mode: str = None,
                     faults: int = None, stats: dict = None,
                     torque_nm: float = None, momentum_nms: float = None,
                     omega_rad_s: float = None) -> None:
        """Update status display."""
        if connected is not None:
            self.connected = connected
        if mode is not None:
            self.mode = mode
        if faults is not None:
            self.faults = faults
        if stats is not None:
            self.stats.update(stats)
        if torque_nm is not None:
            self.torque_nm = torque_nm
        if momentum_nms is not None:
            self.momentum_nms = momentum_nms
        if omega_rad_s is not None:
            self.omega_rad_s = omega_rad_s

        # Build status display
        conn_str = "[green]CONNECTED[/green]" if self.connected else "[red]DISCONNECTED[/red]"
        fault_str = "[green][OK][/green]" if self.faults == 0 else f"[yellow]0x{self.faults:08X}[/yellow]"

        # Convert torque to mNm for display (stored as Nm)
        torque_mnm = self.torque_nm * 1000.0

        content = f"""[bold]SYSTEM STATUS[/bold]

Connection:  {conn_str}
Mode:        {self.mode}
Faults:      {fault_str}

[bold]DYNAMICS[/bold]

Torque:      {torque_mnm:>8.2f} mNm
Omega:       {self.omega_rad_s:>8.2f} rad/s
Momentum:    {self.momentum_nms:>8.4f} Nms

[bold]LINK STATISTICS[/bold]

TX Frames:   {self.stats['frames_tx']:>6}
RX Frames:   {self.stats['frames_rx']:>6}
CRC Errors:  {self.stats['crc_errors']:>6}
Timeouts:    {self.stats['timeouts']:>6}
NACKs:       {self.stats['nacks']:>6}"""

        self.update(content)
        self.refresh()

    def on_mount(self) -> None:
        """Initialize display."""
        self.update_status()


class PacketMonitor(Static):
    """
    Packet monitor with scrollable display.
    """

    DEFAULT_CSS = """
    PacketMonitor {
        height: 100%;
        padding: 0 1;
    }
    """

    def __init__(self, max_packets: int = 10, **kwargs):
        super().__init__(**kwargs)
        self.max_packets = max_packets
        self.packets = []

    def render(self) -> str:
        """Render the widget content."""
        if not self.packets:
            return "[bold]PACKET MONITOR[/bold] (Last 10 Frames)\n\n[dim]No packets yet...[/dim]"

        lines = ["[bold]PACKET MONITOR[/bold] (Last 10 Frames)\n"]

        for pkt in reversed(self.packets):  # Newest first
            time_str = pkt["time"].strftime("%H:%M:%S.%f")[:-3]
            dir_str = pkt["dir"]
            hex_str = pkt["data"].hex().upper()

            # Format as groups of 2 bytes
            hex_groups = " ".join([hex_str[i:i+2] for i in range(0, len(hex_str), 2)])

            # Truncate if too long
            if len(hex_groups) > 60:
                hex_groups = hex_groups[:57] + "..."

            indicator = "[cyan]→[/cyan]" if dir_str == "TX" else "[green]←[/green]"
            lines.append(f"{time_str} {indicator} {dir_str:2} {hex_groups}")

        return "\n".join(lines)

    def add_packet(self, direction: str, data: bytes, timestamp: datetime = None) -> None:
        """Add packet to monitor."""
        if timestamp is None:
            timestamp = datetime.now()

        self.packets.append({
            "time": timestamp,
            "dir": direction,
            "data": data
        })

        # Keep only last N packets
        if len(self.packets) > self.max_packets:
            self.packets = self.packets[-self.max_packets:]

        self.refresh()

    def clear(self) -> None:
        """Clear all packets."""
        self.packets = []
        self.refresh()
