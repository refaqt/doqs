"""Compare the public and the private parts library, file by file.

    python doqs/scripts/validate_mirror.py --root ../stoq --private ../stoq-private [--apply]

`doqs mirror` runs the same thing. The two libraries keep the same paths.
This lists every manifest, table and indexed file that differs, is missing
on one side, or is the same. With `--apply`, files go from the private
library to the public one where the public one may hold them: a file whose
public row says `redistributable`. Nothing ever goes the other way by
itself, and nothing is overwritten: a file that differs is reported, not
replaced. Without `--apply` nothing is written (exit 1 when something
differs, so CI can use it).
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import library_rules as lr
from naming_rules import is_parts_library, is_private_library, repo_root_from_script
from validate_variants import _shared_files


def may_hold_public(public: Path) -> dict[str, str]:
    """``{path from root: terms}`` for every file a public row names."""
    return {rel: terms for _, _, rel, terms in _shared_files(public)}


def apply(public: Path, private: Path, diff: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    """Copy private files the public library may hold. Returns (copied, skipped)."""
    allowed = may_hold_public(public)
    copied: list[str] = []
    skipped: list[str] = []
    for rel, state in diff:
        if state != "only-private":
            continue
        if allowed.get(rel) != "redistributable":
            skipped.append(f"{rel}: public row says {allowed.get(rel) or 'nothing'}, so it stays private")
            continue
        src, dst = private / rel, public / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        copied.append(rel)
    return copied, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None, help="The public library (default: this one)")
    parser.add_argument("--private", type=Path, required=True, help="The private library checkout")
    parser.add_argument("--apply", action="store_true", help="Copy allowed files private -> public")
    args = parser.parse_args(argv)
    public = (args.root.resolve() if args.root else repo_root_from_script())
    private = args.private.resolve()
    for root, name in ((public, "--root"), (private, "--private")):
        if not is_parts_library(root):
            print(f"FAIL  {root} is not a parts library ({name})")
            return 2
    if is_private_library(public) or not is_private_library(private):
        print("FAIL  --root must be the public library and --private the one marked private = true")
        return 2
    diff = lr.mirror_diff(public, private)
    same = [rel for rel, state in diff if state == "same"]
    other = [(rel, state) for rel, state in diff if state != "same"]
    if args.apply:
        copied, skipped = apply(public, private, other)
        for rel in copied:
            print(f"copied {rel}")
        for line in skipped:
            print(f"kept   {line}")
        other = [(rel, state) for rel, state in other if rel not in copied]
    if not other:
        print(f"ok    {len(same)} files are the same in both libraries")
        return 0
    print(f"{'WARN' if args.apply else 'FAIL'}  mirror: {len(other)} files differ between the libraries "
          f"({len(same)} are the same)")
    for rel, state in other:
        print(f"      {state:<13} {rel}")
    return 0 if args.apply else 1


if __name__ == "__main__":
    sys.exit(main())
