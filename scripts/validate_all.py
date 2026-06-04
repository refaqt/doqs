"""Run all DOQS validation gates (excludes build_graph generator)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = (
    "validate_okh.py",
    "check_names.py",
    "check_links.py",
    "validate_build.py",
)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def main() -> int:
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
    args = parser.parse_args()

    scripts_dir = Path(__file__).resolve().parent
    root_args: list[str] = []
    if args.root:
        root_args = ["--root", str(args.root.resolve())]

    failed: list[str] = []
    for name in SCRIPTS:
        script = scripts_dir / name
        cmd = [sys.executable, str(script), *root_args]
        if name == "validate_okh.py" and args.expected_version:
            cmd.extend(["--expected-version", args.expected_version])
        if name == "check_names.py" and args.strict_lexicon:
            cmd.append("--strict-lexicon")

        print(f"--- {name} ---")
        cwd = args.root.resolve() if args.root else repo_root_from_script()
        result = subprocess.run(cmd, cwd=cwd)
        if result.returncode != 0:
            failed.append(name)

    if failed:
        print(f"\nFAILED: {', '.join(failed)}")
        return 1
    print("\nok    all validators passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
