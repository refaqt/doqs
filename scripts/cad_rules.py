"""Geometric fingerprints and agent-CAD guard rules for FreeCAD documents.

A **fingerprint** is a small JSON file recording what a model measures — bounding
box, volume, area, centre of mass, topology counts — for every shaped object in a
document.  It is written by ``doqs/scripts/cad_fingerprint.py`` (inside FreeCAD) and
read back here, where FreeCAD is not available.

It exists because agents need to check their own work.  A screenshot of a model
costs thousands of tokens and still cannot answer "is this 500 mm long"; a
fingerprint diff costs tens of tokens and answers exactly that.  The same file
doubles as a geometric regression gate: a change that moves a volume by 40%
fails CI whether or not anyone thought to look at the render.

Values are rounded to a fixed significance so OCCT's last-bit variation between
runs and platforms does not produce a diff on every rebuild.  See
``docs/agent-cad.md``.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

#: Bumped when the on-disk fingerprint layout changes incompatibly.
FINGERPRINT_SCHEMA = 1

FINGERPRINT_SUFFIX = ".fingerprint.json"

#: Significant figures kept for every float. OCCT recomputes are not bit-stable
#: across platforms; six figures is far tighter than any real design change and
#: loose enough to absorb that noise.
SIG_FIGURES = 6

#: Magnitudes below this are float noise around zero and snap to 0.0.
ZERO_FLOOR = 1e-9

#: FreeCAD MCP tools that write a `.FCStd` on disk behind an open GUI document.
#: Denying them by bare name removes them from the agent's context entirely.
#: ``docs/agent-cad.md`` explains why these two and no others.
DENIED_MCP_TOOLS = (
    "mcp__freecad__execute_code_headless",
    "mcp__freecad__reload_document",
)

#: Datum and origin objects carry a Shape but no meaningful geometry.
SKIPPED_TYPE_PREFIXES = (
    "App::Origin",
    "App::Line",
    "App::Plane",
    "App::Placement",
    "PartDesign::CoordinateSystem",
    "PartDesign::Line",
    "PartDesign::Plane",
    "PartDesign::Point",
)


class FingerprintError(Exception):
    """Raised for a malformed, missing, or schema-mismatched fingerprint."""


def round_sig(value: float, sig: int = SIG_FIGURES) -> float:
    """Round to ``sig`` significant figures, snapping float noise to zero."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise FingerprintError(f"not a number: {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise FingerprintError(f"non-finite measurement: {value!r}")
    if abs(value) < ZERO_FLOOR:
        return 0.0
    digits = -int(math.floor(math.log10(abs(value)))) + (sig - 1)
    return round(value, digits)


def normalise(data):
    """Recursively round every float in a fingerprint payload."""
    if isinstance(data, bool) or data is None or isinstance(data, (str, int)):
        return data
    if isinstance(data, float):
        return round_sig(data)
    if isinstance(data, dict):
        return {k: normalise(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [normalise(v) for v in data]
    raise FingerprintError(f"cannot normalise {type(data).__name__}")


def file_digest(path: Path) -> str:
    """SHA-256 of a file, used to tie a fingerprint to the bytes it describes."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(131072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_path(fcstd: Path) -> Path:
    """`cad/rail.FCStd` -> `cad/rail.fingerprint.json`."""
    return fcstd.with_suffix("").with_name(fcstd.stem + FINGERPRINT_SUFFIX)


def write_fingerprint(path: Path, data: dict) -> dict:
    """Normalise and write a fingerprint as stable, diff-friendly JSON."""
    payload = normalise(data)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


def load_fingerprint(path: Path) -> dict:
    """Read a fingerprint, rejecting a layout this DOQS version cannot compare."""
    if not path.is_file():
        raise FingerprintError(f"no fingerprint at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise FingerprintError(f"{path}: invalid JSON ({err})") from err
    if not isinstance(data, dict):
        raise FingerprintError(f"{path}: expected a JSON object")
    schema = data.get("schema")
    if schema != FINGERPRINT_SCHEMA:
        raise FingerprintError(
            f"{path}: schema {schema!r}, expected {FINGERPRINT_SCHEMA}. "
            "Rebuild with cad/build_model.py."
        )
    return data


def _diff_value(label: str, old, new, out: list[str]) -> None:
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new)):
            _diff_value(f"{label}.{key}", old.get(key), new.get(key), out)
        return
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        for i, (o, n) in enumerate(zip(old, new)):
            _diff_value(f"{label}[{i}]", o, n, out)
        return
    if old != new:
        out.append(f"{label}: {old!r} -> {new!r}")


def compare_fingerprints(old: dict, new: dict) -> list[str]:
    """Human-readable differences between two fingerprints.

    The output is what an agent reads instead of a screenshot, so it names the
    object and field that moved rather than dumping both documents.
    """
    diffs: list[str] = []
    old_objs = old.get("objects", {})
    new_objs = new.get("objects", {})
    for name in sorted(set(old_objs) - set(new_objs)):
        diffs.append(f"{name}: removed")
    for name in sorted(set(new_objs) - set(old_objs)):
        diffs.append(f"{name}: added")
    for name in sorted(set(old_objs) & set(new_objs)):
        _diff_value(name, old_objs[name], new_objs[name], diffs)
    _diff_value("params", old.get("params", {}), new.get("params", {}), diffs)
    return diffs


def missing_guard_rules(settings: dict) -> list[str]:
    """Denied MCP tools absent from a parsed `.claude/settings.json`.

    The deny list is what keeps an agent from writing a `.FCStd` behind an open
    GUI document, so its absence is a validation failure, not a warning.
    """
    permissions = settings.get("permissions")
    deny = permissions.get("deny", []) if isinstance(permissions, dict) else []
    present = set(deny) if isinstance(deny, list) else set()
    return [tool for tool in DENIED_MCP_TOOLS if tool not in present]


def hook_is_registered(settings: dict) -> bool:
    """True if `.claude/settings.json` runs a session-start script.

    The hook file on disk does nothing on its own: the settings file is what
    starts it. A repository with the file but no registration looks set up and
    is not, which is the quietest way to lose the tooling submodules.
    """
    hooks = settings.get("hooks")
    entries = hooks.get("SessionStart", []) if isinstance(hooks, dict) else []
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for hook in entry.get("hooks", []):
            if not isinstance(hook, dict):
                continue
            if str(hook.get("command", "")).rstrip().endswith("session-start.sh"):
                return True
    return False


def cad_documents(root: Path) -> list[Path]:
    """Every committed `.FCStd` outside the tooling submodules."""
    from naming_rules import is_under_tooling_submodule

    return [
        p
        for p in sorted(root.rglob("*.FCStd"))
        if not is_under_tooling_submodule(p, root)
    ]
