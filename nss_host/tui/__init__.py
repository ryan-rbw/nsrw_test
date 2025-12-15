"""
Terminal UI (TUI) for NSS Host.

Implements HOST_SPEC_RPi.md section 7: TUI Design.

Available TUIs:
- main TUI: python -m nss_host.tui.tui
- debug TUI: python -m nss_host.tui.debug_tui
"""

__all__ = ["main", "debug_main"]


def main():
    """Launch main TUI (requires textual)."""
    from nss_host.tui.tui import main as _main
    _main()


def debug_main():
    """Launch debug TUI (requires textual)."""
    from nss_host.tui.debug_tui import main as _debug_main
    _debug_main()
