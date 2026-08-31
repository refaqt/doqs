"""Write the canonical split-licence file set into a repo.

Machine / extracted-module roots: CERN-OHL-S hardware, GPL software, CC BY-SA
docs. The DOQS tools repo itself: GPL software, CC BY-SA docs (no CERN-OHL-S).

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
    advice_any_messages,
    apply_any_repo,
    check_any_generated_files,
    is_doqs_tools_repo,
    iter_repo_roots,
)
from naming_rules import repo_root_from_script


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply DOQS split-licence files at each Git repository root "
            "(machine: CERN-OHL-S / GPL / CC BY-SA; tools repo: GPL / CC BY-SA)."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repo root (default: parent of doqs/ submodule). Pass the doqs "
        "clone root to apply the tools-repo kit.",
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
        kind = "tools" if is_doqs_tools_repo(repo) else "machine"
        if args.check:
            errors = check_any_generated_files(repo)
            if errors:
                failed = True
                print(f"FAIL  {rel} ({kind})")
                for err in errors:
                    print(f"      {err}")
            else:
                print(f"ok    {rel} ({kind})")
            continue

        actions = apply_any_repo(repo)
        if actions:
            print(f"updated {rel} ({kind})")
            for line in actions:
                print(f"      {line}")
        else:
            print(f"ok    {rel} ({kind}, already complete)")
        for note in advice_any_messages(repo):
            for line in note.splitlines():
                print(f"note  {line}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
