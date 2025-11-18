"""
SLIP (Serial Line Internet Protocol) encoder/decoder.

Implements HOST_SPEC_RPi.md section 5: Protocol Details (SLIP).
END=0xC0, ESC=0xDB, ESC_END=0xDC, ESC_ESC=0xDD.
"""

from typing import List

# SLIP special characters
END = 0xC0
ESC = 0xDB
ESC_END = 0xDC
ESC_ESC = 0xDD


def encode(data: bytes) -> bytes:
    """
    Encode data using SLIP framing.

    Args:
        data: Raw data to encode.

    Returns:
        SLIP-encoded data with END delimiters.
    """
    encoded = bytearray([END])  # Start with END

    for byte in data:
        if byte == END:
            encoded.extend([ESC, ESC_END])
        elif byte == ESC:
            encoded.extend([ESC, ESC_ESC])
        else:
            encoded.append(byte)

    encoded.append(END)  # End with END
    return bytes(encoded)


def decode(data: bytes) -> List[bytes]:
    """
    Decode SLIP-framed data.

    Args:
        data: SLIP-encoded data (may contain multiple frames).

    Returns:
        List of decoded frames (without SLIP framing).
    """
    frames: List[bytes] = []
    current_frame = bytearray()
    escape_next = False

    for byte in data:
        if escape_next:
            if byte == ESC_END:
                current_frame.append(END)
            elif byte == ESC_ESC:
                current_frame.append(ESC)
            else:
                # Invalid escape sequence - add both bytes
                current_frame.append(ESC)
                current_frame.append(byte)
            escape_next = False
        elif byte == ESC:
            escape_next = True
        elif byte == END:
            # End of frame
            if len(current_frame) > 0:
                frames.append(bytes(current_frame))
                current_frame = bytearray()
        else:
            current_frame.append(byte)

    # Handle incomplete frame (no trailing END)
    if len(current_frame) > 0:
        frames.append(bytes(current_frame))

    return frames


class SlipDecoder:
    """
    Stateful SLIP decoder for incremental decoding.

    Useful for processing serial data as it arrives.
    """

    def __init__(self) -> None:
        """Initialize SLIP decoder state."""
        self.current_frame = bytearray()
        self.escape_next = False

    def feed(self, data: bytes) -> List[bytes]:
        """
        Feed data to decoder and return complete frames.

        Args:
            data: Raw bytes from serial port.

        Returns:
            List of complete frames (if any).
        """
        frames: List[bytes] = []

        for byte in data:
            if self.escape_next:
                if byte == ESC_END:
                    self.current_frame.append(END)
                elif byte == ESC_ESC:
                    self.current_frame.append(ESC)
                else:
                    # Invalid escape - add both
                    self.current_frame.append(ESC)
                    self.current_frame.append(byte)
                self.escape_next = False
            elif byte == ESC:
                self.escape_next = True
            elif byte == END:
                if len(self.current_frame) > 0:
                    frames.append(bytes(self.current_frame))
                    self.current_frame = bytearray()
            else:
                self.current_frame.append(byte)

        return frames

    def reset(self) -> None:
        """Reset decoder state (discard incomplete frame)."""
        self.current_frame = bytearray()
        self.escape_next = False
