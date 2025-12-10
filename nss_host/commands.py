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
    CurrTelemetry,
    DiagTelemetry,
    StandardTelemetry,
    TelemetryBlock,
    TempTelemetry,
    VoltTelemetry,
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

    def ping(self) -> bytes:
        """
        Send PING command.

        Returns:
            5-byte response: [device_type, serial, version_major, version_minor, version_patch]

        Raises:
            nsp.NspError: On communication error.
        """
        request = nsp.make_request(nsp.NspCommand.PING)
        reply = self._transact(request)
        logger.info(f"PING successful, response={reply.payload.hex()}")
        return reply.payload

    def peek(self, addr: int) -> int:
        """
        Read memory/register (PEEK command).

        Per production code (ns_reaction_wheel.hpp):
            struct PeekCommand { MemoryAddress addr; };  // 1 byte
            struct PeekResponse { Packed<uint32_t> val; };  // 4 bytes LE

        Args:
            addr: Memory address (8-bit).

        Returns:
            32-bit value read (uint32).

        Raises:
            nsp.NspError: On communication error.
        """
        # Build PEEK payload: addr (1 byte)
        payload = bytes([addr & 0xFF])
        request = nsp.make_request(nsp.NspCommand.PEEK, payload)

        reply = self._transact(request)

        if len(reply.payload) < 4:
            raise nsp.NspError(f"PEEK response too short: {len(reply.payload)} bytes")

        value = int.from_bytes(reply.payload[:4], "little", signed=False)
        logger.info(f"PEEK addr=0x{addr:02X} -> 0x{value:08X}")
        return value

    def poke(self, addr: int, value: int) -> None:
        """
        Write memory/register (POKE command).

        Per production code (ns_reaction_wheel.hpp):
            struct PokeCommand {
                MemoryAddress addr;    // 1 byte
                Packed<uint32_t> val;  // 4 bytes LE
            };

        Args:
            addr: Memory address (8-bit).
            value: 32-bit value to write.

        Raises:
            nsp.NspError: On communication error.
        """
        # Build POKE payload: addr (1 byte) + value (4 bytes LE)
        payload = bytes([addr & 0xFF]) + (value & 0xFFFFFFFF).to_bytes(4, "little")
        request = nsp.make_request(nsp.NspCommand.POKE, payload)

        self._transact(request)
        logger.info(f"POKE addr=0x{addr:02X} value=0x{value:08X}")

    def app_telemetry(
        self, block: str | TelemetryBlock | int
    ) -> StandardTelemetry | TempTelemetry | VoltTelemetry | CurrTelemetry | DiagTelemetry:
        """
        Request telemetry block (APP-TM command).

        Args:
            block: Telemetry block name, enum, or ID (0x00-0x04 supported).

        Returns:
            Decoded telemetry object for the requested block type.

        Raises:
            nsp.NspError: On communication error.
            ValueError: If block ID is unknown.

        Note:
            Supported blocks: 0x00=STANDARD, 0x01=TEMPERATURES,
            0x02=VOLTAGES, 0x03=CURRENTS, 0x04=DIAGNOSTICS
        """
        # Convert block to TelemetryBlock enum
        if isinstance(block, str):
            block = TelemetryBlock[block.upper()]
        elif isinstance(block, int):
            block = TelemetryBlock(block)

        block_id = block.value
        block_name = block.name

        # Build APP-TM payload: block ID (1 byte)
        payload = bytes([block_id])
        request = nsp.make_request(nsp.NspCommand.APP_TM, payload)

        reply = self._transact(request)
        logger.info(f"APP-TM block={block_name} payload_len={len(reply.payload)}")

        # Decode telemetry based on block type
        decoded = decode_telemetry_block(block, reply.payload)
        if decoded is None:
            raise ValueError(f"Unknown telemetry block: {block_name}")
        return decoded

    def app_command(
        self,
        mode: "nsp.ControlMode | int",
        setpoint: float = 0.0,
    ) -> None:
        """
        Send application command (APP-CMD).

        Per production code (ns_reaction_wheel.hpp):
            struct AppCommand {
                uint8_t control_mode;      // 1 byte
                Packed<int32_t> setpoint;  // 4 bytes LE
            };

        The setpoint encoding depends on mode:
            - CURRENT: Q14.18 (mA)
            - SPEED: Q14.18 (RPM)
            - TORQUE: Q10.22 (mN-m)
            - PWM: signed 9-bit integer (duty cycle)
            - IDLE: 0 (ignored)

        Args:
            mode: Control mode (ControlMode enum or int).
            setpoint: Setpoint in engineering units (mA, RPM, mN-m, or duty cycle).

        Raises:
            nsp.NspError: On communication error.

        Example:
            # Set to 1000 RPM
            session.app_command(ControlMode.SPEED, 1000.0)

            # Set to 50 mN-m torque
            session.app_command(ControlMode.TORQUE, 50.0)

            # Set to idle
            session.app_command(ControlMode.IDLE)
        """
        from nss_host.icd_fields import encode_q10_22, encode_q14_18

        # Get mode value
        mode_val = int(mode) if not isinstance(mode, int) else mode

        # Encode setpoint based on mode
        if mode_val == nsp.ControlMode.CURRENT or mode_val == nsp.ControlMode.SPEED:
            # Q14.18 for mA or RPM
            setpoint_raw = encode_q14_18(setpoint)
        elif mode_val == nsp.ControlMode.TORQUE:
            # Q10.22 for mN-m
            setpoint_raw = encode_q10_22(setpoint)
        elif mode_val == nsp.ControlMode.PWM:
            # Signed 9-bit integer duty cycle
            raw = int(setpoint)
            if raw < 0:
                raw = (1 << 32) + raw  # Two's complement
            setpoint_raw = raw & 0xFFFFFFFF
        else:  # IDLE or unknown
            setpoint_raw = 0

        # Build 5-byte payload: [mode, setpoint_le]
        payload = bytes([mode_val]) + setpoint_raw.to_bytes(4, "little")

        request = nsp.make_request(nsp.NspCommand.APP_CMD, payload)
        self._transact(request)

        mode_name = nsp.ControlMode(mode_val).name if mode_val in [m.value for m in nsp.ControlMode] else f"0x{mode_val:02X}"
        logger.info(f"APP-CMD mode={mode_name} setpoint={setpoint}")

    def clear_fault(self, mask: int = 0xFFFFFFFF) -> None:
        """
        Clear fault bits (CLEAR-FAULT command).

        Per production code (ns_reaction_wheel.hpp):
            struct ClearFaultCommand {
                Packed<Fault::Type> bits_to_clear;  // 4 bytes LE
            };

        Args:
            mask: Fault bits to clear (default: all 0xFFFFFFFF).

        Raises:
            nsp.NspError: On communication error.
        """
        payload = mask.to_bytes(4, "little")
        request = nsp.make_request(nsp.NspCommand.CLEAR_FAULT, payload)
        self._transact(request)
        logger.info(f"CLEAR-FAULT mask=0x{mask:08X}")

    def config_protection(self, protection_bits: int) -> None:
        """
        Configure protection mechanisms (CONFIG-PROT command).

        Per production code (ns_reaction_wheel.hpp):
            struct ConfigureProtectionCommand {
                Packed<Protection::Type> protection;  // 4 bytes LE
            };

        Protection bits (0 = enabled, 1 = disabled):
            Bit 0: Overspeed fault protection
            Bit 1: Overspeed limit during closed-loop
            Bit 2: Motor overcurrent limit
            Bit 3: EDAC scrubbing
            Bit 4: Braking overvoltage load

        Args:
            protection_bits: Protection bitmask.

        Raises:
            nsp.NspError: On communication error.

        Example:
            # Disable overspeed fault protection (bit 0)
            session.config_protection(ProtectionBits.OVERSPEED_FAULT)

            # Enable all protections
            session.config_protection(0x00000000)
        """
        payload = protection_bits.to_bytes(4, "little")
        request = nsp.make_request(nsp.NspCommand.CONFIG_PROT, payload)
        self._transact(request)
        logger.info(f"CONFIG-PROT bits=0x{protection_bits:08X}")

    def __enter__(self) -> "Session":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
