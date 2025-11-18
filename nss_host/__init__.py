"""
NSS Host - NRWA-T6 Reaction Wheel Host Driver

Python host driver for Raspberry Pi 5 to control and test the NRWA-T6-compatible
reaction wheel emulator over RS-485 with SLIP + NSP framing.

This package implements HOST_SPEC_RPi.md sections 1-24.
"""

__version__ = "0.1.0"
__author__ = "NRWA-T6 Project Contributors"

from nss_host.commands import Session

__all__ = ["Session", "__version__"]
