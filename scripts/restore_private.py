"""Copy the files we may not share from the private library into place.

A parts library commits only the address, checksum and date of a file whose
terms are `fetch-only` or `private`. The file itself is kept in a second,
private repository with the same folder layout. This command copies each such
file from that checkout into the public one, so the models open:

    bash doqs.sh restore-private --from ../stoq-private
    bash doqs.sh restore-private --from ../stoq-private --check   # report only

It never writes to the private checkout, never overwrites a file that already
matches, and refuses a file whose checksum differs from the one recorded. The
copied files stay out of git: each path is listed in `.gitignore`, and
`doqs check` fails if one is tracked anyway.

The private library is never a submodule of a public repository. A public
clone could not fetch it, and every clone would fail.
See docs/decisions/2026-09-29_component-intake.md.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

from intake_rules import NOT_COMMITTED
from naming_rules import csv_reader_skipping_comments, is_under_tooling_submodule, repo_root_from_script
from validate_variants import VENDOR_INDEX, _shared_files, module_root_of


def recorded_checksums(root: Path) -> dict[str, str]:
    """Path from root -> sha256, from every vendor-index.csv."""
    sums: dict[str, str] = {}
    top = root.resolve()
    for index in sorted(root.rglob(VENDOR_INDEX)):
        if is_under_tooling_submodule(index, root):
            continue
        for row in csv_reader_skipping_comments(index.read_text(encoding="utf-8")):
            relpath = (row.get("relpath") or "").strip()
            digest = (row.get("sha256") or "").strip().lower()
            if not relpath or not digest:
                continue
            path = (module_root_of(index) / relpath).resolve()
            if path.is_relative_to(top):
                sums[path.relative_to(top).as_posix()] = digest
    return sums


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync(root: Path, private: Path, *, check: bool) -> tuple[list[str], list[str], list[str]]:
    """Returns (copied or present, missing from the private copy, errors)."""
    done: list[str] = []
    missing: list[str] = []
    errors: list[str] = []
    sums = recorded_checksums(root)
    wanted = sorted({rel for _, _, rel, terms in _shared_files(root) if terms in NOT_COMMITTED})
    for rel in wanted:
        source = private / rel
        target = root / rel
        expected = sums.get(rel)
        if not source.is_file():
            if target.is_file():
                done.append(f"here   {rel} (not in the private copy yet)")
            else:
                missing.append(rel)
            continue
        actual = sha256(source)
        if expected and actual != expected:
            errors.append(
                f"{rel}: the private copy does not match its recorded checksum. "
                "Check which is right before you copy anything.")
            continue
        if target.is_file() and sha256(target) == actual:
            done.append(f"same   {rel}")
            continue
        if check:
            done.append(f"would  {rel}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        done.append(f"copied {rel}")
    return done, missing, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None,
                        help="Parts library root (default: parent of doqs/ submodule)")
    parser.add_argument("--from", dest="private", type=Path, required=True,
                        help="Checkout of the private library")
    parser.add_argument("--check", action="store_true",
                        help="Report what would be copied; change nothing")
    args = parser.parse_args(argv)
    root = (args.root or repo_root_from_script()).resolve()
    private = args.private.resolve()
    if not private.is_dir():
        print(f"error: no private checkout at {private}", file=sys.stderr)
        return 2
    if private == root:
        print("error: --from is the public library itself", file=sys.stderr)
        return 2

    done, missing, errors = sync(root, private, check=args.check)
    for line in done:
        print(f"ok    {line}")
    for rel in missing:
        print(f"WARN  {rel}: not in the private copy and not here")
    for message in errors:
        print(f"FAIL  {message}")
    if errors:
        return 1
    print(f"ok    restore-private ({len(done)} file(s), {len(missing)} missing)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
