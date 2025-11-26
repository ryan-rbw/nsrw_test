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
    STANDARD telemetry block (Block ID 0x00).

    Contains primary dynamics and status fields per emulator implementation.
    Total size: 38 bytes, big-endian encoding.
    """

    status_register: int  # Operational state (0x00000001 = Operational)
    fault_status: int  # Active faults bitmask
    fault_latch: int  # Latched faults bitmask
    warning_status: int  # Active warnings bitmask
    mode: int  # Control mode (0=CURRENT, 1=SPEED, 2=TORQUE, 3=PWM)
    direction: int  # Direction (0=POSITIVE, 1=NEGATIVE)
    speed_rpm: float  # Angular velocity (RPM)
    current_a: float  # Motor current (A, converted from mA)
    torque_nm: float  # Output torque (Nm, converted from mNm)
    power_w: float  # Motor power (W, converted from mW)
    momentum: float  # Angular momentum (converted from µNm·s)

    @classmethod
    def from_bytes(cls, data: bytes) -> "StandardTelemetry":
        """
        Decode STANDARD telemetry from bytes.

        Args:
            data: Raw telemetry block (38 bytes, big-endian).

        Returns:
            Decoded StandardTelemetry.

        Format per emulator:
            [0-3]   Status Register (uint32)
            [4-7]   Fault Status (uint32)
            [8-11]  Fault Latch (uint32)
            [12-15] Warning Status (uint32)
            [16]    Control Mode (uint8)
            [17]    Direction (uint8)
            [18-21] Speed (UQ14.18 RPM)
            [22-25] Current (UQ18.14 mA)
            [26-29] Torque (UQ18.14 mNm)
            [30-33] Power (UQ18.14 mW)
            [34-37] Momentum (UQ18.14 µNm·s)
        """
        if len(data) < 38:
            raise ValueError(f"STANDARD telemetry requires 38 bytes, got {len(data)}")

        # Decode with big-endian byte order
        return cls(
            status_register=decode_field(data[0:4], FieldType.UINT32),
            fault_status=decode_field(data[4:8], FieldType.UINT32),
            fault_latch=decode_field(data[8:12], FieldType.UINT32),
            warning_status=decode_field(data[12:16], FieldType.UINT32),
            mode=decode_field(data[16:17], FieldType.UINT8),
            direction=decode_field(data[17:18], FieldType.UINT8),
            speed_rpm=decode_field(data[18:22], FieldType.UQ14_18),
            current_a=decode_field(data[22:26], FieldType.UQ18_14) / 1000.0,  # mA to A
            torque_nm=decode_field(data[26:30], FieldType.UQ18_14) / 1000.0,  # mNm to Nm
            power_w=decode_field(data[30:34], FieldType.UQ18_14) / 1000.0,  # mW to W
            momentum=decode_field(data[34:38], FieldType.UQ18_14) / 1e6,  # µNm·s to Nm·s
        )


@dataclass
class TempTelemetry:
    """
    TEMPERATURES telemetry block (Block ID 0x01).

    Contains temperature sensor readings.
    Total size: 6 bytes, big-endian encoding per REGS.md.
    """

    temp_motor_c: float  # Motor temperature (°C)
    temp_driver_c: float  # Driver temperature (°C)
    temp_board_c: float  # Board temperature (°C)

    @classmethod
    def from_bytes(cls, data: bytes) -> "TempTelemetry":
        """
        Decode TEMPERATURES telemetry from bytes.

        Args:
            data: Raw telemetry block (6 bytes, big-endian).

        Returns:
            Decoded TempTelemetry.

        Format per REGS.md:
            [0-1]   Motor Temperature (UQ8.8 °C)
            [2-3]   Driver Temperature (UQ8.8 °C)
            [4-5]   Board Temperature (UQ8.8 °C)
        """
        if len(data) < 6:
            raise ValueError(f"TEMPERATURES telemetry requires 6 bytes, got {len(data)}")

        return cls(
            temp_motor_c=decode_field(data[0:2], FieldType.UQ8_8),
            temp_driver_c=decode_field(data[2:4], FieldType.UQ8_8),
            temp_board_c=decode_field(data[4:6], FieldType.UQ8_8),
        )


@dataclass
class VoltTelemetry:
    """
    VOLTAGES telemetry block (Block ID 0x02).

    Contains voltage rail measurements.
    Total size: 12 bytes, big-endian encoding per REGS.md.
    """

    v_bus: float  # Bus voltage (V)
    v_phase_a: float  # Phase A voltage (V)
    v_phase_b: float  # Phase B voltage (V)

    @classmethod
    def from_bytes(cls, data: bytes) -> "VoltTelemetry":
        """
        Decode VOLTAGES telemetry from bytes.

        Args:
            data: Raw telemetry block (12 bytes, big-endian).

        Returns:
            Decoded VoltTelemetry.

        Format per REGS.md:
            [0-3]   Bus Voltage (UQ16.16 V)
            [4-7]   Phase A Voltage (UQ16.16 V)
            [8-11]  Phase B Voltage (UQ16.16 V)
        """
        if len(data) < 12:
            raise ValueError(f"VOLTAGES telemetry requires 12 bytes, got {len(data)}")

        return cls(
            v_bus=decode_field(data[0:4], FieldType.UQ16_16),
            v_phase_a=decode_field(data[4:8], FieldType.UQ16_16),
            v_phase_b=decode_field(data[8:12], FieldType.UQ16_16),
        )


@dataclass
class CurrTelemetry:
    """
    CURRENTS telemetry block (Block ID 0x03).

    Contains detailed current measurements.
    Total size: 12 bytes, big-endian encoding per REGS.md.
    """

    i_phase_a_ma: float  # Phase A current (mA)
    i_phase_b_ma: float  # Phase B current (mA)
    i_bus_ma: float  # Bus current (mA)

    @classmethod
    def from_bytes(cls, data: bytes) -> "CurrTelemetry":
        """
        Decode CURRENTS telemetry from bytes.

        Args:
            data: Raw telemetry block (12 bytes, big-endian).

        Returns:
            Decoded CurrTelemetry.

        Format per REGS.md:
            [0-3]   Phase A Current (UQ18.14 mA)
            [4-7]   Phase B Current (UQ18.14 mA)
            [8-11]  Bus Current (UQ18.14 mA)
        """
        if len(data) < 12:
            raise ValueError(f"CURRENTS telemetry requires 12 bytes, got {len(data)}")

        return cls(
            i_phase_a_ma=decode_field(data[0:4], FieldType.UQ18_14),
            i_phase_b_ma=decode_field(data[4:8], FieldType.UQ18_14),
            i_bus_ma=decode_field(data[8:12], FieldType.UQ18_14),
        )


@dataclass
class DiagTelemetry:
    """
    DIAGNOSTICS telemetry block (Block ID 0x04).

    Contains diagnostic counters and statistics.
    Total size: 18 bytes, big-endian encoding per REGS.md.
    """

    tick_count: int  # Physics tick counter (100 Hz)
    uptime_s: int  # Uptime in seconds
    fault_count: int  # Total fault events
    command_count: int  # Total commands received
    max_jitter_us: int  # Maximum tick jitter (µs)

    @classmethod
    def from_bytes(cls, data: bytes) -> "DiagTelemetry":
        """
        Decode DIAGNOSTICS telemetry from bytes.

        Args:
            data: Raw telemetry block (18 bytes, big-endian).

        Returns:
            Decoded DiagTelemetry.

        Format per REGS.md:
            [0-3]   Tick Count (uint32)
            [4-7]   Uptime (uint32 seconds)
            [8-11]  Fault Count (uint32)
            [12-15] Command Count (uint32)
            [16-17] Max Jitter (uint16 µs)
        """
        if len(data) < 18:
            raise ValueError(f"DIAGNOSTICS telemetry requires 18 bytes, got {len(data)}")

        return cls(
            tick_count=decode_field(data[0:4], FieldType.UINT32),
            uptime_s=decode_field(data[4:8], FieldType.UINT32),
            fault_count=decode_field(data[8:12], FieldType.UINT32),
            command_count=decode_field(data[12:16], FieldType.UINT32),
            max_jitter_us=decode_field(data[16:18], FieldType.UINT16),
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
