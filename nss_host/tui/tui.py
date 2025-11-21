"""
Main TUI application using Textual.

Implements HOST_SPEC_RPi.md section 7: TUI Design.
Provides interactive terminal interface with dashboard, tables, logs, and command palette.
"""

import logging

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Static

logger = logging.getLogger(__name__)


class DashboardView(Static):
    """
    Dashboard view with live gauges.

    Displays speed, torque, current, power, mode, and flags.
    """

    def compose(self) -> ComposeResult:
        yield Static("Dashboard View\n\nSpeed: -- RPM\nCurrent: -- A\nMode: --")


class TablesView(Static):
    """
    Tables browser view.

    Lists all tables and allows browsing fields.
    """

    def compose(self) -> ComposeResult:
        yield Static("Tables View\n\n1. Dynamics\n2. Setpoints\n3. Limits\n4. Protections")


class LinkView(Static):
    """
    Link status view.

    Shows serial/RS-485 health, SLIP/CRC counts, port A/B.
    """

    def compose(self) -> ComposeResult:
        yield Static("Link Status\n\nPort: /dev/ttyAMA0\nBaud: 460800\nStatus: Disconnected")


class LogsView(Static):
    """
    Logs view with rolling log display.

    Supports filtering by module/level.
    """

    def compose(self) -> ComposeResult:
        yield Static("Logs View\n\n[INFO] NSS Host TUI started")


class NssHostApp(App):
    """
    NSS Host TUI application.

    Main Textual app with multiple views and command palette.
    """

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2;
        grid-rows: 1fr;
    }

    DashboardView {
        border: solid $accent;
        height: 100%;
        content-align: center middle;
    }

    TablesView {
        border: solid $accent;
        height: 100%;
        content-align: center middle;
    }

    LinkView {
        border: solid $accent;
        height: 100%;
        content-align: center middle;
    }

    LogsView {
        border: solid $accent;
        height: 100%;
        content-align: center middle;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "view_dashboard", "Dashboard"),
        ("t", "view_tables", "Tables"),
        ("l", "view_link", "Link"),
        ("g", "view_logs", "Logs"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.session: object | None = None
        self.current_view = "dashboard"

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            DashboardView(id="dashboard"),
            TablesView(id="tables"),
        )
        yield Footer()

    def action_view_dashboard(self) -> None:
        """Switch to dashboard view."""
        logger.info("Switching to dashboard view")
        self.current_view = "dashboard"

    def action_view_tables(self) -> None:
        """Switch to tables view."""
        logger.info("Switching to tables view")
        self.current_view = "tables"

    def action_view_link(self) -> None:
        """Switch to link view."""
        logger.info("Switching to link view")
        self.current_view = "link"

    def action_view_logs(self) -> None:
        """Switch to logs view."""
        logger.info("Switching to logs view")
        self.current_view = "logs"

    def on_mount(self) -> None:
        """Called when app starts."""
        self.title = "NSS Host - NRWA-T6 Reaction Wheel Controller"
        self.sub_title = "Raspberry Pi 5 | Disconnected"


def main() -> None:
    """
    Launch TUI application.

    Entry point for nss-tui command.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler("nss_host.log"), logging.StreamHandler()],
    )

    # Run TUI
    app = NssHostApp()
    app.run()


if __name__ == "__main__":
    main()
