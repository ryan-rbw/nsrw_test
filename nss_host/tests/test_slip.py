"""
Unit tests for SLIP encoder/decoder.

Tests HOST_SPEC_RPi.md section 5: Protocol Details (SLIP).
"""

from nss_host import slip


class TestSlipCodec:
    """Test SLIP encoding and decoding."""

    def test_encode_empty(self):
        """Test encoding empty data."""
        encoded = slip.encode(b"")
        # Should have END delimiters only
        assert encoded == bytes([slip.END, slip.END])

    def test_encode_simple(self):
        """Test encoding simple data without special chars."""
        data = b"\x01\x02\x03\x04"
        encoded = slip.encode(data)

        # Should have END at start and end
        assert encoded[0] == slip.END
        assert encoded[-1] == slip.END

        # Data should be in middle
        assert encoded[1:-1] == data

    def test_encode_with_end(self):
        """Test encoding data containing END character."""
        data = bytes([0x01, slip.END, 0x02])
        encoded = slip.encode(data)

        # END should be escaped as ESC + ESC_END
        assert bytes([slip.ESC, slip.ESC_END]) in encoded

    def test_encode_with_esc(self):
        """Test encoding data containing ESC character."""
        data = bytes([0x01, slip.ESC, 0x02])
        encoded = slip.encode(data)

        # ESC should be escaped as ESC + ESC_ESC
        assert bytes([slip.ESC, slip.ESC_ESC]) in encoded

    def test_decode_simple(self):
        """Test decoding simple frame."""
        data = b"\x01\x02\x03\x04"
        encoded = slip.encode(data)
        decoded = slip.decode(encoded)

        assert len(decoded) == 1
        assert decoded[0] == data

    def test_decode_with_end(self):
        """Test decoding frame with escaped END."""
        data = bytes([0x01, slip.END, 0x02])
        encoded = slip.encode(data)
        decoded = slip.decode(encoded)

        assert len(decoded) == 1
        assert decoded[0] == data

    def test_decode_with_esc(self):
        """Test decoding frame with escaped ESC."""
        data = bytes([0x01, slip.ESC, 0x02])
        encoded = slip.encode(data)
        decoded = slip.decode(encoded)

        assert len(decoded) == 1
        assert decoded[0] == data

    def test_decode_multiple_frames(self):
        """Test decoding multiple concatenated frames."""
        data1 = b"\x01\x02"
        data2 = b"\x03\x04"

        encoded1 = slip.encode(data1)
        encoded2 = slip.encode(data2)
        combined = encoded1 + encoded2

        decoded = slip.decode(combined)

        assert len(decoded) == 2
        assert decoded[0] == data1
        assert decoded[1] == data2

    def test_roundtrip(self):
        """Test encode + decode roundtrip.

        Note: Empty frames are intentionally not tested, as SLIP
        implementations typically skip empty frames (consecutive ENDs).
        NSP protocol doesn't require empty frames since all frames
        contain at least control+CRC (3 bytes minimum).
        """
        test_data = [
            b"\x00",
            b"\x01\x02\x03\x04",
            bytes([slip.END, slip.ESC]),
            bytes(range(256)),
        ]

        for data in test_data:
            encoded = slip.encode(data)
            decoded = slip.decode(encoded)

            assert len(decoded) == 1
            assert decoded[0] == data


class TestSlipDecoder:
    """Test stateful SLIP decoder."""

    def test_decoder_simple(self):
        """Test decoder with complete frame."""
        decoder = slip.SlipDecoder()

        data = b"\x01\x02\x03\x04"
        encoded = slip.encode(data)

        frames = decoder.feed(encoded)

        assert len(frames) == 1
        assert frames[0] == data

    def test_decoder_incremental(self):
        """Test decoder with incremental data feed."""
        decoder = slip.SlipDecoder()

        data = b"\x01\x02\x03\x04"
        encoded = slip.encode(data)

        # Feed one byte at a time
        frames = []
        for byte in encoded:
            result = decoder.feed(bytes([byte]))
            frames.extend(result)

        assert len(frames) == 1
        assert frames[0] == data

    def test_decoder_multiple_feeds(self):
        """Test decoder with multiple feeds."""
        decoder = slip.SlipDecoder()

        data1 = b"\x01\x02"
        data2 = b"\x03\x04"

        frames1 = decoder.feed(slip.encode(data1))
        frames2 = decoder.feed(slip.encode(data2))

        assert len(frames1) == 1
        assert frames1[0] == data1

        assert len(frames2) == 1
        assert frames2[0] == data2

    def test_decoder_reset(self):
        """Test decoder reset."""
        decoder = slip.SlipDecoder()

        # Feed partial frame
        decoder.feed(b"\xc0\x01\x02")

        # Reset
        decoder.reset()

        # Feed complete frame
        data = b"\x03\x04"
        frames = decoder.feed(slip.encode(data))

        assert len(frames) == 1
        assert frames[0] == data

    def test_decoder_split_frame(self):
        """Test decoder with frame split across feeds."""
        decoder = slip.SlipDecoder()

        data = b"\x01\x02\x03\x04"
        encoded = slip.encode(data)

        # Split in middle
        mid = len(encoded) // 2
        part1 = encoded[:mid]
        part2 = encoded[mid:]

        frames1 = decoder.feed(part1)
        frames2 = decoder.feed(part2)

        # First part should not produce complete frame
        assert len(frames1) == 0

        # Second part completes the frame
        assert len(frames2) == 1
        assert frames2[0] == data
