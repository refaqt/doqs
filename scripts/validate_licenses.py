"""Validate split-licence files in a machine (or extracted-module) repo."""
from __future__ import annotations

import argparse
from pathlib import Path

from license_rules import check_repo, iter_repo_roots
from naming_rules import repo_root_from_script


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that each Git repository root has the DOQS split-licence "
            "layout (LICENSE, LICENSES/, TRADEMARKS.md, directory stubs, "
            "okh.toml CERN-OHL-S-2.0, README Licence section)."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Machine repo root (default: parent of doqs/ submodule)",
    )
    args = parser.parse_args()
    root = args.root.resolve() if args.root else repo_root_from_script()

    all_ok = True
    for repo in iter_repo_roots(root):
        errors = check_repo(repo)
        rel = "." if repo == root else repo.relative_to(root)
        if errors:
            all_ok = False
            print(f"FAIL  {rel}")
            for err in errors:
                print(f"      {err}")
        else:
            print(f"ok    {rel}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
