#!/usr/bin/env python3
"""
Telemetry dump tool.

Continuously polls and displays telemetry from the emulator.
"""

import argparse
import sys
import time

from nss_host.commands import Session
from nss_host.telemetry import TelemetryBlock


def main() -> int:
    """Main entry point for nss-dump tool."""
    parser = argparse.ArgumentParser(description="Dump telemetry from emulator")
    parser.add_argument("--port", default="/dev/ttyAMA0", help="Serial port")
    parser.add_argument("--baud", type=int, default=460800, help="Baud rate")
    parser.add_argument(
        "--block", default="STANDARD", help="Telemetry block (STANDARD, TEMP, VOLT, etc.)"
    )
    parser.add_argument("--rate", type=float, default=1.0, help="Polling rate (Hz)")
    parser.add_argument("--count", type=int, default=0, help="Number of samples (0=infinite)")

    args = parser.parse_args()

    # Parse block
    try:
        block = TelemetryBlock[args.block.upper()]
    except KeyError:
        print(f"Error: Unknown telemetry block '{args.block}'", file=sys.stderr)
        return 1

    # Polling period
    period_s = 1.0 / args.rate

    # Poll telemetry
    try:
        with Session.open(args.port, args.baud) as session:
            print(f"Polling {block.name} telemetry at {args.rate} Hz...")
            print()

            count = 0
            while args.count == 0 or count < args.count:
                try:
                    tm = session.app_telemetry(block)

                    # Display telemetry
                    print(f"[{count}] {tm}")

                    count += 1
                    time.sleep(period_s)

                except KeyboardInterrupt:
                    print("\nStopped by user")
                    break

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
