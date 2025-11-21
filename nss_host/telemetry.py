"""
Telemetry block decoders.

Implements HOST_SPEC_RPi.md section 16: NSP and ICD Mapping.
Decodes STANDARD, TEMP, VOLT, CURR, and DIAG telemetry blocks.
"""

from dataclasses import dataclass
from enum import Enum

from nss_host.icd_fields import FieldType, decode_field


class TelemetryBlock(Enum):
    """Telemetry block identifiers."""

    STANDARD = 0x00
    TEMP = 0x01
    VOLT = 0x02
    CURR = 0x03
    DIAG = 0x04


@dataclass
class StandardTelemetry:
    """
    STANDARD telemetry block.

    Contains primary dynamics and status fields.
    """

    timestamp_ms: int  # System timestamp (ms)
    mode: int  # Operating mode (0=OFF, 1=SPEED, 2=CURRENT, 3=TORQUE)
    speed_rpm: float  # Wheel speed (RPM)
    current_a: float  # Motor current (A)
    torque_nm: float  # Estimated torque (Nm)
    power_w: float  # Electrical power (W)
    flags: int  # Status flags bitfield
    fault_mask: int  # Active fault mask

    @classmethod
    def from_bytes(cls, data: bytes) -> "StandardTelemetry":
        """
        Decode STANDARD telemetry from bytes.

        Args:
            data: Raw telemetry block (minimum 28 bytes).

        Returns:
            Decoded StandardTelemetry.
        """
        if len(data) < 28:
            raise ValueError(f"STANDARD telemetry requires at least 28 bytes, got {len(data)}")

        return cls(
            timestamp_ms=decode_field(data[0:4], FieldType.UINT32),
            mode=decode_field(data[4:5], FieldType.UINT8),
            speed_rpm=decode_field(data[8:12], FieldType.Q15_16),
            current_a=decode_field(data[12:16], FieldType.Q15_16),
            torque_nm=decode_field(data[16:20], FieldType.Q15_16),
            power_w=decode_field(data[20:24], FieldType.Q15_16),
            flags=decode_field(data[24:26], FieldType.UINT16),
            fault_mask=decode_field(data[26:28], FieldType.UINT16),
        )


@dataclass
class TempTelemetry:
    """
    TEMP telemetry block.

    Contains temperature sensor readings.
    """

    temp_motor_c: float  # Motor temperature (°C)
    temp_electronics_c: float  # Electronics temperature (°C)
    temp_bearing_c: float  # Bearing temperature (°C)

    @classmethod
    def from_bytes(cls, data: bytes) -> "TempTelemetry":
        """
        Decode TEMP telemetry from bytes.

        Args:
            data: Raw telemetry block (minimum 6 bytes).

        Returns:
            Decoded TempTelemetry.
        """
        if len(data) < 6:
            raise ValueError(f"TEMP telemetry requires at least 6 bytes, got {len(data)}")

        return cls(
            temp_motor_c=decode_field(data[0:2], FieldType.Q7_8),
            temp_electronics_c=decode_field(data[2:4], FieldType.Q7_8),
            temp_bearing_c=decode_field(data[4:6], FieldType.Q7_8),
        )


@dataclass
class VoltTelemetry:
    """
    VOLT telemetry block.

    Contains voltage rail measurements.
    """

    v_bus: float  # Bus voltage (V)
    v_3v3: float  # 3.3V rail (V)
    v_5v: float  # 5V rail (V)

    @classmethod
    def from_bytes(cls, data: bytes) -> "VoltTelemetry":
        """
        Decode VOLT telemetry from bytes.

        Args:
            data: Raw telemetry block (minimum 12 bytes).

        Returns:
            Decoded VoltTelemetry.
        """
        if len(data) < 12:
            raise ValueError(f"VOLT telemetry requires at least 12 bytes, got {len(data)}")

        return cls(
            v_bus=decode_field(data[0:4], FieldType.UQ16_16),
            v_3v3=decode_field(data[4:8], FieldType.UQ16_16),
            v_5v=decode_field(data[8:12], FieldType.UQ16_16),
        )


@dataclass
class CurrTelemetry:
    """
    CURR telemetry block.

    Contains detailed current measurements.
    """

    i_motor_a: float  # Motor current (A)
    i_bus_a: float  # Bus current (A)
    i_3v3_ma: float  # 3.3V rail current (mA)

    @classmethod
    def from_bytes(cls, data: bytes) -> "CurrTelemetry":
        """
        Decode CURR telemetry from bytes.

        Args:
            data: Raw telemetry block (minimum 12 bytes).

        Returns:
            Decoded CurrTelemetry.
        """
        if len(data) < 12:
            raise ValueError(f"CURR telemetry requires at least 12 bytes, got {len(data)}")

        return cls(
            i_motor_a=decode_field(data[0:4], FieldType.Q15_16),
            i_bus_a=decode_field(data[4:8], FieldType.Q15_16),
            i_3v3_ma=decode_field(data[8:12], FieldType.UQ16_16),
        )


@dataclass
class DiagTelemetry:
    """
    DIAG telemetry block.

    Contains diagnostic counters and statistics.
    """

    frame_count: int  # Total frame count
    crc_errors: int  # CRC error count
    timeouts: int  # Timeout count
    nacks: int  # NACK count
    resets: int  # Reset count

    @classmethod
    def from_bytes(cls, data: bytes) -> "DiagTelemetry":
        """
        Decode DIAG telemetry from bytes.

        Args:
            data: Raw telemetry block (minimum 20 bytes).

        Returns:
            Decoded DiagTelemetry.
        """
        if len(data) < 20:
            raise ValueError(f"DIAG telemetry requires at least 20 bytes, got {len(data)}")

        return cls(
            frame_count=decode_field(data[0:4], FieldType.UINT32),
            crc_errors=decode_field(data[4:8], FieldType.UINT32),
            timeouts=decode_field(data[8:12], FieldType.UINT32),
            nacks=decode_field(data[12:16], FieldType.UINT32),
            resets=decode_field(data[16:20], FieldType.UINT32),
        )


def decode_telemetry_block(
    block_id: TelemetryBlock, data: bytes
) -> StandardTelemetry | TempTelemetry | VoltTelemetry | CurrTelemetry | DiagTelemetry | None:
    """
    Decode telemetry block by ID.

    Args:
        block_id: Telemetry block identifier.
        data: Raw telemetry data.

    Returns:
        Decoded telemetry object, or None if unknown block ID.
    """
    if block_id == TelemetryBlock.STANDARD:
        return StandardTelemetry.from_bytes(data)
    elif block_id == TelemetryBlock.TEMP:
        return TempTelemetry.from_bytes(data)
    elif block_id == TelemetryBlock.VOLT:
        return VoltTelemetry.from_bytes(data)
    elif block_id == TelemetryBlock.CURR:
        return CurrTelemetry.from_bytes(data)
    elif block_id == TelemetryBlock.DIAG:
        return DiagTelemetry.from_bytes(data)
    else:
        return None
