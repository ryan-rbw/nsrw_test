#!/usr/bin/env python3
"""
NSP traffic recorder/replayer.

Records NSP frames to .nsplog files (pcap-like format).
"""

import argparse
import sys
import time

from nss_host.commands import Session


def main() -> int:
    """Main entry point for nss-record tool."""
    parser = argparse.ArgumentParser(description="Record/replay NSP traffic")
    parser.add_argument("--port", default="/dev/ttyAMA0", help="Serial port")
    parser.add_argument("--baud", type=int, default=460800, help="Baud rate")
    parser.add_argument("--output", required=True, help="Output .nsplog file")
    parser.add_argument("--duration", type=float, default=10.0, help="Recording duration (s)")

    args = parser.parse_args()

    print(f"Recording NSP traffic for {args.duration} seconds...")
    print(f"Output: {args.output}")
    print()

    # TODO: Implement actual recording logic
    # For now, just a placeholder

    try:
        with Session.open(args.port, args.baud) as session:
            start_time = time.time()

            while time.time() - start_time < args.duration:
                try:
                    # Poll telemetry to generate traffic
                    session.app_telemetry("STANDARD")
                    time.sleep(0.1)

                except KeyboardInterrupt:
                    print("\nStopped by user")
                    break

            print()
            print(f"Recording complete")
            print(f"Stats: {session.stats}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
