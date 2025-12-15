"""
Main TUI application using Textual.

Implements HOST_SPEC_RPi.md section 7: TUI Design.
Provides interactive terminal interface with dashboard, gauges, and packet monitoring.
"""

import logging
import math
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from nss_host.commands import Session
from nss_host.nsp import ControlMode
from nss_host.telemetry import TelemetryBlock
from nss_host.tui.widgets_new import (
    BarGauge,
    PacketMonitor,
    SpeedGauge,
    StatusPanel,
    WheelAnimation,
)

logger = logging.getLogger(__name__)


class SessionWithPacketCapture(Session):
    """
    Session subclass that captures TX/RX packets for display.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.packet_callback = None

    def _send_frame(self, frame):
        """Override to capture TX packets."""
        # Capture TX packet if callback is set
        if self.packet_callback:
            self.packet_callback("TX", frame.to_bytes(), datetime.now())

        # Call parent implementation
        super()._send_frame(frame)

    def _receive_frame(self, timeout_s):
        """Override to capture RX packets."""
        # Call parent implementation
        reply = super()._receive_frame(timeout_s)

        # Capture RX packet if callback is set and we got a reply
        if reply and self.packet_callback:
            self.packet_callback("RX", reply.to_bytes(), datetime.now())

        return reply


class ScenarioSelectScreen(ModalScreen[int | None]):
    """Modal screen for selecting a test scenario."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "select", "Select", priority=True),
        Binding("a", "run_all", "Run All", priority=True),
    ]

    DEFAULT_CSS = """
    ScenarioSelectScreen {
        align: center middle;
    }

    #scenario-dialog {
        width: 70;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #scenario-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #scenario-list {
        height: auto;
        max-height: 20;
        margin: 1 0;
        border: solid $primary;
    }

    #scenario-help {
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }

    .scenario-item {
        padding: 0 1;
    }

    .scenario-item:hover {
        background: $accent;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.scenarios = []

    def compose(self) -> ComposeResult:
        from nss_host.scenarios.icd_compliance import list_scenarios

        self.scenarios = list_scenarios()

        with Vertical(id="scenario-dialog"):
            yield Label("Select Test Scenario", id="scenario-title")
            yield ListView(
                *[
                    ListItem(
                        Label(f"{i+1}. {s['name']}", classes="scenario-item"),
                        id=f"scenario-{i}",
                    )
                    for i, s in enumerate(self.scenarios)
                ],
                id="scenario-list",
            )
            yield Label("[Enter] Run  [A] Run All  [Esc] Cancel", id="scenario-help")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle scenario selection."""
        if event.item and event.item.id:
            idx = int(event.item.id.split("-")[1])
            self.dismiss(idx + 1)  # 1-indexed for user

    def on_key(self, event) -> None:
        """Handle key events - ensure Escape closes the modal."""
        if event.key == "escape":
            event.prevent_default()
            event.stop()
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select highlighted item."""
        list_view = self.query_one("#scenario-list", ListView)
        if list_view.highlighted_child:
            idx = int(list_view.highlighted_child.id.split("-")[1])
            self.dismiss(idx + 1)

    def action_run_all(self) -> None:
        """Run all scenarios."""
        self.dismiss(-1)  # Special value for "run all"


class CommandPaletteScreen(ModalScreen[str | None]):
    """Modal screen for command palette."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "select", "Select", priority=True),
    ]

    DEFAULT_CSS = """
    CommandPaletteScreen {
        align: center middle;
    }

    #palette-dialog {
        width: 60;
        height: auto;
        max-height: 70%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #palette-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #palette-input {
        margin-bottom: 1;
    }

    #palette-list {
        height: auto;
        max-height: 15;
        border: solid $primary;
    }

    .cmd-item {
        padding: 0 1;
    }

    #palette-help {
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }
    """

    COMMANDS = [
        ("connect", "Connect to device", "c"),
        ("disconnect", "Disconnect from device", "d"),
        ("ping", "Send PING command", "p"),
        ("telemetry", "Request telemetry", "t"),
        ("scenarios", "Open scenario selector", "s"),
        ("run all", "Run all test scenarios", ""),
        ("idle", "Set wheel to IDLE mode", ""),
        ("speed 100", "Set speed to 100 RPM", ""),
        ("speed 500", "Set speed to 500 RPM", ""),
        ("speed 1000", "Set speed to 1000 RPM", ""),
        ("help", "Show help", "?"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.filtered_commands = list(self.COMMANDS)

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-dialog"):
            yield Label("Command Palette", id="palette-title")
            yield Input(placeholder="Type to filter...", id="palette-input")
            yield ListView(
                *[
                    ListItem(
                        Label(f"{cmd[0]:<15} {cmd[1]:<30} [{cmd[2]}]" if cmd[2] else f"{cmd[0]:<15} {cmd[1]}", classes="cmd-item"),
                        id=f"cmd-{i}",
                    )
                    for i, cmd in enumerate(self.COMMANDS)
                ],
                id="palette-list",
            )
            yield Label("[Enter] Select  [Esc] Close", id="palette-help")

    def on_mount(self) -> None:
        """Focus input on mount."""
        self.query_one("#palette-input", Input).focus()

    def on_key(self, event) -> None:
        """Handle key events - ensure Escape closes the palette."""
        if event.key == "escape":
            event.prevent_default()
            event.stop()
            self.dismiss(None)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter commands as user types."""
        query = event.value.lower()
        list_view = self.query_one("#palette-list", ListView)

        # Update visibility based on filter
        for i, cmd in enumerate(self.COMMANDS):
            item = self.query_one(f"#cmd-{i}", ListItem)
            matches = query in cmd[0].lower() or query in cmd[1].lower()
            item.display = matches

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Select first visible command or use input as command."""
        query = event.value.strip()
        if query:
            # First check if any command matches
            for cmd in self.COMMANDS:
                if query.lower() in cmd[0].lower():
                    self.dismiss(cmd[0])
                    return
            # Otherwise use input as-is
            self.dismiss(query)
        else:
            self.action_select()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle command selection."""
        if event.item and event.item.id:
            idx = int(event.item.id.split("-")[1])
            self.dismiss(self.COMMANDS[idx][0])

    def action_cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select highlighted item."""
        list_view = self.query_one("#palette-list", ListView)
        if list_view.highlighted_child and list_view.highlighted_child.id:
            idx = int(list_view.highlighted_child.id.split("-")[1])
            self.dismiss(self.COMMANDS[idx][0])


class NssHostApp(App):
    """
    NSS Host TUI application.

    Main Textual app with live dashboard, gauges, and packet monitor.
    """

    CSS = """
    Screen {
        layout: vertical;
    }

    #top_row {
        height: auto;
        max-height: 70%;
        layout: horizontal;
    }

    #left_panel {
        width: 1fr;
        layout: vertical;
    }

    #middle_panel {
        width: 1fr;
        layout: vertical;
    }

    #right_panel {
        width: 1fr;
    }

    #gauges_panel {
        height: auto;
        layout: vertical;
    }

    #packet_monitor {
        height: 1fr;
        min-height: 14;
        margin: 1;
        border: solid magenta;
    }

    #command_input {
        dock: bottom;
        height: 3;
        border: solid $accent;
    }

    WheelAnimation {
        height: auto;
        margin: 0 1;
    }

    SpeedGauge {
        height: auto;
        margin: 0 1;
    }

    StatusPanel {
        height: auto;
        margin: 0 1;
    }

    BarGauge {
        height: auto;
        margin: 0 1;
    }

    PacketMonitor {
        height: 100%;
        margin: 0;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("c", "connect", "Connect", priority=True),
        Binding("d", "disconnect", "Disconnect", priority=True),
        Binding("p", "ping", "Ping", priority=True),
        Binding("t", "telemetry", "Telemetry", priority=True),
        Binding("s", "scenarios", "Scenarios", priority=True),
        Binding("space", "refresh", "Refresh", priority=True),
        Binding("ctrl+p", "command_palette", "Commands", priority=True),
        Binding("question_mark", "show_help", "Help", priority=True),
        Binding("slash", "focus_input", "Input", priority=True),
        Binding("escape", "unfocus_input", "Unfocus", show=False, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.session: Session | None = None
        self.connected = False
        self.update_timer = None

        # Widgets
        self.wheel_anim = None
        self.speed_gauge = None
        self.current_gauge = None
        self.voltage_gauge = None
        self.power_gauge = None
        self.temp_gauge = None
        self.status_panel = None
        self.packet_monitor = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()

        with Container(id="top_row"):
            with Vertical(id="left_panel"):
                self.wheel_anim = WheelAnimation()
                yield self.wheel_anim

            with Vertical(id="middle_panel"):
                self.speed_gauge = SpeedGauge(max_rpm=6000.0)
                yield self.speed_gauge

                with Vertical(id="gauges_panel"):
                    self.current_gauge = BarGauge("Current", 0.0, 5.0, "A", width=25)
                    self.voltage_gauge = BarGauge("Voltage", 0.0, 30.0, "V", width=25)
                    self.power_gauge = BarGauge("Power", 0.0, 150.0, "W", width=25)
                    self.temp_gauge = BarGauge("Temp", 0.0, 100.0, "°C", width=25)

                    yield self.current_gauge
                    yield self.voltage_gauge
                    yield self.power_gauge
                    yield self.temp_gauge

            with Vertical(id="right_panel"):
                self.status_panel = StatusPanel()
                yield self.status_panel

        with Container(id="packet_monitor"):
            self.packet_monitor = PacketMonitor(max_packets=10)
            yield self.packet_monitor

        self.command_input = Input(placeholder="Press / to type, Ctrl+P for commands, or use shortcuts: c d p t s q", id="command_input")
        yield self.command_input

        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        self.title = "NSS Host - NRWA-T6 Reaction Wheel Controller"
        self.sub_title = "Raspberry Pi 5 | Keys: c=connect d=disconnect p=ping t=telemetry s=scenarios q=quit"

        # Set up periodic telemetry updates
        self.set_interval(0.2, self.update_telemetry)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command input."""
        command = event.value.strip()
        self.command_input.value = ""
        if command:
            self._execute_command(command)

    def action_connect(self) -> None:
        """Connect to device."""
        logger.info("action_connect: Attempting to connect...")
        if self.connected:
            logger.warning("action_connect: Already connected")
            self.notify("Already connected", severity="warning")
            return

        try:
            # Use SessionWithPacketCapture instead of regular Session
            from nss_host.serial_link import SerialLink

            logger.info("action_connect: Creating serial link (port=/dev/ttyAMA0, baud=460800)")
            # Create serial link
            link = SerialLink(
                port='/dev/ttyAMA0',
                baud=460800,
                timeout=0.1,
                de_gpio=18,
                nre_gpio=23,
            )

            logger.info("action_connect: Creating session with packet capture")
            # Create session with packet capture
            # Use longer timeout for telemetry requests (emulator needs time to build response)
            self.session = SessionWithPacketCapture(link, timeout_ms=200, retries=2)

            # Set up packet callback to update monitor
            self.session.packet_callback = self.packet_monitor.add_packet

            self.connected = True
            self.status_panel.update_status(connected=True)
            self.sub_title = "Raspberry Pi 5 | Connected ✓"
            logger.info("action_connect: Successfully connected")
            self.notify("Connected to emulator", severity="information")

            # Send initial ping
            logger.info("action_connect: Sending initial PING")
            self.action_ping()

        except Exception as e:
            logger.error(f"action_connect: Connection failed - {e}", exc_info=True)
            self.notify(f"Connection failed: {e}", severity="error")

    def action_disconnect(self) -> None:
        """Disconnect from device."""
        if not self.connected:
            self.notify("Not connected", severity="warning")
            return

        if self.session:
            self.session.close()
            self.session = None

        self.connected = False
        self.status_panel.update_status(connected=False)
        self.sub_title = "Raspberry Pi 5 | Disconnected"
        self.notify("Disconnected from emulator", severity="information")

    def action_ping(self) -> None:
        """Send PING command."""
        if not self.connected or not self.session:
            self.notify("Not connected", severity="error")
            return

        try:
            # Send ping (TX/RX packets captured automatically)
            self.session.ping()

            # Show stats (RX packet was received)
            self.status_panel.update_status(stats=self.session.stats)
            self.notify("PING successful ✓", severity="information")

        except Exception as e:
            self.notify(f"PING failed: {e}", severity="error")
            logger.error(f"PING error: {e}", exc_info=True)

    def action_telemetry(self) -> None:
        """Request telemetry manually."""
        self.update_telemetry()

    def action_refresh(self) -> None:
        """Refresh display."""
        if self.connected:
            self.update_telemetry()

    def action_scenarios(self) -> None:
        """Show scenarios modal for selection."""
        if not self.connected or not self.session:
            self.notify("Connect first before running scenarios", severity="error")
            return

        def handle_scenario_result(result: int | None) -> None:
            """Handle scenario selection result."""
            if result is None:
                return  # Cancelled
            elif result == -1:
                self.run_all_scenarios()
            else:
                self.run_scenario(result)

        self.push_screen(ScenarioSelectScreen(), handle_scenario_result)

    def action_command_palette(self) -> None:
        """Open command palette."""
        def handle_command(result: str | None) -> None:
            """Handle command selection."""
            if result:
                self._execute_command(result)

        self.push_screen(CommandPaletteScreen(), handle_command)

    def action_focus_input(self) -> None:
        """Focus the command input."""
        self.command_input.focus()

    def action_unfocus_input(self) -> None:
        """Unfocus the command input."""
        self.set_focus(None)

    def action_show_help(self) -> None:
        """Show help (bound to ?)."""
        self.show_help()

    def _execute_command(self, command: str) -> None:
        """Execute a command string."""
        command = command.strip().lower()

        if command == "connect":
            self.action_connect()
        elif command == "disconnect":
            self.action_disconnect()
        elif command == "ping":
            self.action_ping()
        elif command == "telemetry":
            self.action_telemetry()
        elif command == "scenarios" or command == "s":
            self.action_scenarios()
        elif command.startswith("run "):
            try:
                arg = command.split()[1]
                if arg == "all":
                    self.run_all_scenarios()
                else:
                    scenario_num = int(arg)
                    self.run_scenario(scenario_num)
            except (ValueError, IndexError):
                self.notify("Usage: run <number> or run all", severity="error")
        elif command.startswith("speed "):
            try:
                rpm = float(command.split()[1])
                self.command_speed(rpm)
            except (ValueError, IndexError):
                self.notify("Invalid speed command. Usage: speed <rpm>", severity="error")
        elif command.startswith("idle"):
            self.command_idle()
        elif command == "help":
            self.show_help()
        else:
            self.notify(f"Unknown command: {command}. Type 'help' for commands.", severity="warning")

    def run_scenario(self, scenario_num: int) -> None:
        """Run a specific scenario by number."""
        if not self.connected or not self.session:
            self.notify("Not connected", severity="error")
            return

        from nss_host.scenarios.icd_compliance import ALL_SCENARIOS, ScenarioResult

        if scenario_num < 1 or scenario_num > len(ALL_SCENARIOS):
            self.notify(f"Invalid scenario number. Use 1-{len(ALL_SCENARIOS)}", severity="error")
            return

        scenario_class = ALL_SCENARIOS[scenario_num - 1]
        self.notify(f"Running: {scenario_class.name}...", severity="information")

        try:
            scenario = scenario_class(self.session)
            report = scenario.run()

            # Show results
            if report.result == ScenarioResult.PASSED:
                self.notify(
                    f"✓ {report.name}: PASSED ({report.passed_count}/{len(report.steps)} steps)",
                    severity="information",
                    timeout=10,
                )
            else:
                self.notify(
                    f"✗ {report.name}: {report.result.value.upper()} "
                    f"({report.passed_count}/{len(report.steps)} steps passed)",
                    severity="error",
                    timeout=10,
                )

            # Log detailed results
            for step in report.steps:
                status = "PASS" if step.passed else "FAIL"
                logger.info(f"  [{status}] {step.name}: {step.message}")

        except Exception as e:
            self.notify(f"Scenario failed: {e}", severity="error")
            logger.error(f"Scenario error: {e}", exc_info=True)

    def run_all_scenarios(self) -> None:
        """Run all ICD compliance scenarios."""
        if not self.connected or not self.session:
            self.notify("Not connected", severity="error")
            return

        from nss_host.scenarios.icd_compliance import run_all_scenarios, ScenarioResult

        self.notify("Running all 6 ICD scenarios...", severity="information")

        try:
            reports = run_all_scenarios(self.session)

            passed = sum(1 for r in reports if r.result == ScenarioResult.PASSED)
            failed = len(reports) - passed

            if failed == 0:
                self.notify(
                    f"✓ All {passed} scenarios PASSED!",
                    severity="information",
                    timeout=15,
                )
            else:
                self.notify(
                    f"Results: {passed} passed, {failed} failed",
                    severity="warning",
                    timeout=15,
                )

            # Log summary
            for report in reports:
                status = "PASS" if report.result == ScenarioResult.PASSED else "FAIL"
                logger.info(f"[{status}] {report.name}: {report.passed_count}/{len(report.steps)} steps")

        except Exception as e:
            self.notify(f"Scenarios failed: {e}", severity="error")
            logger.error(f"Scenarios error: {e}", exc_info=True)

    def command_speed(self, rpm: float) -> None:
        """Command wheel to specific speed."""
        if not self.connected or not self.session:
            self.notify("Not connected", severity="error")
            return

        try:
            # Use new unified API: mode + setpoint in one call
            self.session.app_command(ControlMode.SPEED, rpm)
            self.notify(f"Commanded {rpm:.0f} RPM", severity="information")
        except Exception as e:
            self.notify(f"Command failed: {e}", severity="error")

    def command_idle(self) -> None:
        """Set wheel to idle mode."""
        if not self.connected or not self.session:
            self.notify("Not connected", severity="error")
            return

        try:
            self.session.app_command(ControlMode.IDLE)
            self.notify("Wheel set to IDLE", severity="information")
        except Exception as e:
            self.notify(f"Command failed: {e}", severity="error")

    def show_help(self) -> None:
        """Show available commands."""
        help_text = """Keyboard Shortcuts:
  c - Connect to device      d - Disconnect
  p - Send PING              t - Request telemetry
  s - Open scenario selector q - Quit
  / - Focus command input    Esc - Unfocus input
  Ctrl+P - Command palette   ? - This help
  Space - Refresh display

Commands (type in input or use Ctrl+P):
  connect, disconnect, ping, telemetry
  speed <rpm> - Set speed mode (e.g. speed 1000)
  idle - Set idle mode
  run <n> - Run scenario n
  run all - Run all scenarios"""
        self.notify(help_text, severity="information", timeout=20)

    def update_telemetry(self) -> None:
        """Update telemetry displays."""
        if not self.connected or not self.session:
            return

        try:
            # Get STANDARD telemetry (0x00) for primary dynamics
            logger.debug("update_telemetry: Requesting STANDARD telemetry...")
            tm = self.session.app_telemetry(TelemetryBlock.STANDARD)
            logger.debug(f"update_telemetry: Received - control_mode={tm.control_mode}, speed={tm.speed_rpm:.2f} RPM, current={tm.current_ma:.3f} mA")

            # Extract mode and compute mode string
            # Per ICD: IDLE=0x00, CURRENT=0x01, SPEED=0x02, TORQUE=0x04, PWM=0x08
            mode_map = {
                ControlMode.IDLE: "IDLE",
                ControlMode.CURRENT: "CURRENT",
                ControlMode.SPEED: "SPEED",
                ControlMode.TORQUE: "TORQUE",
                ControlMode.PWM: "PWM",
            }
            mode_str = mode_map.get(tm.control_mode, f"0x{tm.control_mode:02X}")

            # Get VOLT telemetry (0x02) for accurate bus voltage
            try:
                volt_tm = self.session.app_telemetry(TelemetryBlock.VOLT)
                # Use 30V rail as bus voltage (closest to drive voltage)
                bus_voltage = volt_tm.v_30v
                logger.debug(f"update_telemetry: VOLT block - v_30v={bus_voltage:.2f} V")
            except Exception as e:
                logger.warning(f"VOLT telemetry failed: {e}, using 0.0")
                bus_voltage = 0.0

            # Get TEMP telemetry (0x01) for temperature readings
            # Note: Raw ADC values - would need conversion formula from ICD
            try:
                temp_tm = self.session.app_telemetry(TelemetryBlock.TEMP)
                # Raw ADC value - display as-is for now (conversion requires ICD formula)
                motor_temp_raw = temp_tm.temp_motor_raw
                # Placeholder conversion (actual formula depends on thermistor)
                motor_temp = motor_temp_raw * 0.01  # Rough estimate
                logger.debug(f"update_telemetry: TEMP block - motor_raw={motor_temp_raw}")
            except Exception as e:
                logger.warning(f"TEMP telemetry failed: {e}, using 0.0")
                motor_temp = 0.0

            # Calculate omega (rad/s) from RPM: omega = RPM * 2π / 60
            omega_rad_s = tm.speed_rpm * 2.0 * math.pi / 60.0

            # Convert current from mA to A for display
            current_a = tm.current_ma / 1000.0

            # Estimate power from voltage and current (P = V * I)
            power_w = bus_voltage * current_a

            # Estimate torque from current (rough approximation)
            # Actual torque constant depends on motor, ~0.01 Nm/A typical for small motors
            torque_nm = current_a * 0.01

            # Estimate momentum (H = I * ω, where I is moment of inertia)
            # Typical small RW inertia ~0.001 kg·m²
            momentum_nms = 0.001 * omega_rad_s

            # Update ALL widgets atomically
            self.wheel_anim.update_rpm(tm.speed_rpm, mode=mode_str)
            self.speed_gauge.update_rpm(tm.speed_rpm)
            self.current_gauge.update_value(current_a)
            self.voltage_gauge.update_value(bus_voltage)
            self.power_gauge.update_value(abs(power_w))
            self.temp_gauge.update_value(motor_temp)

            # Update status panel with telemetry info
            self.status_panel.update_status(
                connected=True,
                mode=mode_str,
                faults=tm.fault,
                stats=self.session.stats,
                # Computed dynamics
                torque_nm=torque_nm,
                momentum_nms=momentum_nms,
                omega_rad_s=omega_rad_s,
            )

        except Exception as e:
            logger.error(f"Telemetry update failed: {e}", exc_info=True)
            # Don't disconnect on transient errors - just log and notify
            # This allows recovery from temporary communication issues
            if self.connected:
                self.notify(f"Telemetry error: {e}", severity="warning")
                # Note: NOT setting self.connected = False here
                # Only disconnect on repeated failures or explicit user action


def main() -> None:
    """
    Launch TUI application.

    Entry point for nss-tui command.
    """
    # Configure comprehensive logging with timestamps
    import sys
    from datetime import datetime

    # Generate timestamped log filename
    log_filename = f"nss_host_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # Configure logging to FILE ONLY (no stderr/stdout to avoid TUI conflict)
    logging.basicConfig(
        level=logging.DEBUG,  # Capture all levels
        format="%(asctime)s.%(msecs)03d [%(levelname)-8s] %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_filename)  # File only - no console output
        ],
    )

    logger.info("=" * 80)
    logger.info("NSS Host TUI Starting")
    logger.info(f"Log file: {log_filename}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)

    # Run TUI
    try:
        app = NssHostApp()
        app.run()
    except Exception as e:
        logger.critical(f"TUI crashed: {e}", exc_info=True)
        raise
    finally:
        logger.info("=" * 80)
        logger.info("NSS Host TUI Exiting")
        logger.info("=" * 80)


if __name__ == "__main__":
    main()
