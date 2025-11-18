#!/usr/bin/env python3
"""
Round-trip time (RTT) benchmark tool.

Measures latency and throughput of NSP communication.
"""

import argparse
import statistics
import sys
import time

from nss_host.commands import Session


def main() -> int:
    """Main entry point for nss-bench tool."""
    parser = argparse.ArgumentParser(description="Benchmark NSP round-trip time")
    parser.add_argument("--port", default="/dev/ttyAMA0", help="Serial port")
    parser.add_argument("--baud", type=int, default=460800, help="Baud rate")
    parser.add_argument("--count", type=int, default=100, help="Number of pings")

    args = parser.parse_args()

    # Run benchmark
    try:
        with Session.open(args.port, args.baud) as session:
            print(f"Benchmarking {args.count} PINGs...")

            rtts = []
            errors = 0

            for i in range(args.count):
                start = time.perf_counter()
                try:
                    session.ping()
                    elapsed = time.perf_counter() - start
                    rtts.append(elapsed * 1000)  # Convert to ms

                    if (i + 1) % 10 == 0:
                        print(f"  {i + 1}/{args.count} completed...")

                except Exception as e:
                    errors += 1
                    print(f"  Error on ping {i + 1}: {e}")

            # Compute statistics
            if rtts:
                print()
                print("Results:")
                print(f"  Successful: {len(rtts)}/{args.count}")
                print(f"  Errors: {errors}")
                print(f"  Mean RTT: {statistics.mean(rtts):.3f} ms")
                print(f"  Median RTT: {statistics.median(rtts):.3f} ms")
                print(f"  Min RTT: {min(rtts):.3f} ms")
                print(f"  Max RTT: {max(rtts):.3f} ms")
                if len(rtts) > 1:
                    print(f"  Std Dev: {statistics.stdev(rtts):.3f} ms")

                # Percentiles
                sorted_rtts = sorted(rtts)
                p50 = sorted_rtts[len(sorted_rtts) // 2]
                p95 = sorted_rtts[int(len(sorted_rtts) * 0.95)]
                p99 = sorted_rtts[int(len(sorted_rtts) * 0.99)]
                print(f"  P50: {p50:.3f} ms")
                print(f"  P95: {p95:.3f} ms")
                print(f"  P99: {p99:.3f} ms")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
