"""Run the DOQS validation gates.

This runs the same seven gates it has always run, and nothing else. That is the
contract: a machine repository can bump its doqs pin without its CI suddenly
gaining checks nobody asked for.

`python doqs/doqs.py check` runs these seven **plus** three checks on generated
files (`resolve_params --table --check`, `resolve_instance --check`,
`apply_licenses --check`). Move your CI to that command when you are ready for
them; see `doqs list`.

The gate list itself lives in `cli.GATES`, so the two commands cannot drift.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from cli import GATES, report, run_steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run all DOQS validation scripts.")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Machine repo root (passed to scripts that support it)",
    )
    parser.add_argument(
        "--expected-version",
        default=None,
        help="Passed to validate_okh.py for release tagging",
    )
    parser.add_argument(
        "--strict-lexicon",
        action="store_true",
        help="Passed to check_names.py",
    )
    args = parser.parse_args(argv)

    extra: dict[str, list[str]] = {}
    if args.expected_version:
        extra["validate_okh.py"] = ["--expected-version", args.expected_version]
    if args.strict_lexicon:
        extra["check_names.py"] = ["--strict-lexicon"]

    return report(run_steps(GATES, args.root, extra), "all validators passed")


if __name__ == "__main__":
    raise SystemExit(main())
