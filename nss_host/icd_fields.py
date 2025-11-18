"""
ICD field definitions and fixed-point encoding/decoding.

Implements HOST_SPEC_RPi.md section 16: NSP and ICD Mapping.
Provides UQ (unsigned) and Q (signed) fixed-point format conversions.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Union


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


def encode_field(value: Union[int, float], field_type: FieldType) -> bytes:
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


def decode_field(data: bytes, field_type: FieldType) -> Union[int, float]:
    """
    Decode field value from bytes.

    Args:
        data: Encoded bytes (little-endian).
        field_type: Field data type.

    Returns:
        Decoded value.
    """
    if field_type == FieldType.UINT8:
        return int.from_bytes(data[:1], "little", signed=False)
    elif field_type == FieldType.UINT16:
        return int.from_bytes(data[:2], "little", signed=False)
    elif field_type == FieldType.UINT32:
        return int.from_bytes(data[:4], "little", signed=False)
    elif field_type == FieldType.INT8:
        return int.from_bytes(data[:1], "little", signed=True)
    elif field_type == FieldType.INT16:
        return int.from_bytes(data[:2], "little", signed=True)
    elif field_type == FieldType.INT32:
        return int.from_bytes(data[:4], "little", signed=True)
    elif field_type == FieldType.UQ16_16:
        raw = int.from_bytes(data[:4], "little", signed=False)
        return decode_uq16_16(raw)
    elif field_type == FieldType.Q15_16:
        raw = int.from_bytes(data[:4], "little", signed=False)
        return decode_q15_16(raw)
    elif field_type == FieldType.UQ8_8:
        raw = int.from_bytes(data[:2], "little", signed=False)
        return decode_uq8_8(raw)
    elif field_type == FieldType.Q7_8:
        raw = int.from_bytes(data[:2], "little", signed=False)
        return decode_q7_8(raw)
    else:
        raise ValueError(f"Unsupported field type: {field_type}")
