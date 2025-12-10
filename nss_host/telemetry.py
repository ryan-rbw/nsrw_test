"""
Telemetry block decoders.

Implements telemetry decoding per NRWA-T6 ICD and production code.
All structures match ns_reaction_wheel.hpp exactly.
"""

from dataclasses import dataclass
from enum import Enum

from nss_host.icd_fields import (
    FieldType,
    decode_field,
    decode_q14_2,
    decode_q20_12,
    decode_q24_8,
)


class TelemetryBlock(Enum):
    """Telemetry block identifiers per NRWA-T6 ICD."""

    STANDARD = 0x00
    TEMP = 0x01
    VOLT = 0x02
    CURR = 0x03
    DIAG_GENERAL = 0x04
    DIAG_EDAC = 0x05
    DIAG_SCIA = 0x06
    DIAG_SCIB = 0x07


@dataclass
class StandardTelemetry:
    """
    STANDARD telemetry block (Block ID 0x00).

    Per production code (ns_reaction_wheel.hpp):
        struct AppTelemStandard {
            Packed<Status::Type> status;         // 4 bytes
            Packed<Fault::Type> fault;           // 4 bytes
            uint8_t control_mode;                // 1 byte
            Packed<int32_t> setpoint;            // 4 bytes
            Packed<int16_t> duty_cycle;          // 2 bytes
            PackedQ<int16_t, 2> current_target;  // 2 bytes (Q14.2 mA)
            PackedQ<int32_t, 12> current;        // 4 bytes (Q20.12 mA)
            PackedQ<int32_t, 8> speed;           // 4 bytes (Q24.8 RPM)
        };
        static_assert(sizeof(AppTelemStandard) == 25);

    Total size: 25 bytes, little-endian encoding.
    """

    status: int  # Status flags (uint32)
    fault: int  # Fault flags (uint32)
    control_mode: int  # Control mode (uint8)
    setpoint: int  # Raw setpoint (int32, Q-format varies by mode)
    duty_cycle: int  # PWM duty cycle (int16)
    current_target_ma: float  # Current target (Q14.2 mA)
    current_ma: float  # Motor current (Q20.12 mA)
    speed_rpm: float  # Motor speed (Q24.8 RPM)

    @property
    def setpoint_decoded(self) -> float:
        """
        Decode setpoint based on control_mode.

        Returns:
            Decoded setpoint in engineering units (mA, RPM, mN-m, or duty cycle).
        """
        from nss_host.icd_fields import decode_q10_22, decode_q14_18
        from nss_host.nsp import ControlMode

        if self.control_mode == ControlMode.CURRENT:
            return decode_q14_18(self.setpoint)  # mA
        elif self.control_mode == ControlMode.SPEED:
            return decode_q14_18(self.setpoint)  # RPM
        elif self.control_mode == ControlMode.TORQUE:
            return decode_q10_22(self.setpoint)  # mN-m
        elif self.control_mode == ControlMode.PWM:
            # Signed 9-bit integer
            if self.setpoint & 0x80000000:
                return float(self.setpoint - (1 << 32))
            return float(self.setpoint)
        return 0.0

    @classmethod
    def from_bytes(cls, data: bytes) -> "StandardTelemetry":
        """
        Decode STANDARD telemetry from bytes.

        Args:
            data: Raw telemetry block (25 bytes, little-endian).

        Returns:
            Decoded StandardTelemetry.
        """
        if len(data) < 25:
            raise ValueError(f"STANDARD telemetry requires 25 bytes, got {len(data)}")

        # All fields are little-endian per production code
        status = int.from_bytes(data[0:4], "little", signed=False)
        fault = int.from_bytes(data[4:8], "little", signed=False)
        control_mode = data[8]
        setpoint = int.from_bytes(data[9:13], "little", signed=True)
        duty_cycle = int.from_bytes(data[13:15], "little", signed=True)
        current_target_raw = int.from_bytes(data[15:17], "little", signed=False)
        current_raw = int.from_bytes(data[17:21], "little", signed=False)
        speed_raw = int.from_bytes(data[21:25], "little", signed=False)

        return cls(
            status=status,
            fault=fault,
            control_mode=control_mode,
            setpoint=setpoint,
            duty_cycle=duty_cycle,
            current_target_ma=decode_q14_2(current_target_raw),
            current_ma=decode_q20_12(current_raw),
            speed_rpm=decode_q24_8(speed_raw),
        )


@dataclass
class TempTelemetry:
    """
    TEMPERATURES telemetry block (Block ID 0x01).

    Per production code (ns_reaction_wheel.hpp):
        struct AppTelemTemperatures {
            Packed<uint16_t> dcdc;       // DC/DC converter temperature (raw ADC)
            Packed<uint16_t> enclosure;  // Enclosure temperature (raw ADC)
            Packed<uint16_t> driver;     // Motor driver temperature (raw ADC)
            Packed<uint16_t> motor;      // Motor temperature (raw ADC)
        };
        static_assert(sizeof(AppTelemTemperatures) == 8);

    Total size: 8 bytes, little-endian encoding.
    Note: Values are raw ADC readings. Use raw_temp_to_celsius() for conversion.
    """

    temp_dcdc_raw: int  # DC/DC converter temperature (raw ADC)
    temp_enclosure_raw: int  # Enclosure temperature (raw ADC)
    temp_driver_raw: int  # Motor driver temperature (raw ADC)
    temp_motor_raw: int  # Motor temperature (raw ADC)

    @classmethod
    def from_bytes(cls, data: bytes) -> "TempTelemetry":
        """
        Decode TEMPERATURES telemetry from bytes.

        Args:
            data: Raw telemetry block (8 bytes, little-endian).

        Returns:
            Decoded TempTelemetry.
        """
        if len(data) < 8:
            raise ValueError(f"TEMPERATURES telemetry requires 8 bytes, got {len(data)}")

        return cls(
            temp_dcdc_raw=int.from_bytes(data[0:2], "little", signed=False),
            temp_enclosure_raw=int.from_bytes(data[2:4], "little", signed=False),
            temp_driver_raw=int.from_bytes(data[4:6], "little", signed=False),
            temp_motor_raw=int.from_bytes(data[6:8], "little", signed=False),
        )


@dataclass
class VoltTelemetry:
    """
    VOLTAGES telemetry block (Block ID 0x02).

    Per production code (ns_reaction_wheel.hpp):
        struct AppTelemVoltages {
            PackedQ<uint32_t, 16> vmon_1v5_v;  // 1.5V rail (UQ16.16 V)
            PackedQ<uint32_t, 16> vmon_3v3_v;  // 3.3V rail (UQ16.16 V)
            PackedQ<uint32_t, 16> vmon_5v_v;   // 5V rail (UQ16.16 V)
            PackedQ<uint32_t, 16> vmon_12v_v;  // 12V rail (UQ16.16 V)
            PackedQ<uint32_t, 16> vmon_30v_v;  // 30V rail (UQ16.16 V)
            PackedQ<uint32_t, 16> vmon_2v5_v;  // 2.5V rail (UQ16.16 V)
        };
        static_assert(sizeof(AppTelemVoltages) == 24);

    Total size: 24 bytes, little-endian encoding.
    """

    v_1v5: float  # 1.5V rail voltage (V)
    v_3v3: float  # 3.3V rail voltage (V)
    v_5v: float  # 5V rail voltage (V)
    v_12v: float  # 12V rail voltage (V)
    v_30v: float  # 30V (drive) rail voltage (V)
    v_2v5: float  # 2.5V rail voltage (V)

    @classmethod
    def from_bytes(cls, data: bytes) -> "VoltTelemetry":
        """
        Decode VOLTAGES telemetry from bytes.

        Args:
            data: Raw telemetry block (24 bytes, little-endian).

        Returns:
            Decoded VoltTelemetry.
        """
        if len(data) < 24:
            raise ValueError(f"VOLTAGES telemetry requires 24 bytes, got {len(data)}")

        return cls(
            v_1v5=decode_field(data[0:4], FieldType.UQ16_16, "little"),
            v_3v3=decode_field(data[4:8], FieldType.UQ16_16, "little"),
            v_5v=decode_field(data[8:12], FieldType.UQ16_16, "little"),
            v_12v=decode_field(data[12:16], FieldType.UQ16_16, "little"),
            v_30v=decode_field(data[16:20], FieldType.UQ16_16, "little"),
            v_2v5=decode_field(data[20:24], FieldType.UQ16_16, "little"),
        )


@dataclass
class CurrTelemetry:
    """
    CURRENTS telemetry block (Block ID 0x03).

    Per production code (ns_reaction_wheel.hpp):
        struct AppTelemCurrents {
            PackedQ<uint32_t, 16> imon_1v5_ma;         // 1.5V rail (UQ16.16 mA)
            PackedQ<uint32_t, 16> imon_3v3_ma;         // 3.3V rail (UQ16.16 mA)
            PackedQ<uint32_t, 16> imon_5v_analog_ma;   // 5V analog rail (UQ16.16 mA)
            PackedQ<uint32_t, 16> imon_5v_digital_ma;  // 5V digital rail (UQ16.16 mA)
            PackedQ<uint32_t, 16> imon_12v_ma;         // 12V rail (UQ16.16 mA)
            PackedQ<uint32_t, 16> imon_30v_a;          // 30V rail (UQ16.16 A)
        };
        static_assert(sizeof(AppTelemCurrents) == 24);

    Total size: 24 bytes, little-endian encoding.
    """

    i_1v5_ma: float  # 1.5V rail current (mA)
    i_3v3_ma: float  # 3.3V rail current (mA)
    i_5v_analog_ma: float  # 5V analog rail current (mA)
    i_5v_digital_ma: float  # 5V digital rail current (mA)
    i_12v_ma: float  # 12V rail current (mA)
    i_30v_a: float  # 30V (drive) rail current (A)

    @classmethod
    def from_bytes(cls, data: bytes) -> "CurrTelemetry":
        """
        Decode CURRENTS telemetry from bytes.

        Args:
            data: Raw telemetry block (24 bytes, little-endian).

        Returns:
            Decoded CurrTelemetry.
        """
        if len(data) < 24:
            raise ValueError(f"CURRENTS telemetry requires 24 bytes, got {len(data)}")

        return cls(
            i_1v5_ma=decode_field(data[0:4], FieldType.UQ16_16, "little"),
            i_3v3_ma=decode_field(data[4:8], FieldType.UQ16_16, "little"),
            i_5v_analog_ma=decode_field(data[8:12], FieldType.UQ16_16, "little"),
            i_5v_digital_ma=decode_field(data[12:16], FieldType.UQ16_16, "little"),
            i_12v_ma=decode_field(data[16:20], FieldType.UQ16_16, "little"),
            i_30v_a=decode_field(data[20:24], FieldType.UQ16_16, "little"),
        )


@dataclass
class DiagGeneralTelemetry:
    """
    DIAGNOSTICS-GENERAL telemetry block (Block ID 0x04).

    Per production code (ns_reaction_wheel.hpp):
        struct AppTelemDiagGeneral {
            PackedQ<uint32_t, 2> uptime_s;          // Uptime (Q30.2 sec)
            Packed<uint32_t> rev_count;             // Revolution count
            Packed<uint32_t> hall_bad_trans_count;  // Hall sensor bad transitions
            Packed<uint32_t> drive_fault_count;     // Drive fault count
            Packed<uint32_t> over_temp_count;       // Over temperature count
        };
        static_assert(sizeof(AppTelemDiagGeneral) == 20);

    Total size: 20 bytes, little-endian encoding.
    """

    uptime_s: float  # Uptime (Q30.2 seconds)
    rev_count: int  # Revolution count
    hall_bad_trans_count: int  # Hall sensor bad transition count
    drive_fault_count: int  # Drive fault count
    over_temp_count: int  # Over temperature count

    @classmethod
    def from_bytes(cls, data: bytes) -> "DiagGeneralTelemetry":
        """
        Decode DIAGNOSTICS-GENERAL telemetry from bytes.

        Args:
            data: Raw telemetry block (20 bytes, little-endian).

        Returns:
            Decoded DiagGeneralTelemetry.
        """
        if len(data) < 20:
            raise ValueError(f"DIAGNOSTICS-GENERAL telemetry requires 20 bytes, got {len(data)}")

        uptime_raw = int.from_bytes(data[0:4], "little", signed=False)
        uptime_s = uptime_raw / (1 << 2)  # Q30.2

        return cls(
            uptime_s=uptime_s,
            rev_count=int.from_bytes(data[4:8], "little", signed=False),
            hall_bad_trans_count=int.from_bytes(data[8:12], "little", signed=False),
            drive_fault_count=int.from_bytes(data[12:16], "little", signed=False),
            over_temp_count=int.from_bytes(data[16:20], "little", signed=False),
        )


# Alias for backward compatibility
DiagTelemetry = DiagGeneralTelemetry


def decode_telemetry_block(
    block_id: TelemetryBlock, data: bytes
) -> StandardTelemetry | TempTelemetry | VoltTelemetry | CurrTelemetry | DiagGeneralTelemetry | None:
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
    elif block_id == TelemetryBlock.DIAG_GENERAL:
        return DiagGeneralTelemetry.from_bytes(data)
    else:
        return None
