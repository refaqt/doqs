"""Stop sharing files whose terms became fetch-only or private.

When a brand's terms change, or a file turns out to have come with a quotation,
a file that git tracks may no longer be shared. This command takes it out of git
without losing it:

    bash doqs.sh unshare --from ../stoq-private modules/hiwin/modules/hgr-rail/cad/original/HGR20R500.step

For every path it first checks that the private library holds the same file,
with the same checksum. Only when every path passes does it run
`git rm --cached` and add the exact paths to `.gitignore`. It never deletes
the file on disk, and it says so, with the command to delete it or to get it
back.

It cannot take the file out of earlier commits. History here is never
rewritten, so a file that was pushed to a public place stays there.
See docs/parts-library.md, "Files we may not share never enter git".
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

from intake_rules import NOT_COMMITTED
from naming_rules import repo_root_from_script
from validate_variants import _shared_files, git_tracked

#: Characters that mean something in a .gitignore line. A path that holds one
#: gets a backslash before it, so the line matches that one file only.
_GITIGNORE_SPECIAL = "\\*?[]!#"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gitignore_line(rel: str) -> str:
    """The exact path as a .gitignore line that matches this one file."""
    escaped = "".join("\\" + c if c in _GITIGNORE_SPECIAL else c for c in rel)
    if escaped.endswith(" "):
        escaped = escaped[:-1] + "\\ "
    return escaped


def relative_paths(root: Path, paths: list[str]) -> tuple[list[str], list[str]]:
    """Paths from the repository root, and problems with the ones that are not."""
    found: list[str] = []
    problems: list[str] = []
    for raw in paths:
        path = (Path.cwd() / raw).resolve()
        try:
            found.append(path.relative_to(root).as_posix())
        except ValueError:
            problems.append(f"{raw}: not inside the repository at {root}")
    return found, problems


def check(root: Path, private: Path, rels: list[str]) -> list[str]:
    """Every reason not to unshare. Empty when all paths are safe to take out."""
    problems: list[str] = []
    tracked = git_tracked(root)
    if tracked is None:
        return [f"{root} is not a git checkout"]
    for rel in rels:
        local = root / rel
        if not local.is_file():
            problems.append(f"{rel}: no such file here")
            continue
        if rel not in tracked:
            problems.append(f"{rel}: git does not track it, so there is nothing to unshare")
            continue
        copy = private / rel
        if not copy.is_file():
            problems.append(
                f"{rel}: not in the private library at {private}. Copy it there and "
                "commit it first, or the only copy is the one on this disk.")
            continue
        if sha256(copy) != sha256(local):
            problems.append(
                f"{rel}: the private copy has a different checksum. Find out which "
                "one is right before you take it out of git.")
    return problems


def rows_not_marked(root: Path, rels: list[str]) -> list[str]:
    """Paths whose row still says the file may be shared."""
    terms_of = {rel: terms for _, _, rel, terms in _shared_files(root)}
    return [rel for rel in rels if terms_of.get(rel) not in NOT_COMMITTED]


def add_to_gitignore(root: Path, rels: list[str]) -> list[str]:
    """Append the exact paths to the root .gitignore. Returns the lines added."""
    path = root / ".gitignore"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    present = {line.strip() for line in text.splitlines()}
    added = [gitignore_line(rel) for rel in rels if gitignore_line(rel) not in present]
    if not added:
        return []
    if text and not text.endswith("\n"):
        text += "\n"
    text += "# Not shared any more: the copy we keep is in the private library.\n"
    text += "".join(line + "\n" for line in added)
    path.write_text(text, encoding="utf-8")
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", help="Files to stop sharing, from the current folder")
    parser.add_argument("--from", dest="private", type=Path, required=True,
                        help="Checkout of the private library that keeps the copy")
    parser.add_argument("--root", type=Path, default=None,
                        help="Parts library root (default: parent of doqs/ submodule)")
    args = parser.parse_args(argv)
    root = (args.root or repo_root_from_script()).resolve()
    private = args.private.resolve()
    if not private.is_dir():
        print(f"error: no private checkout at {private}", file=sys.stderr)
        return 2
    if private == root:
        print("error: --from is this library itself", file=sys.stderr)
        return 2

    rels, problems = relative_paths(root, args.paths)
    problems += check(root, private, rels)
    if problems:
        for message in problems:
            print(f"FAIL  {message}")
        print("FAIL  nothing was changed")
        return 1

    result = subprocess.run(
        ["git", "-C", str(root), "rm", "--cached", "--quiet", "--", *rels],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"FAIL  git rm --cached failed: {result.stderr.strip()}")
        return 1
    added = add_to_gitignore(root, rels)

    for rel in rels:
        print(f"ok    {rel}: git no longer tracks it")
    if added:
        print(f"ok    .gitignore: added {len(added)} exact path(s)")
    for rel in rows_not_marked(root, rels):
        print(f"WARN  {rel}: its row still says it may be shared. Set its terms to "
              "fetch-only or private.")
    print()
    print("The file is still on this disk. Git does not track it any more.")
    print("Commit the change: git commit -m \"chore: stop sharing files we may not share\"")
    print("To delete the local copy:")
    for rel in rels:
        print(f"    rm \"{rel}\"")
    print("To get it back later from the private library:")
    print(f"    bash doqs.sh restore-private --from {args.private}")
    print("Earlier commits still hold the file. If they were pushed to a public")
    print("place, tell the person who approved the brand's terms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
