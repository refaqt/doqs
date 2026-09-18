"""Fetch back the editable files a machine was built from.

A build lockfile records a machine that exists. That is only worth having if
you can still open it, and until now nothing could: the record named a version
tag, which can be moved or deleted, and no command turned it back into files.

Two jobs:

    restore-build builds/serial-0042 --out /tmp/serial-0042
        Clone every pinned repository at its exact commit.

    restore-build builds/serial-0042 --check
        Ask whether every commit is still reachable, and fetch nothing.
        Exits 1 when a commit is gone, and 2 when a repository could not be
        reached -- those are different problems and only the first needs you.

`--check` is the valuable half. Run it in CI and you learn that a record has
gone unreachable while you can still do something about it -- rather than on
the day somebody needs the drawing.

See docs/decisions/2026-09-18_build-records.md.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tomllib
from pathlib import Path

from naming_rules import repo_root_from_script

#: A shallow fetch of one commit. Cheaper than a full clone by a lot, and a
#: build record names an exact commit, so there is nothing else to fetch.
_FETCH_DEPTH = "1"


class RestoreError(Exception):
    """Raised for a lockfile that cannot be read or acted on."""


def pinned_entries(build: dict) -> list[dict]:
    """Every repository this record pins, base first."""
    entries = []
    if "base" in build:
        entries.append({"path": ".", **build["base"]})
    entries.extend(build.get("module", []))
    return [e for e in entries if e.get("repo") and e.get("commit")]


def load_build(build_dir: Path) -> dict:
    path = build_dir / "build.toml"
    if not path.is_file():
        raise RestoreError(f"no build.toml in {build_dir}")
    with open(path, "rb") as f:
        return tomllib.load(f)


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


#: Git messages that mean "I could not reach the server", not "the commit is
#: gone". Blaming the record for a network problem sends somebody hunting
#: through a history that is perfectly intact.
_UNREACHABLE_MARKERS = (
    "unable to access",
    "could not resolve host",
    "connection refused",
    "connection timed out",
    "could not read from remote repository",
    "authentication failed",
    "terminal prompts disabled",
)


def _failure_kind(stderr: str) -> str:
    """`network` when the server could not be reached, `missing` otherwise."""
    lowered = stderr.lower()
    return "network" if any(m in lowered for m in _UNREACHABLE_MARKERS) else "missing"


def commit_is_reachable(repo: str, commit: str) -> tuple[bool, str]:
    """Ask the remote whether it still has this commit, fetching nothing.

    A shallow fetch into an empty repository is the only honest test: a tag
    listing would not tell us, because the commit may be reachable with the tag
    long gone, or the tag may have been moved to something else entirely.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        init = _git("init", "--quiet", str(work))
        if init.returncode != 0:
            return False, init.stderr.strip() or "git init failed"
        result = _git(
            "fetch", "--depth", _FETCH_DEPTH, "--quiet", repo, commit, cwd=work
        )
        if result.returncode == 0:
            return True, ""
        detail = (result.stderr.strip().splitlines() or ["unreachable"])[-1]
        return False, f"{_failure_kind(result.stderr)}: {detail}"


def restore_one(entry: dict, out_dir: Path) -> str:
    """Clone one pinned repository at its commit. Returns where it landed."""
    destination = out_dir / (entry["path"] if entry["path"] != "." else "_base")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    init = _git("init", "--quiet", str(destination))
    if init.returncode != 0:
        raise RestoreError(f"{entry['path']}: {init.stderr.strip()}")
    fetch = _git(
        "fetch", "--depth", _FETCH_DEPTH, "--quiet",
        entry["repo"], entry["commit"], cwd=destination,
    )
    if fetch.returncode != 0:
        raise RestoreError(
            f"{entry['path']}: cannot fetch {entry['commit'][:12]} from "
            f"{entry['repo']} -- {(fetch.stderr.strip().splitlines() or ['unreachable'])[-1]}"
        )
    checkout = _git("checkout", "--quiet", "FETCH_HEAD", cwd=destination)
    if checkout.returncode != 0:
        raise RestoreError(f"{entry['path']}: {checkout.stderr.strip()}")
    return str(destination)


def check(build_dir: Path) -> tuple[list[str], list[str]]:
    """Pins that are gone, and pins we could not ask about.

    They are different problems with different answers. A commit that is gone
    needs somebody to act. A server we could not reach needs a network, and
    failing a build over that would teach people to ignore this check.
    """
    entries = pinned_entries(load_build(build_dir))
    gone: list[str] = []
    unknown: list[str] = []
    for entry in entries:
        ok, why = commit_is_reachable(entry["repo"], entry["commit"])
        if not ok:
            kind, _, detail = why.partition(": ")
            if kind == "network":
                unknown.append(
                    f"{entry['path']}: could not reach {entry['repo']}, so "
                    f"whether {entry['commit'][:12]} is still there is unknown "
                    f"-- {detail}"
                )
            else:
                gone.append(
                    f"{entry['path']}: {entry['commit'][:12]} is no longer in "
                    f"{entry['repo']} -- {detail}"
                )
    return gone, unknown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch back the files a machine was built from."
    )
    parser.add_argument("build", type=Path, help="a builds/<id>/ directory")
    parser.add_argument("--out", type=Path, default=None,
                        help="where to put the restored files")
    parser.add_argument("--check", action="store_true",
                        help="report unreachable pins; fetch nothing")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)

    root = args.root.resolve() if args.root else repo_root_from_script()
    build_dir = args.build if args.build.is_absolute() else root / args.build

    try:
        if args.check:
            gone, unknown = check(build_dir)
            for problem in gone + unknown:
                print(f"      {problem}")
            if gone:
                print(f"FAIL  {args.build}: {len(gone)} pin(s) are gone")
                return 1
            if unknown:
                # Exit 2, not 1: nothing is known to be wrong, but nothing was
                # confirmed either. A caller can tell the two apart; a build
                # that goes red whenever the network hiccups gets ignored.
                print(f"WARN  {args.build}: could not reach {len(unknown)} repository(ies)")
                return 2
            print(f"ok    {args.build} (every pin is still reachable)")
            return 0

        if args.out is None:
            parser.error("--out is required unless you pass --check")
        entries = pinned_entries(load_build(build_dir))
        if not entries:
            print(f"FAIL  {args.build}: nothing is pinned with a repo and a commit")
            return 1
        args.out.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            print(f"      {entry['path']} -> {restore_one(entry, args.out)}")
        print(f"ok    {args.build} restored into {args.out}")
        return 0
    except RestoreError as err:
        print(f"FAIL  {args.build}: {err}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
