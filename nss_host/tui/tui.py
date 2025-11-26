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
        elif command.startswith("speed "):
            try:
                rpm = float(command.split()[1])
                self.command_speed(rpm)
            except (ValueError, IndexError):
                self.notify("Invalid speed command. Usage: speed <rpm>", severity="error")
        else:
            self.notify(f"Unknown command: {command}", severity="warning")

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

    def command_speed(self, rpm: float) -> None:
        """Command wheel to specific speed."""
        if not self.connected or not self.session:
            self.notify("Not connected", severity="error")
            return

        try:
            # First set mode to SPEED, then set the speed setpoint
            self.session.app_command(mode='SPEED')
            self.session.app_command(setpoint_rpm=rpm)
            self.notify(f"Commanded {rpm:.0f} RPM", severity="information")
        except Exception as e:
            self.notify(f"Command failed: {e}", severity="error")

    def update_telemetry(self) -> None:
        """Update telemetry displays."""
        if not self.connected or not self.session:
            return

        try:
            # Get STANDARD telemetry (0x00) for primary dynamics
            logger.debug("update_telemetry: Requesting STANDARD telemetry...")
            tm = self.session.app_telemetry(TelemetryBlock.STANDARD)
            logger.debug(f"update_telemetry: Received - mode={tm.mode}, speed={tm.speed_rpm:.2f} RPM, current={tm.current_a:.3f} A")

            # Extract mode and compute mode string ONCE
            # Per REGS.md line 257: 0=CURRENT, 1=SPEED, 2=TORQUE, 3=PWM
            mode_map = {0: "CURRENT", 1: "SPEED", 2: "TORQUE", 3: "PWM"}
            mode_str = mode_map.get(tm.mode, "UNKNOWN")

            # Get VOLT telemetry (0x02) for accurate bus voltage
            try:
                volt_tm = self.session.app_telemetry(TelemetryBlock.VOLT)
                bus_voltage = volt_tm.v_bus
                logger.debug(f"update_telemetry: VOLT block - v_bus={bus_voltage:.2f} V")
            except Exception as e:
                logger.warning(f"VOLT telemetry failed: {e}, using 0.0")
                bus_voltage = 0.0

            # Get TEMP telemetry (0x01) for temperature readings
            try:
                temp_tm = self.session.app_telemetry(TelemetryBlock.TEMP)
                motor_temp = temp_tm.temp_motor_c
                logger.debug(f"update_telemetry: TEMP block - motor={motor_temp:.1f} °C")
            except Exception as e:
                logger.warning(f"TEMP telemetry failed: {e}, using 0.0")
                motor_temp = 0.0

            # Calculate omega (rad/s) from RPM: omega = RPM * 2π / 60
            omega_rad_s = tm.speed_rpm * 2.0 * math.pi / 60.0

            # Update ALL widgets atomically
            self.wheel_anim.update_rpm(tm.speed_rpm, mode=mode_str)
            self.speed_gauge.update_rpm(tm.speed_rpm)
            self.current_gauge.update_value(tm.current_a)
            self.voltage_gauge.update_value(bus_voltage)
            self.power_gauge.update_value(abs(tm.power_w))
            self.temp_gauge.update_value(motor_temp)

            # Update status panel with extended telemetry info
            self.status_panel.update_status(
                connected=True,
                mode=mode_str,
                faults=tm.fault_status,
                stats=self.session.stats,
                # Additional dynamics from STANDARD telemetry
                torque_nm=tm.torque_nm,
                momentum_nms=tm.momentum,
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
