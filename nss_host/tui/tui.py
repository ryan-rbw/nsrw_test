"""
Main TUI application using Textual.

Implements HOST_SPEC_RPi.md section 7: TUI Design.
Provides interactive terminal interface with dashboard, gauges, and packet monitoring.
"""

import logging
import math
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Static

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
        ("q", "quit", "Quit"),
        ("c", "connect", "Connect"),
        ("d", "disconnect", "Disconnect"),
        ("p", "ping", "Ping"),
        ("t", "telemetry", "Telemetry"),
        ("s", "scenarios", "Scenarios"),
        ("space", "refresh", "Refresh"),
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

        self.command_input = Input(placeholder="Enter command (ping, telemetry, connect, disconnect)...", id="command_input")
        yield self.command_input

        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        self.title = "NSS Host - NRWA-T6 Reaction Wheel Controller"
        self.sub_title = "Raspberry Pi 5 | Press 'c' to connect"

        # Set up periodic telemetry updates
        self.set_interval(0.2, self.update_telemetry)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command input."""
        command = event.value.strip().lower()
        self.command_input.value = ""

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
        """Show scenarios menu and run selected scenario."""
        if not self.connected or not self.session:
            self.notify("Connect first before running scenarios", severity="error")
            return

        # Show available scenarios
        from nss_host.scenarios.icd_compliance import list_scenarios

        scenarios = list_scenarios()
        scenario_list = "\n".join([f"  {i+1}. {s['name']}" for i, s in enumerate(scenarios)])
        self.notify(
            f"Available scenarios:\n{scenario_list}\n\nType 'run <number>' to execute",
            severity="information",
            timeout=10,
        )

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
        help_text = """Commands:
  connect     - Connect to emulator
  disconnect  - Disconnect
  ping        - Send PING
  telemetry   - Request telemetry
  speed <rpm> - Set speed mode
  idle        - Set idle mode
  scenarios   - List test scenarios
  run <n>     - Run scenario n
  run all     - Run all scenarios
  help        - Show this help

Shortcuts: c=connect, d=disconnect, p=ping, t=telemetry, s=scenarios, q=quit"""
        self.notify(help_text, severity="information", timeout=15)

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
