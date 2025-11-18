"""
Command palette for TUI.

Implements HOST_SPEC_RPi.md section 7.2: Command Palette.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class Command:
    """
    Command palette entry.

    Attributes:
        name: Command name.
        aliases: Alternative names/abbreviations.
        description: Command description.
        handler: Command handler function.
    """

    name: str
    aliases: List[str]
    description: str
    handler: Callable


# Command palette registry
COMMANDS: List[Command] = [
    Command("help", ["?"], "Show help", lambda: None),
    Command("quit", ["q", "exit"], "Exit TUI", lambda: None),
    Command("connect", [], "Connect to device", lambda: None),
    Command("disconnect", [], "Disconnect from device", lambda: None),
    Command("tables", [], "List tables", lambda: None),
    Command("describe", [], "Describe table", lambda: None),
    Command("get", [], "Get table field value", lambda: None),
    Command("set", [], "Set table field value", lambda: None),
    Command("peek", [], "Read memory/registers", lambda: None),
    Command("poke", [], "Write memory/registers", lambda: None),
    Command("ping", [], "Ping device", lambda: None),
    Command("fault", [], "Fault operations", lambda: None),
    Command("scenario", [], "Scenario operations", lambda: None),
    Command("record", [], "Record/replay NSP traffic", lambda: None),
]


def find_command(name: str) -> Optional[Command]:
    """
    Find command by name or alias.

    Args:
        name: Command name or alias.

    Returns:
        Command if found, None otherwise.
    """
    name_lower = name.lower()
    for cmd in COMMANDS:
        if cmd.name == name_lower or name_lower in cmd.aliases:
            return cmd
    return None
