"""Write the canonical split-licence file set into a machine (or extracted-module) repo.

Default: create or update generated files (root LICENSE, TRADEMARKS.md,
LICENSES/ texts, per-directory LICENSE stubs). Does not rewrite README.md or
okh.toml — prints the expected snippets if they are missing.

    python doqs/scripts/apply_licenses.py
    python doqs/scripts/apply_licenses.py --check
    python doqs/scripts/apply_licenses.py --root PATH
"""
from __future__ import annotations

import argparse
from pathlib import Path

from license_rules import (
    advice_messages,
    apply_repo,
    check_generated_files,
    iter_repo_roots,
)
from naming_rules import repo_root_from_script


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply DOQS split-licence files (CERN-OHL-S hardware, GPL software, "
            "CC BY-SA docs) at each Git repository root."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Machine repo root (default: parent of doqs/ submodule)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report missing/invalid generated files; do not write",
    )
    args = parser.parse_args()
    root = args.root.resolve() if args.root else repo_root_from_script()

    failed = False
    for repo in iter_repo_roots(root):
        rel = "." if repo == root else repo.relative_to(root)
        if args.check:
            errors = check_generated_files(repo)
            if errors:
                failed = True
                print(f"FAIL  {rel}")
                for err in errors:
                    print(f"      {err}")
            else:
                print(f"ok    {rel}")
            continue

        actions = apply_repo(repo)
        if actions:
            print(f"updated {rel}")
            for line in actions:
                print(f"      {line}")
        else:
            print(f"ok    {rel} (already complete)")
        for note in advice_messages(repo):
            for line in note.splitlines():
                print(f"note  {line}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
