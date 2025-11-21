"""
High-level command API for NSS Host.

Implements HOST_SPEC_RPi.md section 6: High-Level Python API.
Provides Session class for managing NSP communication with the emulator.
"""

import logging
import time

from nss_host import crc_ccitt, nsp, slip
from nss_host.serial_link import SerialLink
from nss_host.telemetry import (
    StandardTelemetry,
    TelemetryBlock,
    decode_telemetry_block,
)

logger = logging.getLogger(__name__)


class Session:
    """
    NSP session for communicating with reaction wheel emulator.

    Handles SLIP framing, CRC, NSP protocol, retries, and logging.
    """

    def __init__(
        self,
        link: SerialLink,
        timeout_ms: int = 10,
        retries: int = 2,
    ):
        """
        Initialize session.

        Args:
            link: Serial link instance.
            timeout_ms: Reply timeout in milliseconds.
            retries: Number of retries on error.
        """
        self.link = link
        self.timeout_ms = timeout_ms
        self.retries = retries
        self.slip_decoder = slip.SlipDecoder()

        # Statistics
        self.stats = {
            "frames_tx": 0,
            "frames_rx": 0,
            "crc_errors": 0,
            "slip_errors": 0,
            "timeouts": 0,
            "nacks": 0,
        }

    def close(self) -> None:
        """Close session and serial link."""
        self.link.close()

    @classmethod
    def open(
        cls,
        port: str,
        baud: int = 460800,
        rs485: dict | None = None,
        timeout_ms: int = 10,
        retries: int = 2,
    ) -> "Session":
        """
        Open a new session.

        Args:
            port: Serial port device.
            baud: Baud rate.
            rs485: RS-485 GPIO configuration (dict with 'de', 'nre' keys).
            timeout_ms: Reply timeout in milliseconds.
            retries: Number of retries on error.

        Returns:
            Opened Session instance.
        """
        de_gpio = rs485.get("de") if rs485 else None
        nre_gpio = rs485.get("nre") if rs485 else None

        link = SerialLink(
            port=port,
            baud=baud,
            timeout=timeout_ms / 1000.0,
            de_gpio=de_gpio,
            nre_gpio=nre_gpio,
        )

        return cls(link, timeout_ms, retries)

    def _send_frame(self, frame: nsp.NspFrame) -> None:
        """
        Send NSP frame with SLIP encoding and CRC.

        Args:
            frame: NSP frame to send.
        """
        # Build frame: NSP + CRC + SLIP
        nsp_bytes = frame.to_bytes()
        with_crc = crc_ccitt.append_crc(nsp_bytes)
        slip_encoded = slip.encode(with_crc)

        # Send
        self.link.write(slip_encoded)
        self.stats["frames_tx"] += 1

        logger.debug(f"TX: {nsp_bytes.hex()} (CRC: {with_crc[-2:].hex()})")

    def _receive_frame(self, timeout_s: float) -> nsp.NspFrame | None:
        """
        Receive NSP frame with SLIP decoding and CRC verification.

        Args:
            timeout_s: Timeout in seconds.

        Returns:
            Received NSP frame, or None on timeout.

        Raises:
            nsp.NspCrcError: If CRC check fails.
        """
        start_time = time.time()

        while time.time() - start_time < timeout_s:
            # Read available data
            data = self.link.read_available()
            if len(data) > 0:
                # Feed to SLIP decoder
                frames = self.slip_decoder.feed(data)

                for frame_data in frames:
                    # Verify CRC
                    if not crc_ccitt.verify_crc(frame_data):
                        self.stats["crc_errors"] += 1
                        logger.warning(f"RX: CRC error on frame: {frame_data.hex()}")
                        raise nsp.NspCrcError()

                    # Strip CRC and parse NSP
                    nsp_bytes = crc_ccitt.strip_crc(frame_data)
                    nsp_frame = nsp.NspFrame.from_bytes(nsp_bytes)

                    self.stats["frames_rx"] += 1
                    logger.debug(f"RX: {nsp_bytes.hex()}")

                    return nsp_frame

            # Small sleep to avoid busy-waiting
            time.sleep(0.001)

        # Timeout
        self.stats["timeouts"] += 1
        return None

    def _transact(self, request: nsp.NspFrame) -> nsp.NspFrame:
        """
        Send request and receive reply with retries.

        Args:
            request: Request frame.

        Returns:
            Reply frame.

        Raises:
            nsp.NspTimeoutError: If no reply received after retries.
            nsp.NspNackError: If NACK received.
            nsp.NspError: On other protocol errors.
        """
        for attempt in range(self.retries + 1):
            try:
                # Flush input buffer
                self.link.flush_input()

                # Send request
                self._send_frame(request)

                # Wait for reply
                reply = self._receive_frame(self.timeout_ms / 1000.0)

                if reply is None:
                    if attempt < self.retries:
                        logger.debug(f"Timeout, retrying ({attempt + 1}/{self.retries})...")
                        continue
                    else:
                        raise nsp.NspTimeoutError(request.command)

                # Validate reply
                nsp.validate_reply(request, reply)

                return reply

            except nsp.NspCrcError:
                if attempt < self.retries:
                    logger.debug(f"CRC error, retrying ({attempt + 1}/{self.retries})...")
                    continue
                else:
                    raise

            except nsp.NspNackError as e:
                self.stats["nacks"] += 1
                raise e

        # Should not reach here
        raise nsp.NspTimeoutError(request.command)

    def ping(self) -> None:
        """
        Send PING command.

        Raises:
            nsp.NspError: On communication error.
        """
        request = nsp.make_request(nsp.NspCommand.PING)
        self._transact(request)
        logger.info("PING successful")

    def peek(self, addr: int, length: int) -> bytes:
        """
        Read memory/registers (PEEK command).

        Args:
            addr: Start address (16-bit, must be 4-byte aligned).
            length: Number of bytes to read (8-bit count).

        Returns:
            Read data.

        Raises:
            nsp.NspError: On communication error.

        Note:
            Format per emulator: [Addr_H, Addr_L, Count]
            - Address is 16-bit big-endian
            - Count is 8-bit
            - Address must be 4-byte aligned
            - Count must be > 0
            - Address must be <= 0x0500
        """
        # Build PEEK payload: addr (2 bytes big-endian) + count (1 byte)
        payload = addr.to_bytes(2, "big") + bytes([length])
        request = nsp.make_request(nsp.NspCommand.PEEK, payload)

        reply = self._transact(request)
        logger.info(f"PEEK addr=0x{addr:04X} len={length}")

        return reply.payload

    def poke(self, addr: int, data: bytes) -> None:
        """
        Write memory/registers (POKE command).

        Args:
            addr: Start address (16-bit, must be 4-byte aligned).
            data: Data to write (must be multiple of 4 bytes).

        Raises:
            nsp.NspError: On communication error.
            ValueError: If data length is not a multiple of 4 bytes.

        Note:
            Format per emulator: [Addr_H, Addr_L, Count, Data...]
            - Address is 16-bit big-endian
            - Count is number of 4-byte registers (not number of bytes)
            - Data must be a multiple of 4 bytes
            - Cannot write to read-only regions (0x0000-0x00FF, 0x0300-0x03FF)
        """
        # Validate data length is multiple of 4 bytes (register size)
        if len(data) % 4 != 0:
            raise ValueError(f"Data length must be multiple of 4 bytes, got {len(data)}")

        # Count = number of registers (4-byte units)
        num_registers = len(data) // 4

        # Build POKE payload: addr (2 bytes big-endian) + count (1 byte) + data
        payload = addr.to_bytes(2, "big") + bytes([num_registers]) + data
        request = nsp.make_request(nsp.NspCommand.POKE, payload)

        self._transact(request)
        logger.info(f"POKE addr=0x{addr:04X} count={num_registers} ({len(data)} bytes)")

    def app_telemetry(self, block: str | TelemetryBlock | int) -> StandardTelemetry | bytes:
        """
        Request telemetry block (APP-TM command).

        Args:
            block: Telemetry block name, enum, or ID (0x00-0x04 supported).

        Returns:
            Decoded telemetry object for STANDARD, or raw bytes for others.

        Raises:
            nsp.NspError: On communication error.

        Note:
            Supported blocks: 0x00=STANDARD, 0x01=TEMPERATURES,
            0x02=VOLTAGES, 0x03=CURRENTS, 0x04=DIAGNOSTICS
        """
        # Convert block to ID
        if isinstance(block, str):
            block = TelemetryBlock[block.upper()]

        if isinstance(block, TelemetryBlock):
            block_id = block.value
            block_name = block.name
        else:
            block_id = block
            block_name = f"0x{block:02X}"

        # Build APP-TM payload: block ID (1 byte)
        payload = bytes([block_id])
        request = nsp.make_request(nsp.NspCommand.APP_TM, payload)

        reply = self._transact(request)
        logger.info(f"APP-TM block={block_name}")

        # Decode telemetry if STANDARD block
        if block_id == 0x00 or (isinstance(block, TelemetryBlock) and block == TelemetryBlock.STANDARD):
            return decode_telemetry_block(TelemetryBlock.STANDARD, reply.payload)
        else:
            # Return raw payload for other blocks
            return reply.payload

    def app_command(self, mode: str | None = None, setpoint_rpm: float | None = None) -> None:
        """
        Send application command (APP-CMD).

        Args:
            mode: Operating mode ('OFF', 'SPEED', 'CURRENT', 'TORQUE').
            setpoint_rpm: Speed setpoint in RPM (for SPEED mode).

        Raises:
            nsp.NspError: On communication error.
        """
        # Build APP-CMD payload (simplified, needs proper implementation)
        payload = bytearray()

        if mode is not None:
            mode_map = {"OFF": 0, "SPEED": 1, "CURRENT": 2, "TORQUE": 3}
            payload.append(mode_map.get(mode.upper(), 0))
        else:
            payload.append(0xFF)  # No change

        if setpoint_rpm is not None:
            from nss_host.icd_fields import FieldType, encode_field

            payload.extend(encode_field(setpoint_rpm, FieldType.Q15_16))

        request = nsp.make_request(nsp.NspCommand.APP_CMD, bytes(payload))
        self._transact(request)
        logger.info(f"APP-CMD mode={mode} setpoint_rpm={setpoint_rpm}")

    def clear_fault(self, mask: int = 0xFFFFFFFF) -> None:
        """
        Clear fault bits (CLEAR-FAULT command).

        Args:
            mask: Fault bits to clear (default: all).

        Raises:
            nsp.NspError: On communication error.
        """
        payload = mask.to_bytes(4, "little")
        request = nsp.make_request(nsp.NspCommand.CLEAR_FAULT, payload)
        self._transact(request)
        logger.info(f"CLEAR-FAULT mask=0x{mask:08X}")

    def config_protection(
        self,
        overspeed_limit_rpm: float | None = None,
        overcurrent_limit_a: float | None = None,
    ) -> None:
        """
        Configure protection thresholds (CONFIG-PROT command).

        Args:
            overspeed_limit_rpm: Overspeed trip threshold (RPM).
            overcurrent_limit_a: Overcurrent trip threshold (A).

        Raises:
            nsp.NspError: On communication error.
        """
        from nss_host.icd_fields import FieldType, encode_field

        payload = bytearray()

        if overspeed_limit_rpm is not None:
            payload.extend(encode_field(overspeed_limit_rpm, FieldType.UQ16_16))
        if overcurrent_limit_a is not None:
            payload.extend(encode_field(overcurrent_limit_a, FieldType.UQ16_16))

        request = nsp.make_request(nsp.NspCommand.CONFIG_PROT, bytes(payload))
        self._transact(request)
        logger.info(
            f"CONFIG-PROT overspeed={overspeed_limit_rpm} overcurrent={overcurrent_limit_a}"
        )

    def __enter__(self) -> "Session":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
