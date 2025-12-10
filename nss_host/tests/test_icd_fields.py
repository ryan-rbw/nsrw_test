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


# =============================================================================
# Production Protocol Q-Format Tests (per NRWA-T6 ICD and ns_reaction_wheel.hpp)
# =============================================================================


class TestQ1418:
    """Test Q14.18 signed fixed-point codec (speed/current setpoint)."""

    def test_encode_zero(self):
        """Test encoding zero."""
        result = icd_fields.encode_q14_18(0.0)
        assert result == 0

    def test_encode_positive(self):
        """Test encoding positive value (1000 RPM)."""
        result = icd_fields.encode_q14_18(1000.0)
        expected = int(1000.0 * (1 << 18))
        assert result == expected

    def test_encode_negative(self):
        """Test encoding negative value (-500 RPM)."""
        result = icd_fields.encode_q14_18(-500.0)
        # Two's complement for negative
        expected = (1 << 32) + int(-500.0 * (1 << 18))
        assert result == expected

    def test_decode_zero(self):
        """Test decoding zero."""
        result = icd_fields.decode_q14_18(0)
        assert result == 0.0

    def test_decode_positive(self):
        """Test decoding positive value."""
        raw = int(2000.0 * (1 << 18))
        result = icd_fields.decode_q14_18(raw)
        assert result == pytest.approx(2000.0, abs=1e-5)

    def test_decode_negative(self):
        """Test decoding negative value."""
        raw = (1 << 32) + int(-1000.0 * (1 << 18))
        result = icd_fields.decode_q14_18(raw)
        assert result == pytest.approx(-1000.0, abs=1e-5)

    def test_roundtrip(self):
        """Test encode/decode roundtrip for typical RPM values."""
        test_values = [0.0, 100.0, 1000.0, 5000.0, -100.0, -1000.0, -5000.0]

        for value in test_values:
            encoded = icd_fields.encode_q14_18(value)
            decoded = icd_fields.decode_q14_18(encoded)
            assert decoded == pytest.approx(value, abs=1e-5)

    def test_clamp_max(self):
        """Test clamping at maximum value (~8191.999)."""
        result = icd_fields.encode_q14_18(10000.0)
        decoded = icd_fields.decode_q14_18(result)
        assert decoded < 10000.0  # Should be clamped


class TestQ1022:
    """Test Q10.22 signed fixed-point codec (torque setpoint)."""

    def test_encode_zero(self):
        """Test encoding zero."""
        result = icd_fields.encode_q10_22(0.0)
        assert result == 0

    def test_encode_positive(self):
        """Test encoding positive value (50 mN-m)."""
        result = icd_fields.encode_q10_22(50.0)
        expected = int(50.0 * (1 << 22))
        assert result == expected

    def test_encode_negative(self):
        """Test encoding negative value (-50 mN-m)."""
        result = icd_fields.encode_q10_22(-50.0)
        expected = (1 << 32) + int(-50.0 * (1 << 22))
        assert result == expected

    def test_decode_zero(self):
        """Test decoding zero."""
        result = icd_fields.decode_q10_22(0)
        assert result == 0.0

    def test_roundtrip(self):
        """Test encode/decode roundtrip for typical torque values."""
        # ICD max torque: 310 mN-m
        test_values = [0.0, 10.0, 50.0, 100.0, 310.0, -10.0, -50.0, -100.0]

        for value in test_values:
            encoded = icd_fields.encode_q10_22(value)
            decoded = icd_fields.decode_q10_22(encoded)
            assert decoded == pytest.approx(value, abs=1e-6)

    def test_clamp_max(self):
        """Test clamping at maximum value (~511.999)."""
        result = icd_fields.encode_q10_22(600.0)
        decoded = icd_fields.decode_q10_22(result)
        assert decoded < 600.0  # Should be clamped


class TestQ248:
    """Test Q24.8 signed fixed-point codec (telemetry speed)."""

    def test_decode_zero(self):
        """Test decoding zero."""
        result = icd_fields.decode_q24_8(0)
        assert result == 0.0

    def test_decode_positive(self):
        """Test decoding positive value (3000 RPM)."""
        raw = int(3000.0 * (1 << 8))
        result = icd_fields.decode_q24_8(raw)
        assert result == pytest.approx(3000.0, abs=1e-2)

    def test_decode_negative(self):
        """Test decoding negative value (-1500 RPM)."""
        raw = (1 << 32) + int(-1500.0 * (1 << 8))
        result = icd_fields.decode_q24_8(raw)
        assert result == pytest.approx(-1500.0, abs=1e-2)

    def test_decode_max_speed(self):
        """Test decoding max operational speed (5000 RPM per ICD)."""
        raw = int(5000.0 * (1 << 8))
        result = icd_fields.decode_q24_8(raw)
        assert result == pytest.approx(5000.0, abs=1e-2)

    def test_decode_fractional(self):
        """Test decoding fractional RPM."""
        raw = int(1234.5 * (1 << 8))
        result = icd_fields.decode_q24_8(raw)
        assert result == pytest.approx(1234.5, abs=1e-2)


class TestQ2012:
    """Test Q20.12 signed fixed-point codec (telemetry current)."""

    def test_decode_zero(self):
        """Test decoding zero."""
        result = icd_fields.decode_q20_12(0)
        assert result == 0.0

    def test_decode_positive(self):
        """Test decoding positive current (500 mA)."""
        raw = int(500.0 * (1 << 12))
        result = icd_fields.decode_q20_12(raw)
        assert result == pytest.approx(500.0, abs=1e-3)

    def test_decode_negative(self):
        """Test decoding negative current (-200 mA)."""
        raw = (1 << 32) + int(-200.0 * (1 << 12))
        result = icd_fields.decode_q20_12(raw)
        assert result == pytest.approx(-200.0, abs=1e-3)

    def test_decode_fractional(self):
        """Test decoding fractional mA."""
        raw = int(123.456 * (1 << 12))
        result = icd_fields.decode_q20_12(raw)
        assert result == pytest.approx(123.456, abs=1e-3)


class TestQ142:
    """Test Q14.2 signed fixed-point codec (current target)."""

    def test_decode_zero(self):
        """Test decoding zero."""
        result = icd_fields.decode_q14_2(0)
        assert result == 0.0

    def test_decode_positive(self):
        """Test decoding positive value (100 mA)."""
        raw = int(100.0 * (1 << 2))
        result = icd_fields.decode_q14_2(raw)
        assert result == pytest.approx(100.0, abs=0.25)

    def test_decode_negative(self):
        """Test decoding negative value (-50 mA)."""
        raw = (1 << 16) + int(-50.0 * (1 << 2))
        result = icd_fields.decode_q14_2(raw)
        assert result == pytest.approx(-50.0, abs=0.25)

    def test_decode_fractional(self):
        """Test decoding fractional mA (0.25 resolution)."""
        raw = int(25.5 * (1 << 2))  # 25.5 mA = 102 raw
        result = icd_fields.decode_q14_2(raw)
        assert result == pytest.approx(25.5, abs=0.25)


class TestUQ248:
    """Test UQ24.8 unsigned fixed-point codec (overspeed threshold)."""

    def test_encode_zero(self):
        """Test encoding zero."""
        result = icd_fields.encode_uq24_8(0.0)
        assert result == 0

    def test_encode_default_threshold(self):
        """Test encoding default overspeed threshold (6000 RPM per ICD)."""
        result = icd_fields.encode_uq24_8(6000.0)
        expected = int(6000.0 * (1 << 8))
        assert result == expected

    def test_decode_zero(self):
        """Test decoding zero."""
        result = icd_fields.decode_uq24_8(0)
        assert result == 0.0

    def test_decode_threshold(self):
        """Test decoding overspeed threshold."""
        raw = int(6000.0 * (1 << 8))
        result = icd_fields.decode_uq24_8(raw)
        assert result == pytest.approx(6000.0, abs=1e-2)

    def test_roundtrip(self):
        """Test encode/decode roundtrip."""
        test_values = [0.0, 1000.0, 5000.0, 6000.0, 10000.0]

        for value in test_values:
            encoded = icd_fields.encode_uq24_8(value)
            decoded = icd_fields.decode_uq24_8(encoded)
            assert decoded == pytest.approx(value, abs=1e-2)
