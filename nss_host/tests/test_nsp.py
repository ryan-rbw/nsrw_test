"""
Unit tests for NSP protocol implementation.

Tests HOST_SPEC_RPi.md section 5: Protocol Details (NSP).
"""

import pytest

from nss_host import nsp


class TestNspFrame:
    """Test NSP frame structure and parsing."""

    def test_frame_creation(self):
        """Test creating NSP frame."""
        frame = nsp.NspFrame(control=0x80, payload=b"\x01\x02\x03")

        assert frame.control == 0x80
        assert frame.payload == b"\x01\x02\x03"

    def test_frame_is_request(self):
        """Test POLL bit detection."""
        request = nsp.NspFrame(control=0x80, payload=b"")
        reply = nsp.NspFrame(control=0x00, payload=b"")

        assert request.is_request is True
        assert reply.is_request is False

    def test_frame_is_ack(self):
        """Test ACK bit detection."""
        ack = nsp.NspFrame(control=0x20, payload=b"")
        nack = nsp.NspFrame(control=0x00, payload=b"")

        assert ack.is_ack is True
        assert nack.is_ack is False

    def test_frame_is_nack(self):
        """Test NACK detection."""
        ack_reply = nsp.NspFrame(control=0x20, payload=b"")
        nack_reply = nsp.NspFrame(control=0x00, payload=b"")
        request = nsp.NspFrame(control=0x80, payload=b"")

        assert ack_reply.is_nack is False
        assert nack_reply.is_nack is True
        assert request.is_nack is False  # Requests are not NACKs

    def test_frame_command(self):
        """Test command code extraction."""
        frame = nsp.NspFrame(control=0x85, payload=b"")  # POLL=1, cmd=5

        assert frame.command == 0x05

    def test_frame_to_bytes(self):
        """Test frame serialization."""
        frame = nsp.NspFrame(control=0x80, payload=b"\x01\x02\x03")
        data = frame.to_bytes()

        assert data == b"\x80\x01\x02\x03"

    def test_frame_from_bytes(self):
        """Test frame parsing."""
        data = b"\x80\x01\x02\x03"
        frame = nsp.NspFrame.from_bytes(data)

        assert frame.control == 0x80
        assert frame.payload == b"\x01\x02\x03"

    def test_frame_from_bytes_empty(self):
        """Test parsing empty data raises error."""
        with pytest.raises(ValueError):
            nsp.NspFrame.from_bytes(b"")

    def test_frame_from_bytes_control_only(self):
        """Test parsing control byte only."""
        data = b"\x80"
        frame = nsp.NspFrame.from_bytes(data)

        assert frame.control == 0x80
        assert frame.payload == b""


class TestNspRequestReply:
    """Test NSP request/reply construction."""

    def test_make_request(self):
        """Test creating request frame."""
        request = nsp.make_request(nsp.NspCommand.PING, b"\x01\x02")

        assert request.is_request is True
        assert request.command == nsp.NspCommand.PING
        assert request.payload == b"\x01\x02"

    def test_make_reply_ack(self):
        """Test creating ACK reply."""
        reply = nsp.make_reply(nsp.NspCommand.PING, b"\x03\x04", ack=True)

        assert reply.is_request is False
        assert reply.is_ack is True
        assert reply.command == nsp.NspCommand.PING
        assert reply.payload == b"\x03\x04"

    def test_make_reply_nack(self):
        """Test creating NACK reply."""
        reply = nsp.make_reply(nsp.NspCommand.PING, b"\x05\x06", ack=False)

        assert reply.is_request is False
        assert reply.is_ack is False
        assert reply.is_nack is True
        assert reply.command == nsp.NspCommand.PING
        assert reply.payload == b"\x05\x06"


class TestNspValidation:
    """Test NSP reply validation."""

    def test_validate_reply_success(self):
        """Test validating matching ACK reply."""
        request = nsp.make_request(nsp.NspCommand.PING)
        reply = nsp.make_reply(nsp.NspCommand.PING, ack=True)

        # Should not raise
        nsp.validate_reply(request, reply)

    def test_validate_reply_command_mismatch(self):
        """Test validation fails on command mismatch."""
        request = nsp.make_request(nsp.NspCommand.PING)
        reply = nsp.make_reply(nsp.NspCommand.PEEK, ack=True)

        with pytest.raises(nsp.NspError):
            nsp.validate_reply(request, reply)

    def test_validate_reply_nack(self):
        """Test validation fails on NACK."""
        request = nsp.make_request(nsp.NspCommand.PING)
        reply = nsp.make_reply(nsp.NspCommand.PING, ack=False)

        with pytest.raises(nsp.NspNackError):
            nsp.validate_reply(request, reply)

    def test_validate_reply_request_received(self):
        """Test validation fails if reply is a request."""
        request = nsp.make_request(nsp.NspCommand.PING)
        fake_reply = nsp.make_request(nsp.NspCommand.PING)

        with pytest.raises(nsp.NspError):
            nsp.validate_reply(request, fake_reply)


class TestNspCommands:
    """Test NSP command codes."""

    def test_command_codes(self):
        """Test command code values."""
        assert nsp.NspCommand.PING == 0x00
        assert nsp.NspCommand.PEEK == 0x02
        assert nsp.NspCommand.POKE == 0x03
        assert nsp.NspCommand.APP_TM == 0x07
        assert nsp.NspCommand.APP_CMD == 0x08
        assert nsp.NspCommand.CLEAR_FAULT == 0x09
        assert nsp.NspCommand.CONFIG_PROT == 0x0A
        assert nsp.NspCommand.TRIP_LCL == 0x0B
