"""Validate build lockfiles: interface consistency, and pins you can act on.

A lockfile records a machine that exists. It is only worth having if you can
still get back what went into it, so each entry names the repository, the
readable tag, and the exact commit. A tag can be moved or deleted; a commit
cannot. See docs/decisions/2026-09-18_build-records.md.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
import tomllib

from naming_rules import GIT_TAG, repo_root_from_script


def load_module_manifest(root: Path, mod_entry: dict) -> dict:
    """Read the manifest a lockfile entry points at.

    When the entry names a `composition` inside a family, the interfaces that
    matter are the composition's, not the family root's: a stepper SKU and a
    servo SKU genuinely offer different ones.
    """
    base = root / mod_entry["path"]
    composition = mod_entry.get("composition")
    if composition:
        base = base / composition
    mod_path = base / "okh.toml"
    with open(mod_path, "rb") as f:
        return tomllib.load(f)


def collect_interfaces(modules: list[dict]) -> tuple[dict, list]:
    provided: dict = {}
    consumed: list = []
    for m in modules:
        manifest = m["manifest"]
        for iface in manifest.get("provides-interface", []):
            key = (iface["name"], iface["version"].split(".")[0])
            provided.setdefault(key, []).append(m["path"])
        for iface in manifest.get("consumes-interface", []):
            key = (iface["name"], iface["version"].split(".")[0])
            consumed.append({"interface": key, "by": m["path"]})
    return provided, consumed


COMMIT = re.compile(r"^[0-9a-f]{40}$")


def check_pins(build: dict) -> list[str]:
    """Can this record still be opened?

    Three things make the difference between a record and a reference: which
    repository, which readable version, and which exact commit. Only the last
    one cannot drift.
    """
    errors: list[str] = []
    entries = [("[base]", build["base"])] if "base" in build else []
    entries += [(f"[[module]] {e.get('path', '?')}", e) for e in build.get("module", [])]
    for label, entry in entries:
        if not entry.get("repo"):
            errors.append(
                f"{label} has no 'repo'. Without it nobody knows where to fetch "
                "this from."
            )
        version = str(entry.get("version", ""))
        if version and not GIT_TAG.match(version):
            errors.append(
                f"{label} version {version!r} is not a tag like 'v1.2.0'"
            )
        commit = str(entry.get("commit", ""))
        if not commit:
            errors.append(
                f"{label} has no 'commit'. A tag can be moved or deleted, so a "
                "version alone does not pin anything."
            )
        elif not COMMIT.match(commit):
            errors.append(
                f"{label} commit {commit!r} is not a full 40-character commit id"
            )
    return errors


def validate(build_path: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    with open(build_path, "rb") as f:
        build = tomllib.load(f)

    modules = []
    for entry in build.get("module", []):
        modules.append({
            "path": entry["path"],
            "version": entry["version"],
            "manifest": load_module_manifest(repo_root, entry),
        })
    for entry in build.get("module", []):
        if "adapter" not in entry:
            continue
        adapter_path = entry["adapter"].split("@")[0]
        modules.append({
            "path": adapter_path,
            "version": entry["adapter"].split("@")[1],
            "manifest": load_module_manifest(repo_root, {"path": adapter_path}),
        })

    errors.extend(check_pins(build))

    provided, consumed = collect_interfaces(modules)
    for need in consumed:
        if need["interface"] not in provided:
            errors.append(
                f"Unsatisfied interface {need['interface']} required by "
                f"{need['by']} — no module in this build provides it"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate build lockfiles.")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_script()
    all_ok = True
    build_files = sorted((root / "builds").rglob("build.toml"))
    for build_file in build_files:
        errs = validate(build_file, root)
        rel = build_file.relative_to(root)
        if errs:
            all_ok = False
            print(f"FAIL  {rel}")
            for e in errs:
                print(f"      {e}")
        else:
            print(f"ok    {rel}")
    if not build_files:
        print("No build.toml files found under builds/")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
