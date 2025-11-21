"""
Unit tests for CRC-CCITT implementation.

Tests HOST_SPEC_RPi.md section 5: Protocol Details (CRC).
"""

from nss_host import crc_ccitt


class TestCrcCcitt:
    """Test CRC-CCITT calculation and verification."""

    def test_crc_empty(self):
        """Test CRC of empty data."""
        crc = crc_ccitt.crc_ccitt(b"")
        assert crc == 0xFFFF

    def test_crc_single_byte(self):
        """Test CRC of single byte."""
        crc = crc_ccitt.crc_ccitt(b"\x00")
        assert crc != 0xFFFF

    def test_crc_known_vectors(self):
        """Test CRC with known test vectors."""
        # Golden test vectors (add actual vectors from ICD)
        vectors = [
            (b"\x01\x02\x03\x04", None),  # TODO: Add expected CRC
            (b"Hello", None),  # TODO: Add expected CRC
        ]

        for data, expected in vectors:
            crc = crc_ccitt.crc_ccitt(data)
            if expected is not None:
                assert crc == expected

    def test_append_crc(self):
        """Test appending CRC to data (LSB first)."""
        data = b"\x01\x02\x03\x04"
        with_crc = crc_ccitt.append_crc(data)

        # Check length
        assert len(with_crc) == len(data) + 2

        # Check data unchanged
        assert with_crc[:-2] == data

    def test_verify_crc_valid(self):
        """Test verification of valid CRC."""
        data = b"\x01\x02\x03\x04"
        with_crc = crc_ccitt.append_crc(data)

        assert crc_ccitt.verify_crc(with_crc) is True

    def test_verify_crc_invalid(self):
        """Test verification of invalid CRC."""
        data = b"\x01\x02\x03\x04"
        with_crc = crc_ccitt.append_crc(data)

        # Corrupt CRC
        corrupted = bytearray(with_crc)
        corrupted[-1] ^= 0xFF
        corrupted = bytes(corrupted)

        assert crc_ccitt.verify_crc(corrupted) is False

    def test_verify_crc_too_short(self):
        """Test verification with insufficient data."""
        assert crc_ccitt.verify_crc(b"\x01") is False
        assert crc_ccitt.verify_crc(b"") is False

    def test_strip_crc(self):
        """Test stripping CRC from data."""
        data = b"\x01\x02\x03\x04"
        with_crc = crc_ccitt.append_crc(data)
        stripped = crc_ccitt.strip_crc(with_crc)

        assert stripped == data

    def test_roundtrip(self):
        """Test append + verify + strip roundtrip."""
        data = b"Test data for CRC roundtrip"

        # Append CRC
        with_crc = crc_ccitt.append_crc(data)

        # Verify
        assert crc_ccitt.verify_crc(with_crc) is True

        # Strip
        stripped = crc_ccitt.strip_crc(with_crc)
        assert stripped == data
