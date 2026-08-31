"""Validate split-licence files in a machine, extracted-module, or tools repo."""
from __future__ import annotations

import argparse
from pathlib import Path

from license_rules import check_any_repo, is_doqs_tools_repo, iter_repo_roots
from naming_rules import repo_root_from_script


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that each Git repository root has the DOQS split-licence "
            "layout. Machine repos: LICENSE, LICENSES/, TRADEMARKS.md, "
            "directory stubs, okh.toml CERN-OHL-S-2.0, README Licence section. "
            "The DOQS tools repo: GPL-3.0 / CC BY-SA kit (no CERN-OHL-S, no okh.toml)."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repo root (default: parent of doqs/ submodule). Pass the doqs "
        "clone root to check the tools-repo kit.",
    )
    args = parser.parse_args()
    root = args.root.resolve() if args.root else repo_root_from_script()

    all_ok = True
    for repo in iter_repo_roots(root):
        errors = check_any_repo(repo)
        rel = "." if repo == root else repo.relative_to(root)
        kind = "tools" if is_doqs_tools_repo(repo) else "machine"
        if errors:
            all_ok = False
            print(f"FAIL  {rel} ({kind})")
            for err in errors:
                print(f"      {err}")
        else:
            print(f"ok    {rel} ({kind})")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
