#!/usr/bin/env python3
"""Verify that independent Celery workers are reachable and registered."""

import argparse
import sys

from config.celery import app

REQUIRED_TASKS = {
    "apps.product_data.tasks.execute_product_application",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-workers", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    inspector = app.control.inspect(timeout=args.timeout)
    pings = inspector.ping() or {}
    if len(pings) < args.min_workers:
        print(
            f"Expected at least {args.min_workers} workers, found {len(pings)}: "
            f"{sorted(pings)}",
            file=sys.stderr,
        )
        return 1

    registered = inspector.registered() or {}
    failed = False
    for worker in sorted(pings):
        tasks = set(registered.get(worker, ()))
        missing = sorted(REQUIRED_TASKS - tasks)
        if missing:
            failed = True
            print(f"{worker} missing tasks: {', '.join(missing)}", file=sys.stderr)
        else:
            print(f"{worker}: OK ({len(tasks)} registered tasks)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
