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

5. **A Part on top.** In a part document every `PartDesign::Body` must sit
   inside an `App::Part` container, so an Assembly can insert and place the
   part as one object. Documents under `cad/assemblies/`, and documents that
   hold an Assembly, are exempt: their master sketches live in a Body inside a
   plain Group (docs/decisions/2026-06-24_freecad-master-sketches-body.md).

6. **A build script that runs headless.** FreeCADCmd 1.1 runs a script with
   `__name__` set to the file name, so a build script that ends with
   `if __name__ == "__main__":` builds nothing and exits 0. It fails here.

7. **Own models in a parts library.** A model under `cad/own/` is our design,
   not a supplier file, so it gets the same checks as a machine part: a build
   script, its parameters, a current fingerprint from a saved build, a Part on
   top, and no backup or cache files in git. Supplier files in the library are
   still checked by their checksums in validate_variants.py instead.

8. **Every dimension is linked.** The fingerprint records each sketch that can
   still move and each size typed in as a number instead of an expression
   over the `Params` sheet. They are warnings, so an older machine repository
   keeps passing when it updates doqs. `--strict-parametric` makes them
   failures. See docs/decisions/2026-10-06_every-dimension-has-a-source.md.

Run from the machine repository root:

    python doqs/scripts/validate_cad.py
    python doqs/scripts/validate_cad.py --check-clean
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import re

from cad_rules import (
    DENIED_MCP_TOOLS,
    OWN_BUILD_SUFFIX,
    FingerprintError,
    bodies_outside_part,
    cad_documents,
    document_tree,
    file_digest,
    fingerprint_path,
    hook_is_registered,
    is_assembly_path,
    load_fingerprint,
    missing_guard_rules,
)
from intake_rules import OWN_MODEL_DIR
import parametric_rules
from license_rules import is_doqs_tools_repo
from naming_rules import (
    is_parts_library,
    is_under_tooling_submodule,
    repo_root_from_script,
)
from validate_variants import git_tracked

SETTINGS_PATH = Path(".claude") / "settings.json"
HOOK_PATH = Path(".claude") / "hooks" / "session-start.sh"


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


def validate_hook_registration(root: Path) -> list[str]:
    """A session hook on disk that nothing starts is worse than no hook.

    Only checked when the file is actually there: a repository that does not use
    the hook is free not to have one.
    """
    if not (root / HOOK_PATH).is_file():
        return []
    settings_file = root / SETTINGS_PATH
    if not settings_file.is_file():
        return [
            f"{HOOK_PATH} exists but {SETTINGS_PATH} does not, so nothing runs it. "
            "Run: python doqs/doqs.py setup"
        ]
    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []  # validate_guard already reports the broken JSON
    if not isinstance(settings, dict) or not hook_is_registered(settings):
        return [
            f"{HOOK_PATH} exists but {SETTINGS_PATH} does not run it, so the tooling "
            "submodules are never checked out. Run: python doqs/doqs.py setup"
        ]
    return []


def validate_part_container(fcstd: Path, root: Path) -> list[str]:
    """Every Body in a part document must sit inside a Part container."""
    rel = fcstd.relative_to(root)
    if is_assembly_path(rel):
        return []
    return [
        f"{rel}: Body {name!r} is not inside a Part container. The top object of "
        "a part must be a Part: add one with the Create part command (Std_Part) "
        "and drag the Body into it, or rebuild with body(doc) from cad_build."
        for name in bodies_outside_part(document_tree(fcstd))
    ]


def validate_document(fcstd: Path, root: Path, build_script: Path | None = None) -> list[str]:
    """Check one .FCStd against its committed fingerprint and its model tree."""
    rel = fcstd.relative_to(root)
    script = build_script or fcstd.parent / "build_model.py"
    rebuild = f"Rebuild with: FreeCADCmd {script.relative_to(root).as_posix()}"
    container_errors = validate_part_container(fcstd, root)
    fp_path = fingerprint_path(fcstd)
    try:
        data = load_fingerprint(fp_path)
    except FingerprintError as err:
        return [f"{err}. {rebuild}"] + container_errors

    errors: list[str] = list(container_errors)
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
            f"measurements describe different geometry. It was saved again after "
            f"its build, by hand or in the GUI. {rebuild}"
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


def parametric_findings(fcstd: Path, root: Path, build_script: Path | None = None) -> list[str]:
    """Free sketches and typed sizes, as the committed fingerprint records them."""
    rel = fcstd.relative_to(root).as_posix()
    try:
        data = load_fingerprint(fingerprint_path(fcstd))
    except FingerprintError:
        return []  # validate_document already says the fingerprint is missing
    if "parametric" not in data:
        script = build_script or fcstd.parent / "build_model.py"
        return [
            f"{rel}: its fingerprint does not record whether every dimension is "
            "linked. It was built with an older doqs. Rebuild with: "
            f"FreeCADCmd {script.relative_to(root).as_posix()}"
        ]
    return [f"{rel}: {line}" for line in parametric_rules.problems(data["parametric"])]


def report_parametric(documents: list[tuple[Path, Path | None]], root: Path, strict: bool) -> bool:
    """Print the linked-dimension findings. False only when strict and any exist."""
    findings = [f for fcstd, script in documents for f in parametric_findings(fcstd, root, script)]
    if not documents:
        return True
    if not findings:
        print("ok    every dimension is linked and every sketch is fully constrained")
        return True
    print(f"{'FAIL' if strict else 'WARN'}  linked dimensions: {len(findings)} findings. "
          "Drive every size from the Params sheet and fully constrain every sketch; "
          "see doqs/docs/agent-cad.md#every-dimension-has-a-reason")
    for line in findings:
        print(f"      {line}")
    return not strict


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
        if is_under_tooling_submodule(cad_dir, root):
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
            else:
                errors.extend(main_guard_errors(build, root))
    return errors


#: The guard FreeCADCmd 1.1 never enters: it sets `__name__` to the file name.
MAIN_GUARD = re.compile(r"""^if\s+__name__\s*==\s*["']__main__["']\s*:""", re.MULTILINE)


def main_guard_errors(script: Path, root: Path) -> list[str]:
    """A build script that FreeCADCmd runs without building anything."""
    try:
        body = script.read_text(encoding="utf-8")
    except OSError:
        return []
    if not MAIN_GUARD.search(body):
        return []
    return [
        f"{script.relative_to(root).as_posix()} starts its build under "
        '`if __name__ == "__main__":`. FreeCADCmd 1.1 sets __name__ to the file '
        "name, so a headless run builds nothing and still exits 0. End the file "
        "with main(build, globals()) instead, as the template does."
    ]


#: A build script for an own model must say which axes and origin it uses.
_AXES = re.compile(r"""^AXES\s*=\s*(["'(].*)$""", re.MULTILINE)


def own_build_script_errors(script: Path, root: Path) -> list[str]:
    """The build script of one own model: present, headless-safe, axes stated."""
    rel = script.relative_to(root).as_posix()
    if not script.is_file():
        return [
            f"{rel} not found. An own model is built by a script, never by hand in "
            "the GUI. Copy doqs/templates/parts-library/cad/own/build.py there."
        ]
    errors = main_guard_errors(script, root)
    body = script.read_text(encoding="utf-8")
    axes = _AXES.search(body)
    if not axes:
        errors.append(
            f"{rel} does not state its axes. Add AXES = \"...\": which way X, Y "
            "and Z point and where the origin is. They must be the same as in the "
            "brand's model, so ours can replace it in an assembly."
        )
    elif "TODO" in axes.group(1):
        errors.append(f"{rel}: AXES still holds the template text. Describe the real axes.")
    return errors


def own_model_documents(root: Path) -> list[Path]:
    """Every `cad/own/<pn>.FCStd` in a parts library."""
    return [
        p for p in sorted(root.rglob(f"cad/{OWN_MODEL_DIR}/*.FCStd"))
        if not is_under_tooling_submodule(p, root)
    ]


def validate_own_model(fcstd: Path, root: Path) -> list[str]:
    """One model we drew ourselves: rebuilt by its script, nothing by hand."""
    pn = fcstd.stem
    script = fcstd.with_name(pn + OWN_BUILD_SUFFIX)
    errors = own_build_script_errors(script, root)
    params = fcstd.with_name(f"{pn}.params.csv")
    if not params.is_file():
        errors.append(
            f"{params.relative_to(root).as_posix()} not found. Every value the "
            "build uses goes there, marked catalogue, estimated or measured. "
            "Copy doqs/templates/parts-library/cad/own/params.csv."
        )
    return errors + validate_document(fcstd, root, build_script=script)


def builds_without_model(root: Path) -> list[str]:
    """An own-model build script whose model was never built and committed."""
    errors = []
    for script in sorted(root.rglob(f"cad/{OWN_MODEL_DIR}/*{OWN_BUILD_SUFFIX}")):
        if is_under_tooling_submodule(script, root):
            continue
        pn = script.name[: -len(OWN_BUILD_SUFFIX)]
        if not script.with_name(f"{pn}.FCStd").is_file():
            errors.append(
                f"{script.relative_to(root).as_posix()}: {pn}.FCStd not found. "
                f"Build it: FreeCADCmd {script.relative_to(root).as_posix()}"
            )
    return errors


def tracked_junk(root: Path) -> list[str]:
    """FreeCAD backups and Python caches that git tracks. Neither belongs there."""
    tracked = git_tracked(root)
    if tracked is None:
        return []
    return [
        f"{path} is tracked by git. Run: git rm --cached \"{path}\", and keep "
        "*.FCBak and __pycache__/ in .gitignore"
        for path in sorted(tracked)
        if path.endswith(".FCBak") or "__pycache__" in path.split("/")
    ]


def validate_parts_library(root: Path, strict_parametric: bool = False) -> bool:
    """Our own models in a library. Supplier files are checked by checksum."""
    all_ok = True
    for fcstd in own_model_documents(root):
        rel = fcstd.relative_to(root).as_posix()
        errs = validate_own_model(fcstd, root)
        if errs:
            all_ok = False
            print(f"FAIL  {rel}")
            for e in errs:
                print(f"      {e}")
        else:
            print(f"ok    {rel}")
    for label, errs in (
        ("own-model build scripts", builds_without_model(root)),
        ("files tracked by git", tracked_junk(root)),
    ):
        if errs:
            all_ok = False
            print(f"FAIL  {label}")
            for e in errs:
                print(f"      {e}")
    own = [(f, f.with_name(f.stem + OWN_BUILD_SUFFIX)) for f in own_model_documents(root)]
    if not report_parametric(own, root, strict_parametric):
        all_ok = False
    print("ok    parts library: supplier files are checked by their checksums")
    return all_ok


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
    parser.add_argument(
        "--strict-parametric",
        action="store_true",
        help="Fail, not warn, on a free sketch or a size typed in as a number.",
    )
    args = parser.parse_args()
    root = args.root.resolve() if args.root else repo_root_from_script()
    all_ok = True

    if is_doqs_tools_repo(root):
        print("ok    doqs tools repo (no machine CAD to validate)")
        return 0

    # A parts library mostly holds documents built from files brands published.
    # There is no build script behind them, and every committed file already
    # carries a byte-exact checksum in vendor-index.csv, which
    # validate_variants.py compares (docs/decisions/2026-09-18_parts-library.md).
    # Our own models under cad/own/ are different: they are our designs, and
    # skipping them let a re-saved model through unnoticed.
    # See docs/mistakes/2026-10-02_own-models-were-not-checked.md.
    if is_parts_library(root):
        return 0 if validate_parts_library(root, args.strict_parametric) else 1

    legacy = legacy_tool_copies(root)
    if legacy:
        all_ok = False
        print("FAIL  stale DOQS tool copies")
        for e in legacy:
            print(f"      {e}")
    else:
        print("ok    no stale DOQS tool copies")

    # Unlike the guard below, this does not wait for a .FCStd: a hook nothing
    # runs costs you the tooling submodules, CAD or no CAD.
    hook_errors = validate_hook_registration(root)
    if hook_errors:
        all_ok = False
        print(f"FAIL  {HOOK_PATH}")
        for e in hook_errors:
            print(f"      {e}")

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
    if not report_parametric([(f, None) for f in documents], root, args.strict_parametric):
        all_ok = False
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
