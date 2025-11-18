#!/usr/bin/env python3
"""
Command fuzzing tool.

Sends random commands within safe bounds for robustness testing.
"""

import argparse
import random
import sys

from nss_host.commands import Session


def main() -> int:
    """Main entry point for nss-fuzz tool."""
    parser = argparse.ArgumentParser(description="Fuzz emulator with random commands")
    parser.add_argument("--port", default="/dev/ttyAMA0", help="Serial port")
    parser.add_argument("--baud", type=int, default=460800, help="Baud rate")
    parser.add_argument("--count", type=int, default=100, help="Number of fuzzing iterations")
    parser.add_argument(
        "--safe", action="store_true", help="Stay within safe bounds (recommended)"
    )

    args = parser.parse_args()

    # Safety limits
    max_speed_rpm = 1000.0 if args.safe else 5000.0

    print(f"Fuzzing with {args.count} iterations...")
    if args.safe:
        print("  Safe mode: enabled")
    else:
        print("  WARNING: Safe mode disabled - may trigger protections!")

    try:
        with Session.open(args.port, args.baud) as session:
            successes = 0
            failures = 0

            for i in range(args.count):
                try:
                    # Random operation
                    op = random.choice(["ping", "telemetry", "command"])

                    if op == "ping":
                        session.ping()
                        successes += 1

                    elif op == "telemetry":
                        session.app_telemetry("STANDARD")
                        successes += 1

                    elif op == "command":
                        # Random speed setpoint
                        speed = random.uniform(-max_speed_rpm, max_speed_rpm)
                        session.app_command(mode="SPEED", setpoint_rpm=speed)
                        successes += 1

                    if (i + 1) % 10 == 0:
                        print(f"  {i + 1}/{args.count} completed...")

                except Exception as e:
                    failures += 1
                    print(f"  Failure on iteration {i + 1}: {e}")

            print()
            print("Fuzzing complete:")
            print(f"  Successes: {successes}")
            print(f"  Failures: {failures}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
