"""
RS-485 serial link with GPIO control for DE/nRE.

Implements HOST_SPEC_RPi.md section 2: Hardware Topology & Wiring.
Provides pyserial interface with RS-485 direction control via GPIO.
"""

import logging
import time
from typing import Optional

import serial

try:
    from gpiozero import OutputDevice

    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

logger = logging.getLogger(__name__)


class SerialLink:
    """
    RS-485 serial link with GPIO direction control.

    Manages serial port and DE/nRE GPIO pins for half/full-duplex RS-485.
    """

    def __init__(
        self,
        port: str,
        baud: int = 460800,
        timeout: float = 0.01,
        de_gpio: Optional[int] = None,
        nre_gpio: Optional[int] = None,
    ):
        """
        Initialize serial link.

        Args:
            port: Serial port device (e.g., '/dev/ttyAMA0').
            baud: Baud rate (default 460800).
            timeout: Read timeout in seconds (default 10ms).
            de_gpio: Driver Enable GPIO (BCM numbering, active-high).
            nre_gpio: Receiver Enable GPIO (BCM numbering, active-low).
        """
        self.port = port
        self.baud = baud
        self.timeout = timeout

        # Initialize serial port
        self.serial = serial.Serial(
            port=port, baudrate=baud, timeout=timeout, bytesize=8, parity="N", stopbits=1
        )

        # Initialize GPIO for RS-485 direction control
        self.de_pin: Optional[OutputDevice] = None
        self.nre_pin: Optional[OutputDevice] = None

        if GPIO_AVAILABLE and de_gpio is not None:
            try:
                self.de_pin = OutputDevice(de_gpio, initial_value=False)
                logger.info(f"Initialized DE GPIO on pin {de_gpio}")
            except Exception as e:
                logger.warning(f"Failed to initialize DE GPIO: {e}")

        if GPIO_AVAILABLE and nre_gpio is not None:
            try:
                # nRE is active-low, so we set it low to enable receiver
                self.nre_pin = OutputDevice(nre_gpio, initial_value=False)
                logger.info(f"Initialized nRE GPIO on pin {nre_gpio}")
            except Exception as e:
                logger.warning(f"Failed to initialize nRE GPIO: {e}")

        # Full-duplex mode: always enable receiver
        self._enable_rx()

        logger.info(f"Serial link opened: {port} @ {baud} baud")

    def close(self) -> None:
        """Close serial port and release GPIO."""
        if self.serial.is_open:
            self.serial.close()

        if self.de_pin:
            self.de_pin.close()
        if self.nre_pin:
            self.nre_pin.close()

        logger.info("Serial link closed")

    def _enable_tx(self) -> None:
        """Enable RS-485 transmitter (DE=1)."""
        if self.de_pin:
            self.de_pin.on()

    def _disable_tx(self) -> None:
        """Disable RS-485 transmitter (DE=0, tri-state)."""
        if self.de_pin:
            self.de_pin.off()

    def _enable_rx(self) -> None:
        """Enable RS-485 receiver (nRE=0)."""
        if self.nre_pin:
            self.nre_pin.off()  # Active-low

    def write(self, data: bytes) -> int:
        """
        Write data to serial port.

        Args:
            data: Bytes to write.

        Returns:
            Number of bytes written.
        """
        self._enable_tx()
        try:
            n = self.serial.write(data)
            self.serial.flush()  # Wait for TX to complete
            # Small delay to ensure last byte is transmitted
            time.sleep(len(data) / (self.baud / 10) + 0.001)
            return n
        finally:
            self._disable_tx()  # Tri-state TX when idle

    def read(self, size: int = 1) -> bytes:
        """
        Read data from serial port.

        Args:
            size: Number of bytes to read.

        Returns:
            Bytes read (may be shorter than requested if timeout).
        """
        return self.serial.read(size)

    def read_available(self) -> bytes:
        """
        Read all available data from serial port.

        Returns:
            All bytes currently in receive buffer.
        """
        available = self.serial.in_waiting
        if available > 0:
            return self.serial.read(available)
        return b""

    def flush_input(self) -> None:
        """Flush input buffer."""
        self.serial.reset_input_buffer()

    def flush_output(self) -> None:
        """Flush output buffer."""
        self.serial.reset_output_buffer()

    @property
    def in_waiting(self) -> int:
        """Number of bytes available in input buffer."""
        return self.serial.in_waiting

    def __enter__(self) -> "SerialLink":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
