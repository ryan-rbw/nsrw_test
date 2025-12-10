"""
ICD field definitions and fixed-point encoding/decoding.

Implements HOST_SPEC_RPi.md section 16: NSP and ICD Mapping.
Provides UQ (unsigned) and Q (signed) fixed-point format conversions.
"""

from dataclasses import dataclass
from enum import Enum


class FieldType(Enum):
    """ICD field data types."""

    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    FLOAT32 = "float32"
    UQ16_16 = "uq16_16"  # Unsigned 16.16 fixed-point
    Q15_16 = "q15_16"  # Signed 15.16 fixed-point
    UQ8_8 = "uq8_8"  # Unsigned 8.8 fixed-point
    Q7_8 = "q7_8"  # Signed 7.8 fixed-point
    UQ14_18 = "uq14_18"  # Unsigned 14.18 fixed-point (for RPM)
    UQ18_14 = "uq18_14"  # Unsigned 18.14 fixed-point (for torque/current/power)
    # Production protocol Q-formats (signed, per NRWA-T6 ICD)
    Q14_18 = "q14_18"  # Signed 14.18 fixed-point (speed/current setpoint)
    Q10_22 = "q10_22"  # Signed 10.22 fixed-point (torque setpoint)
    Q24_8 = "q24_8"  # Signed 24.8 fixed-point (telemetry speed)
    Q20_12 = "q20_12"  # Signed 20.12 fixed-point (telemetry current)
    Q14_2 = "q14_2"  # Signed 14.2 fixed-point (current target)
    UQ24_8 = "uq24_8"  # Unsigned 24.8 fixed-point (overspeed threshold)


@dataclass
class FieldDef:
    """
    ICD field definition.

    Attributes:
        name: Field name.
        type: Field data type.
        offset: Byte offset in structure.
        units: Physical units (e.g., "RPM", "A", "V").
        scale: Scaling factor for engineering units.
        min_val: Minimum valid value.
        max_val: Maximum valid value.
        description: Field description.
    """

    name: str
    type: FieldType
    offset: int
    units: str = ""
    scale: float = 1.0
    min_val: float = 0.0
    max_val: float = 0.0
    description: str = ""


def encode_uq16_16(value: float) -> int:
    """
    Encode float to UQ16.16 unsigned fixed-point.

    Args:
        value: Floating-point value (0.0 to 65535.9999).

    Returns:
        32-bit unsigned integer representation.
    """
    value = max(0.0, min(65535.9999, value))  # Clamp
    return int(value * (1 << 16)) & 0xFFFFFFFF


def decode_uq16_16(raw: int) -> float:
    """
    Decode UQ16.16 unsigned fixed-point to float.

    Args:
        raw: 32-bit unsigned integer.

    Returns:
        Floating-point value.
    """
    return (raw & 0xFFFFFFFF) / (1 << 16)


def encode_q15_16(value: float) -> int:
    """
    Encode float to Q15.16 signed fixed-point.

    Args:
        value: Floating-point value (-32768.0 to 32767.9999).

    Returns:
        32-bit signed integer representation.
    """
    value = max(-32768.0, min(32767.9999, value))  # Clamp
    raw = int(value * (1 << 16))
    if raw < 0:
        raw = (1 << 32) + raw  # Two's complement
    return raw & 0xFFFFFFFF


def decode_q15_16(raw: int) -> float:
    """
    Decode Q15.16 signed fixed-point to float.

    Args:
        raw: 32-bit integer.

    Returns:
        Floating-point value.
    """
    # Handle two's complement
    if raw & 0x80000000:
        raw = raw - (1 << 32)
    return raw / (1 << 16)


def encode_uq8_8(value: float) -> int:
    """
    Encode float to UQ8.8 unsigned fixed-point.

    Args:
        value: Floating-point value (0.0 to 255.9961).

    Returns:
        16-bit unsigned integer representation.
    """
    value = max(0.0, min(255.9961, value))  # Clamp
    return int(value * (1 << 8)) & 0xFFFF


def decode_uq8_8(raw: int) -> float:
    """
    Decode UQ8.8 unsigned fixed-point to float.

    Args:
        raw: 16-bit unsigned integer.

    Returns:
        Floating-point value.
    """
    return (raw & 0xFFFF) / (1 << 8)


def encode_q7_8(value: float) -> int:
    """
    Encode float to Q7.8 signed fixed-point.

    Args:
        value: Floating-point value (-128.0 to 127.9961).

    Returns:
        16-bit signed integer representation.
    """
    value = max(-128.0, min(127.9961, value))  # Clamp
    raw = int(value * (1 << 8))
    if raw < 0:
        raw = (1 << 16) + raw  # Two's complement
    return raw & 0xFFFF


def decode_q7_8(raw: int) -> float:
    """
    Decode Q7.8 signed fixed-point to float.

    Args:
        raw: 16-bit integer.

    Returns:
        Floating-point value.
    """
    # Handle two's complement
    if raw & 0x8000:
        raw = raw - (1 << 16)
    return raw / (1 << 8)


def encode_uq14_18(value: float) -> int:
    """
    Encode float to UQ14.18 unsigned fixed-point.

    Args:
        value: Floating-point value (0.0 to 16383.999996).

    Returns:
        32-bit unsigned integer representation.
    """
    value = max(0.0, min(16383.999996, value))  # Clamp
    return int(value * (1 << 18)) & 0xFFFFFFFF


def decode_uq14_18(raw: int) -> float:
    """
    Decode UQ14.18 unsigned fixed-point to float.

    Args:
        raw: 32-bit unsigned integer.

    Returns:
        Floating-point value.
    """
    return (raw & 0xFFFFFFFF) / (1 << 18)


def encode_uq18_14(value: float) -> int:
    """
    Encode float to UQ18.14 unsigned fixed-point.

    Args:
        value: Floating-point value (0.0 to 262143.99994).

    Returns:
        32-bit unsigned integer representation.
    """
    value = max(0.0, min(262143.99994, value))  # Clamp
    return int(value * (1 << 14)) & 0xFFFFFFFF


def decode_uq18_14(raw: int) -> float:
    """
    Decode UQ18.14 unsigned fixed-point to float.

    Args:
        raw: 32-bit unsigned integer.

    Returns:
        Floating-point value.
    """
    return (raw & 0xFFFFFFFF) / (1 << 14)


# =============================================================================
# Production Protocol Q-Formats (Signed, per NRWA-T6 ICD and production code)
# =============================================================================


def encode_q14_18(value: float) -> int:
    """
    Encode float to Q14.18 signed fixed-point.

    Used for CURRENT and SPEED mode setpoints (mA or RPM).
    Per production code: cmd->setpoint = static_cast<int32_t>(setpoint * (1L << 18))

    Args:
        value: Floating-point value (approximately -8192 to +8191.999996).

    Returns:
        32-bit signed integer representation (as unsigned for wire format).
    """
    value = max(-8192.0, min(8191.999996, value))  # Clamp
    raw = int(value * (1 << 18))
    if raw < 0:
        raw = (1 << 32) + raw  # Two's complement
    return raw & 0xFFFFFFFF


def decode_q14_18(raw: int) -> float:
    """
    Decode Q14.18 signed fixed-point to float.

    Args:
        raw: 32-bit integer (as unsigned).

    Returns:
        Floating-point value.
    """
    if raw & 0x80000000:
        raw = raw - (1 << 32)
    return raw / (1 << 18)


def encode_q10_22(value: float) -> int:
    """
    Encode float to Q10.22 signed fixed-point.

    Used for TORQUE mode setpoint (mN-m).
    Per production code: cmd->setpoint = static_cast<int32_t>(setpoint * (1L << 22))

    Args:
        value: Floating-point value (approximately -512 to +511.999999).

    Returns:
        32-bit signed integer representation (as unsigned for wire format).
    """
    value = max(-512.0, min(511.999999, value))  # Clamp
    raw = int(value * (1 << 22))
    if raw < 0:
        raw = (1 << 32) + raw  # Two's complement
    return raw & 0xFFFFFFFF


def decode_q10_22(raw: int) -> float:
    """
    Decode Q10.22 signed fixed-point to float.

    Args:
        raw: 32-bit integer (as unsigned).

    Returns:
        Floating-point value.
    """
    if raw & 0x80000000:
        raw = raw - (1 << 32)
    return raw / (1 << 22)


def decode_q24_8(raw: int) -> float:
    """
    Decode Q24.8 signed fixed-point to float.

    Used for telemetry speed (RPM).
    Per production code: PackedQ<int32_t, 8> speed

    Args:
        raw: 32-bit integer (as unsigned).

    Returns:
        Floating-point value (RPM).
    """
    if raw & 0x80000000:
        raw = raw - (1 << 32)
    return raw / (1 << 8)


def decode_q20_12(raw: int) -> float:
    """
    Decode Q20.12 signed fixed-point to float.

    Used for telemetry current (mA).
    Per production code: PackedQ<int32_t, 12> current

    Args:
        raw: 32-bit integer (as unsigned).

    Returns:
        Floating-point value (mA).
    """
    if raw & 0x80000000:
        raw = raw - (1 << 32)
    return raw / (1 << 12)


def decode_q14_2(raw: int) -> float:
    """
    Decode Q14.2 signed fixed-point to float.

    Used for telemetry current_target (mA).
    Per production code: PackedQ<int16_t, 2> current_target

    Args:
        raw: 16-bit integer (as unsigned).

    Returns:
        Floating-point value (mA).
    """
    if raw & 0x8000:
        raw = raw - (1 << 16)
    return raw / (1 << 2)


def encode_uq24_8(value: float) -> int:
    """
    Encode float to UQ24.8 unsigned fixed-point.

    Used for overspeed fault threshold (RPM).
    Per production code: address 0x06, format UQ24.8

    Args:
        value: Floating-point value (0.0 to 16777215.996).

    Returns:
        32-bit unsigned integer representation.
    """
    value = max(0.0, min(16777215.996, value))  # Clamp
    return int(value * (1 << 8)) & 0xFFFFFFFF


def decode_uq24_8(raw: int) -> float:
    """
    Decode UQ24.8 unsigned fixed-point to float.

    Args:
        raw: 32-bit unsigned integer.

    Returns:
        Floating-point value.
    """
    return (raw & 0xFFFFFFFF) / (1 << 8)


def encode_field(value: int | float, field_type: FieldType) -> bytes:
    """
    Encode field value to bytes.

    Args:
        value: Field value.
        field_type: Field data type.

    Returns:
        Encoded bytes (little-endian).
    """
    if field_type == FieldType.UINT8:
        return int(value).to_bytes(1, "little", signed=False)
    elif field_type == FieldType.UINT16:
        return int(value).to_bytes(2, "little", signed=False)
    elif field_type == FieldType.UINT32:
        return int(value).to_bytes(4, "little", signed=False)
    elif field_type == FieldType.INT8:
        return int(value).to_bytes(1, "little", signed=True)
    elif field_type == FieldType.INT16:
        return int(value).to_bytes(2, "little", signed=True)
    elif field_type == FieldType.INT32:
        return int(value).to_bytes(4, "little", signed=True)
    elif field_type == FieldType.UQ16_16:
        return encode_uq16_16(float(value)).to_bytes(4, "little", signed=False)
    elif field_type == FieldType.Q15_16:
        return encode_q15_16(float(value)).to_bytes(4, "little", signed=False)
    elif field_type == FieldType.UQ8_8:
        return encode_uq8_8(float(value)).to_bytes(2, "little", signed=False)
    elif field_type == FieldType.Q7_8:
        return encode_q7_8(float(value)).to_bytes(2, "little", signed=False)
    else:
        raise ValueError(f"Unsupported field type: {field_type}")


def decode_field(data: bytes, field_type: FieldType, byte_order: str = "little") -> int | float:
    """
    Decode field value from bytes.

    Args:
        data: Encoded bytes.
        field_type: Field data type.
        byte_order: "big" or "little" (default: "little" per NRWA-T6 ICD).

    Returns:
        Decoded value.
    """
    if field_type == FieldType.UINT8:
        return int.from_bytes(data[:1], byte_order, signed=False)
    elif field_type == FieldType.UINT16:
        return int.from_bytes(data[:2], byte_order, signed=False)
    elif field_type == FieldType.UINT32:
        return int.from_bytes(data[:4], byte_order, signed=False)
    elif field_type == FieldType.INT8:
        return int.from_bytes(data[:1], byte_order, signed=True)
    elif field_type == FieldType.INT16:
        return int.from_bytes(data[:2], byte_order, signed=True)
    elif field_type == FieldType.INT32:
        return int.from_bytes(data[:4], byte_order, signed=True)
    elif field_type == FieldType.UQ16_16:
        raw = int.from_bytes(data[:4], byte_order, signed=False)
        return decode_uq16_16(raw)
    elif field_type == FieldType.Q15_16:
        raw = int.from_bytes(data[:4], byte_order, signed=False)
        return decode_q15_16(raw)
    elif field_type == FieldType.UQ8_8:
        raw = int.from_bytes(data[:2], byte_order, signed=False)
        return decode_uq8_8(raw)
    elif field_type == FieldType.Q7_8:
        raw = int.from_bytes(data[:2], byte_order, signed=False)
        return decode_q7_8(raw)
    elif field_type == FieldType.UQ14_18:
        raw = int.from_bytes(data[:4], byte_order, signed=False)
        return decode_uq14_18(raw)
    elif field_type == FieldType.UQ18_14:
        raw = int.from_bytes(data[:4], byte_order, signed=False)
        return decode_uq18_14(raw)
    # Production protocol Q-formats
    elif field_type == FieldType.Q14_18:
        raw = int.from_bytes(data[:4], byte_order, signed=False)
        return decode_q14_18(raw)
    elif field_type == FieldType.Q10_22:
        raw = int.from_bytes(data[:4], byte_order, signed=False)
        return decode_q10_22(raw)
    elif field_type == FieldType.Q24_8:
        raw = int.from_bytes(data[:4], byte_order, signed=False)
        return decode_q24_8(raw)
    elif field_type == FieldType.Q20_12:
        raw = int.from_bytes(data[:4], byte_order, signed=False)
        return decode_q20_12(raw)
    elif field_type == FieldType.Q14_2:
        raw = int.from_bytes(data[:2], byte_order, signed=False)
        return decode_q14_2(raw)
    elif field_type == FieldType.UQ24_8:
        raw = int.from_bytes(data[:4], byte_order, signed=False)
        return decode_uq24_8(raw)
    else:
        raise ValueError(f"Unsupported field type: {field_type}")
