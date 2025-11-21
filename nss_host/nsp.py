"""
NSP (Network Serial Protocol) implementation.

Implements HOST_SPEC_RPi.md section 5: Protocol Details (NSP).
Control byte format: [POLL|B|A|cmd4..0]
Commands: PING (0x00), PEEK (0x02), POKE (0x03), APP-TM (0x07),
          APP-CMD (0x08), CLEAR-FAULT (0x09), CONFIG-PROT (0x0A), TRIP-LCL (0x0B)
"""

from dataclasses import dataclass
from enum import IntEnum


class NspCommand(IntEnum):
    """NSP command codes."""

    PING = 0x00
    PEEK = 0x02
    POKE = 0x03
    APP_TM = 0x07
    APP_CMD = 0x08
    CLEAR_FAULT = 0x09
    CONFIG_PROT = 0x0A
    TRIP_LCL = 0x0B


# Control byte bit masks
POLL_BIT = 0x80  # Bit 7: POLL (1=request, 0=reply)
B_BIT = 0x40  # Bit 6: B (unused by host)
ACK_BIT = 0x20  # Bit 5: A (ACK bit, set by device in reply)
CMD_MASK = 0x1F  # Bits 4-0: Command code


@dataclass
class NspFrame:
    """
    NSP frame structure per NRWA-T6 emulator implementation.

    Attributes:
        dest_addr: Destination address (0-127, set by ADDR0-ADDR2 pins)
        src_addr: Source address (0-127, host typically uses 0x11)
        control: Control byte [POLL|B|A|cmd4..0]
        payload: Frame payload (command/telemetry data)
        is_request: True if POLL bit is set
        is_ack: True if ACK bit is set
        command: Command code (0-31)

    Note:
        The emulator expects format: [Dest | Src | Ctrl | Len | Data... | CRC]
        where Len is the length of the Data field (not in ICD but required by emulator).
    """

    dest_addr: int
    src_addr: int
    control: int
    payload: bytes

    @property
    def is_request(self) -> bool:
        """Check if frame is a request (POLL=1)."""
        return bool(self.control & POLL_BIT)

    @property
    def is_ack(self) -> bool:
        """Check if frame is an ACK (A=1)."""
        return bool(self.control & ACK_BIT)

    @property
    def is_nack(self) -> bool:
        """Check if frame is a NACK (A=0 in reply)."""
        return not self.is_request and not self.is_ack

    @property
    def command(self) -> int:
        """Get command code (0-31)."""
        return self.control & CMD_MASK

    def to_bytes(self) -> bytes:
        """Convert frame to bytes per ICD: [dest_addr][src_addr][control][payload]."""
        return bytes([self.dest_addr, self.src_addr, self.control]) + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "NspFrame":
        """
        Parse NSP frame from bytes per ICD format.

        Args:
            data: Raw frame data [dest_addr][src_addr][control][payload].

        Returns:
            Parsed NspFrame.

        Raises:
            ValueError: If data is too short.
        """
        if len(data) < 3:
            raise ValueError("NSP frame must have at least dest_addr, src_addr, and control bytes")

        return cls(
            dest_addr=data[0], src_addr=data[1], control=data[2], payload=data[3:]
        )


def make_request(
    command: NspCommand | int,
    payload: bytes = b"",
    dest_addr: int = 0x07,
    src_addr: int = 0x11,
) -> NspFrame:
    """
    Create NSP request frame per ICD specification.

    Args:
        command: Command code.
        payload: Command payload.
        dest_addr: Destination address (default 0x07 for typical emulator config).
        src_addr: Source address (default 0x11 for host).

    Returns:
        NSP request frame with POLL=1, A=0, proper addressing.
    """
    control = POLL_BIT | (int(command) & CMD_MASK)
    return NspFrame(dest_addr=dest_addr, src_addr=src_addr, control=control, payload=payload)


def make_reply(
    command: NspCommand | int,
    payload: bytes = b"",
    ack: bool = True,
    dest_addr: int = 0x11,
    src_addr: int = 0x07,
) -> NspFrame:
    """
    Create NSP reply frame per ICD specification.

    Args:
        command: Command code.
        payload: Reply payload.
        ack: True for ACK, False for NACK.
        dest_addr: Destination address (typically host address 0x11).
        src_addr: Source address (typically device address 0x07).

    Returns:
        NSP reply frame with POLL=0, A=ack, proper addressing.
    """
    control = int(command) & CMD_MASK
    if ack:
        control |= ACK_BIT
    return NspFrame(dest_addr=dest_addr, src_addr=src_addr, control=control, payload=payload)


class NspError(Exception):
    """Base exception for NSP errors."""

    pass


class NspNackError(NspError):
    """NACK received from device."""

    def __init__(self, command: int, payload: bytes):
        self.command = command
        self.payload = payload
        super().__init__(f"NACK for command 0x{command:02X}: {payload.hex()}")


class NspTimeoutError(NspError):
    """Timeout waiting for reply."""

    def __init__(self, command: int):
        self.command = command
        super().__init__(f"Timeout waiting for reply to command 0x{command:02X}")


class NspCrcError(NspError):
    """CRC check failed."""

    def __init__(self, message: str = "CRC check failed"):
        super().__init__(message)


def validate_reply(request: NspFrame, reply: NspFrame) -> None:
    """
    Validate that reply matches request.

    Args:
        request: Original request frame.
        reply: Received reply frame.

    Raises:
        NspError: If reply is invalid.
        NspNackError: If reply is a NACK.
    """
    # Check command code matches
    if reply.command != request.command:
        raise NspError(
            f"Reply command 0x{reply.command:02X} does not match "
            f"request command 0x{request.command:02X}"
        )

    # Check for NACK
    if reply.is_nack:
        raise NspNackError(reply.command, reply.payload)

    # Ensure reply is not a request
    if reply.is_request:
        raise NspError("Received request frame when expecting reply")
