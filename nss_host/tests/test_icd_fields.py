"""
Unit tests for ICD field encoding/decoding.

Tests HOST_SPEC_RPi.md section 16: NSP and ICD Mapping (field codecs).
"""

import pytest

from nss_host import icd_fields


class TestUQ1616:
    """Test UQ16.16 unsigned fixed-point codec."""

    def test_encode_zero(self):
        """Test encoding zero."""
        result = icd_fields.encode_uq16_16(0.0)
        assert result == 0

    def test_encode_one(self):
        """Test encoding 1.0."""
        result = icd_fields.encode_uq16_16(1.0)
        assert result == (1 << 16)

    def test_encode_fractional(self):
        """Test encoding fractional value."""
        result = icd_fields.encode_uq16_16(0.5)
        assert result == (1 << 15)

    def test_encode_large(self):
        """Test encoding large value."""
        result = icd_fields.encode_uq16_16(1000.0)
        assert result == (1000 << 16)

    def test_decode_zero(self):
        """Test decoding zero."""
        result = icd_fields.decode_uq16_16(0)
        assert result == 0.0

    def test_decode_one(self):
        """Test decoding 1.0."""
        result = icd_fields.decode_uq16_16(1 << 16)
        assert result == pytest.approx(1.0)

    def test_decode_fractional(self):
        """Test decoding fractional value."""
        result = icd_fields.decode_uq16_16(1 << 15)
        assert result == pytest.approx(0.5)

    def test_roundtrip(self):
        """Test encode/decode roundtrip."""
        test_values = [0.0, 1.0, 0.5, 100.5, 12345.6789]

        for value in test_values:
            encoded = icd_fields.encode_uq16_16(value)
            decoded = icd_fields.decode_uq16_16(encoded)
            assert decoded == pytest.approx(value, abs=1e-4)


class TestQ1516:
    """Test Q15.16 signed fixed-point codec."""

    def test_encode_zero(self):
        """Test encoding zero."""
        result = icd_fields.encode_q15_16(0.0)
        assert result == 0

    def test_encode_positive(self):
        """Test encoding positive value."""
        result = icd_fields.encode_q15_16(1.0)
        assert result == (1 << 16)

    def test_encode_negative(self):
        """Test encoding negative value."""
        result = icd_fields.encode_q15_16(-1.0)
        # Two's complement
        assert result == ((1 << 32) - (1 << 16))

    def test_decode_zero(self):
        """Test decoding zero."""
        result = icd_fields.decode_q15_16(0)
        assert result == 0.0

    def test_decode_positive(self):
        """Test decoding positive value."""
        result = icd_fields.decode_q15_16(1 << 16)
        assert result == pytest.approx(1.0)

    def test_decode_negative(self):
        """Test decoding negative value."""
        result = icd_fields.decode_q15_16((1 << 32) - (1 << 16))
        assert result == pytest.approx(-1.0)

    def test_roundtrip(self):
        """Test encode/decode roundtrip."""
        test_values = [0.0, 1.0, -1.0, 123.456, -456.789]

        for value in test_values:
            encoded = icd_fields.encode_q15_16(value)
            decoded = icd_fields.decode_q15_16(encoded)
            assert decoded == pytest.approx(value, abs=1e-4)


class TestUQ88:
    """Test UQ8.8 unsigned fixed-point codec."""

    def test_encode_zero(self):
        """Test encoding zero."""
        result = icd_fields.encode_uq8_8(0.0)
        assert result == 0

    def test_encode_one(self):
        """Test encoding 1.0."""
        result = icd_fields.encode_uq8_8(1.0)
        assert result == (1 << 8)

    def test_decode_zero(self):
        """Test decoding zero."""
        result = icd_fields.decode_uq8_8(0)
        assert result == 0.0

    def test_roundtrip(self):
        """Test encode/decode roundtrip."""
        test_values = [0.0, 1.0, 0.5, 100.5, 255.0]

        for value in test_values:
            encoded = icd_fields.encode_uq8_8(value)
            decoded = icd_fields.decode_uq8_8(encoded)
            assert decoded == pytest.approx(value, abs=1e-2)


class TestQ78:
    """Test Q7.8 signed fixed-point codec."""

    def test_encode_zero(self):
        """Test encoding zero."""
        result = icd_fields.encode_q7_8(0.0)
        assert result == 0

    def test_encode_positive(self):
        """Test encoding positive value."""
        result = icd_fields.encode_q7_8(1.0)
        assert result == (1 << 8)

    def test_encode_negative(self):
        """Test encoding negative value."""
        result = icd_fields.encode_q7_8(-1.0)
        assert result == ((1 << 16) - (1 << 8))

    def test_roundtrip(self):
        """Test encode/decode roundtrip."""
        test_values = [0.0, 1.0, -1.0, 50.5, -75.25]

        for value in test_values:
            encoded = icd_fields.encode_q7_8(value)
            decoded = icd_fields.decode_q7_8(encoded)
            assert decoded == pytest.approx(value, abs=1e-2)


class TestFieldEncodeDecode:
    """Test high-level field encoding/decoding."""

    def test_encode_uint16(self):
        """Test encoding UINT16."""
        data = icd_fields.encode_field(1234, icd_fields.FieldType.UINT16)
        assert data == (1234).to_bytes(2, "little")

    def test_decode_uint16(self):
        """Test decoding UINT16."""
        data = (1234).to_bytes(2, "little")
        value = icd_fields.decode_field(data, icd_fields.FieldType.UINT16)
        assert value == 1234

    def test_encode_q15_16(self):
        """Test encoding Q15.16."""
        data = icd_fields.encode_field(123.456, icd_fields.FieldType.Q15_16)
        assert len(data) == 4

    def test_decode_q15_16(self):
        """Test decoding Q15.16."""
        encoded = icd_fields.encode_field(123.456, icd_fields.FieldType.Q15_16)
        decoded = icd_fields.decode_field(encoded, icd_fields.FieldType.Q15_16)
        assert decoded == pytest.approx(123.456, abs=1e-4)

    def test_roundtrip_all_types(self):
        """Test encode/decode roundtrip for all field types."""
        test_cases = [
            (42, icd_fields.FieldType.UINT8),
            (1234, icd_fields.FieldType.UINT16),
            (123456, icd_fields.FieldType.UINT32),
            (-42, icd_fields.FieldType.INT8),
            (-1234, icd_fields.FieldType.INT16),
            (-123456, icd_fields.FieldType.INT32),
            (123.456, icd_fields.FieldType.UQ16_16),
            (-123.456, icd_fields.FieldType.Q15_16),
            (12.34, icd_fields.FieldType.UQ8_8),
            (-12.34, icd_fields.FieldType.Q7_8),
        ]

        for value, field_type in test_cases:
            encoded = icd_fields.encode_field(value, field_type)
            decoded = icd_fields.decode_field(encoded, field_type)

            if isinstance(value, int):
                assert decoded == value
            else:
                assert decoded == pytest.approx(value, abs=1e-2)
