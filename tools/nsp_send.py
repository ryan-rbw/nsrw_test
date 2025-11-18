#!/usr/bin/env python3
"""
Raw NSP frame sender tool.

Allows sending arbitrary NSP frames for testing and debugging.
"""

import argparse
import sys

from nss_host.commands import Session
from nss_host.nsp import NspCommand, make_request


def main() -> int:
    """Main entry point for nss-send tool."""
    parser = argparse.ArgumentParser(description="Send raw NSP frames")
    parser.add_argument("--port", default="/dev/ttyAMA0", help="Serial port")
    parser.add_argument("--baud", type=int, default=460800, help="Baud rate")
    parser.add_argument(
        "--command", required=True, type=str, help="Command (PING, PEEK, POKE, etc.)"
    )
    parser.add_argument("--payload", default="", help="Payload as hex string")

    args = parser.parse_args()

    # Parse command
    try:
        cmd = NspCommand[args.command.upper()]
    except KeyError:
        print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
        return 1

    # Parse payload
    try:
        payload = bytes.fromhex(args.payload) if args.payload else b""
    except ValueError:
        print(f"Error: Invalid hex payload '{args.payload}'", file=sys.stderr)
        return 1

    # Send frame
    try:
        with Session.open(args.port, args.baud) as session:
            request = make_request(cmd, payload)
            session._send_frame(request)
            print(f"Sent {cmd.name} with {len(payload)} byte payload")

            # Try to receive reply
            reply = session._receive_frame(timeout_s=0.1)
            if reply:
                print(f"Reply: {reply.to_bytes().hex()}")
                print(f"  ACK: {reply.is_ack}, Payload: {len(reply.payload)} bytes")
            else:
                print("No reply received")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
