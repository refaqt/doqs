"""Validate FreeCAD documents, their fingerprints, and the agent-CAD guard.

Three gates, in order of how much damage they prevent:

1. **The guard.** `.claude/settings.json` must deny the FreeCAD MCP tools that
   write a `.FCStd` behind an open GUI document. FreeCAD does not detect that a
   file changed on disk and silently overwrites on the next save from either
   side (FreeCAD issue #8924), so this is a data-loss gate, not a style rule.
   It is enforced only once a repository actually has a `.FCStd`: the guard
   protects FreeCAD documents, so a machine repo without any has nothing to
   guard, and CI asks for the guard on the commit that adds the first one.

2. **Fingerprint currency.** Every committed `.FCStd` needs a fingerprint whose
   recorded digest matches the file. A mismatch means geometry moved without a
   rebuild, so the committed measurements describe a model that no longer
   exists.

3. **Geometric regression.** Because fingerprints are committed, a change that
   moves a volume or a bounding box shows up as a reviewable text diff in the
   pull request. Nothing to run here — `git diff` is the report.

4. **Stale tool copies.** DOQS used to ship `fingerprint.py` and
   `sync_params.py` as per-module copies, and `build_model.py` with its
   scaffolding inlined. Those copies never update with the submodule, and a
   stale `fingerprint.py` is actively unsafe: it reads `FINGERPRINT_SCHEMA`
   live from `cad_rules.py` while its own `measure()` is frozen, so a schema
   bump makes it stamp a new schema number on an old payload. This is a FAIL
   rather than a warning because a stale copy still runs.

Run from the machine repository root:

    python doqs/scripts/validate_cad.py
    python doqs/scripts/validate_cad.py --check-clean
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from cad_rules import (
    DENIED_MCP_TOOLS,
    FingerprintError,
    cad_documents,
    file_digest,
    fingerprint_path,
    load_fingerprint,
    missing_guard_rules,
)
from license_rules import is_doqs_tools_repo
from naming_rules import repo_root_from_script

SETTINGS_PATH = Path(".claude") / "settings.json"


def validate_guard(root: Path) -> list[str]:
    """The deny rules that keep an agent from writing a .FCStd on disk."""
    settings_file = root / SETTINGS_PATH
    if not settings_file.is_file():
        return [
            f"{SETTINGS_PATH} not found. Copy doqs/templates/agent-cad/claude-settings.json "
            f"there, or run setup-tooling. Without it an agent can be handed tools that "
            f"overwrite an open .FCStd: {', '.join(DENIED_MCP_TOOLS)}"
        ]
    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        return [f"{SETTINGS_PATH}: invalid JSON ({err})"]
    if not isinstance(settings, dict):
        return [f"{SETTINGS_PATH}: expected a JSON object"]
    missing = missing_guard_rules(settings)
    if missing:
        return [
            f"{SETTINGS_PATH}: permissions.deny is missing {m} — an agent could "
            "overwrite a .FCStd that is open in the GUI"
            for m in missing
        ]
    return []


def validate_document(fcstd: Path, root: Path) -> list[str]:
    """Check one .FCStd against its committed fingerprint."""
    rel = fcstd.relative_to(root)
    fp_path = fingerprint_path(fcstd)
    try:
        data = load_fingerprint(fp_path)
    except FingerprintError as err:
        return [
            f"{err}. Rebuild with: FreeCADCmd {fcstd.parent.relative_to(root)}/build_model.py"
        ]

    errors: list[str] = []
    if not data.get("saved"):
        errors.append(
            f"{fp_path.relative_to(root)}: measured from an unsaved document, so it "
            "cannot be reproduced from the committed .FCStd. Rebuild headless before committing."
        )

    sources = data.get("sources") or {}
    recorded = sources.get(fcstd.name)
    if recorded is None:
        errors.append(f"{fp_path.relative_to(root)}: records no digest for {fcstd.name}")
    elif recorded != file_digest(fcstd):
        errors.append(
            f"{rel} changed since its fingerprint was written — the committed "
            "measurements describe different geometry. Rebuild with build_model.py."
        )

    for name, digest in sorted(sources.items()):
        if name == fcstd.name:
            continue
        export = fcstd.parent / name
        if not export.is_file():
            errors.append(f"{rel}: fingerprinted export {name} is missing")
        elif file_digest(export) != digest:
            errors.append(f"{rel}: export {name} is stale relative to the fingerprint")

    for recorded_error in data.get("errors") or []:
        errors.append(f"{rel}: recorded at build time — {recorded_error}")

    return errors


#: Tools that used to be copied into a module's `cad/`, and where they live now.
LEGACY_TOOL_COPIES = {
    "fingerprint.py": "doqs/scripts/cad_fingerprint.py",
    "sync_params.py": "doqs/scripts/cad_sync_params.py",
}

#: A pre-refactor `build_model.py` carried its own scaffolding. The seed that
#: replaced it imports `cad_build` instead, so this marker tells them apart.
LEGACY_BUILD_MARKER = "def open_document("


def legacy_tool_copies(root: Path) -> list[str]:
    """Per-module copies of tools that now live in the doqs submodule."""
    errors: list[str] = []
    for cad_dir in sorted(root.rglob("cad")):
        if not cad_dir.is_dir():
            continue
        parts = cad_dir.relative_to(root).parts
        if "doqs" in parts or ".agents" in parts:
            continue
        for name, replacement in LEGACY_TOOL_COPIES.items():
            stale = cad_dir / name
            if stale.is_file():
                errors.append(
                    f"{stale.relative_to(root)} is a stale copy of a DOQS tool. "
                    f"Delete it — {replacement} is used automatically."
                )
        build = cad_dir / "build_model.py"
        if build.is_file():
            try:
                body = build.read_text(encoding="utf-8")
            except OSError:
                continue
            if LEGACY_BUILD_MARKER in body:
                errors.append(
                    f"{build.relative_to(root)} still inlines the build scaffolding. "
                    "Re-seed it from doqs/templates/cad/build_model.py, keeping "
                    "your build() body."
                )
    return errors


def dirty_documents(root: Path) -> list[str]:
    """Committed .FCStd files with uncommitted modifications, via git."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", "*.FCStd"],
            cwd=root, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as err:
        return [f"could not run git to check for modified .FCStd files: {err}"]
    if result.returncode != 0:
        return [f"git status failed: {result.stderr.strip()}"]
    return [
        f"{line[3:]} was modified on disk — an agent session should leave .FCStd "
        "files untouched; save deliberately, then commit"
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate FreeCAD documents, fingerprints and the agent-CAD guard."
    )
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--check-clean",
        action="store_true",
        help="Also fail if any .FCStd has uncommitted changes (run after an agent session).",
    )
    args = parser.parse_args()
    root = args.root.resolve() if args.root else repo_root_from_script()
    all_ok = True

    if is_doqs_tools_repo(root):
        print("ok    doqs tools repo (no machine CAD to validate)")
        return 0

    legacy = legacy_tool_copies(root)
    if legacy:
        all_ok = False
        print("FAIL  stale DOQS tool copies")
        for e in legacy:
            print(f"      {e}")
    else:
        print("ok    no stale DOQS tool copies")

    documents = cad_documents(root)

    # No FreeCAD documents means nothing for the guard to protect. Demanding it
    # anyway would fail every consumer repo that has no CAD yet.
    if documents:
        guard_errors = validate_guard(root)
        if guard_errors:
            all_ok = False
            print(f"FAIL  {SETTINGS_PATH}")
            for e in guard_errors:
                print(f"      {e}")
        else:
            print(f"ok    {SETTINGS_PATH} (agent-CAD guard in place)")

    for fcstd in documents:
        rel = fcstd.relative_to(root)
        errs = validate_document(fcstd, root)
        if errs:
            all_ok = False
            print(f"FAIL  {rel}")
            for e in errs:
                print(f"      {e}")
        else:
            print(f"ok    {rel}")
    if not documents:
        print("No .FCStd files found (agent-CAD guard not required yet)")

    if args.check_clean:
        dirty = dirty_documents(root)
        if dirty:
            all_ok = False
            print("FAIL  working tree")
            for e in dirty:
                print(f"      {e}")
        else:
            print("ok    working tree (no modified .FCStd)")

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
