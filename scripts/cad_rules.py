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
import zipfile
import re
import xml.etree.ElementTree as ET
import json
import math
from pathlib import Path

#: Bumped when the on-disk fingerprint layout changes incompatibly.
FINGERPRINT_SCHEMA = 1

FINGERPRINT_SUFFIX = ".fingerprint.json"

#: The build script of one own model in a parts library:
#: `cad/own/<pn>.build.py` builds `cad/own/<pn>.FCStd`. Several own models
#: share one folder, so each script carries the part number in its name.
OWN_BUILD_SUFFIX = ".build.py"

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
    # An origin's point was missing here while its line and its plane were on
    # the list, so every document measured its origin points. A vertex has no
    # mass and nothing worth fingerprinting.
    "App::Point",
    "App::Placement",
    "PartDesign::CoordinateSystem",
    "PartDesign::Line",
    "PartDesign::Plane",
    "PartDesign::Point",
    # The same datums made in a Part container instead of a Body. A mounting
    # frame is one of these.
    "Part::LocalCoordinateSystem",
    "Part::DatumLine",
    "Part::DatumPlane",
    "Part::DatumPoint",
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


def measured_nothing(payload: dict) -> bool:
    """True when every object in a fingerprint run failed to be measured.

    A document with no geometry at all — a spreadsheet, say — measures zero
    objects and reports zero errors, which is correct and must stay quiet. The
    case worth shouting about is zero measured *and* something failed: the file
    then describes no geometry while looking like a finished result. That is how
    the tool wrote empty fingerprints for every real model without anyone
    noticing.
    """
    return not payload.get("objects") and bool(payload.get("errors"))


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


#: An external link inside a FreeCAD document. A .FCStd is a zip whose
#: Document.xml records each link to another document as an XLink with the
#: path it points at. Reading it needs no FreeCAD, which matters because a
#: validator must run in CI where FreeCAD is not installed.
_XLINK_FILE = re.compile(r'<XLink\b[^>]*\bfile="([^"]+)"')


def document_links(fcstd: Path) -> list[str]:
    """Paths this document links to, as written inside it.

    Returns an empty list for a file that is not a readable FreeCAD document,
    so a stub or a partial download reports "links to nothing" rather than
    crashing a gate.
    """
    try:
        with zipfile.ZipFile(fcstd) as archive:
            xml = archive.read("Document.xml").decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, KeyError, OSError):
        return []
    return _XLINK_FILE.findall(xml)


def links_resolve_to(fcstd: Path, target: Path) -> bool:
    """True when this document links the given file.

    Link paths are written relative to the document, and FreeCAD is configured
    to keep them that way so a clone elsewhere still resolves.
    """
    target = target.resolve()
    for link in document_links(fcstd):
        try:
            if (fcstd.parent / link).resolve() == target:
                return True
        except OSError:
            continue
    return False


#: The container an Assembly inserts and places. A part document keeps its
#: Bodies inside one, so the top object of the tree is a Part, not a Body.
PART_TYPE = "App::Part"
BODY_TYPE = "PartDesign::Body"

#: An assembly document is exempt: its master sketches live in a Body inside a
#: plain Group. See docs/decisions/2026-06-24_freecad-master-sketches-body.md.
ASSEMBLY_TYPE = "Assembly::AssemblyObject"

#: A mounting frame: a named coordinate system inside a part's Part container.
#: Assembly joints attach to these, never to a face, an edge or a point.
#: See docs/decisions/2026-10-06_joints-attach-to-frames.md.
FRAME_TYPE = "Part::LocalCoordinateSystem"

#: A solid that came from a supplier's STEP file, as the GUI importer makes it.
IMPORTED_SOLID_TYPE = "Part::Feature"

#: Objects a person must see when a build creates them: the part, its Body,
#: the assembly, the links an assembly uses to hold its parts, an imported
#: solid, and a mounting frame. A headless build writes no view data, so
#: without this they open hidden.
SHOWN_TYPES = (PART_TYPE, BODY_TYPE, ASSEMBLY_TYPE, "App::Link", IMPORTED_SOLID_TYPE, FRAME_TYPE)

#: The coordinate system of a Part, a Body or an Assembly: its axes, planes and
#: point. FreeCAD keeps them hidden, and so does a build.
ORIGIN_TYPES = ("App::Origin", "App::Line", "App::Plane", "App::Point")


def visibility_for(type_id: str):
    """True to show a new object, False to hide it, None to leave it as it is.

    None covers sketches and in-between features, which FreeCAD hides on
    purpose once a later feature uses them.
    """
    if type_id in SHOWN_TYPES:
        return True
    if type_id in ORIGIN_TYPES:
        return False
    return None


def bodies_outside_part(objects) -> list[str]:
    """Bodies that no Part container holds, in document order.

    ``objects`` is a list of ``(name, type_id, children)``, where ``children``
    are the names in that object's ``Group`` property. The walk goes down from
    every Part through nested groups, so a Body in a Group inside a Part counts
    as held. An assembly document returns nothing.
    """
    objects = list(objects)
    if any(type_id == ASSEMBLY_TYPE for _, type_id, _ in objects):
        return []
    children = {name: list(kids) for name, _, kids in objects}
    held: set[str] = set()
    stack = [name for name, type_id, _ in objects if type_id == PART_TYPE]
    while stack:
        name = stack.pop()
        for child in children.get(name, []):
            if child not in held:
                held.add(child)
                stack.append(child)
    return [
        name for name, type_id, _ in objects
        if type_id == BODY_TYPE and name not in held
    ]


def document_tree(fcstd: Path) -> list[tuple[str, str, list[str]]]:
    """``(name, type_id, children)`` for every object in a saved document.

    Read from Document.xml, so no FreeCAD is needed. Returns an empty list for
    a file that is not a readable FreeCAD document, like ``document_links``.
    """
    try:
        with zipfile.ZipFile(fcstd) as archive:
            root = ET.fromstring(archive.read("Document.xml"))
    except (zipfile.BadZipFile, KeyError, OSError, ET.ParseError):
        return []
    groups: dict[str, list[str]] = {}
    for obj in root.findall("./ObjectData/Object"):
        for prop in obj.findall("./Properties/Property"):
            if prop.get("name") == "Group":
                groups[obj.get("name", "")] = [
                    link.get("value", "") for link in prop.iter("Link")
                ]
    return [
        (obj.get("name", ""), obj.get("type", ""), groups.get(obj.get("name", ""), []))
        for obj in root.findall("./Objects/Object")
    ]


def _object_data(fcstd: Path):
    """``(types by name, ObjectData elements)`` of a saved document, or ``None``."""
    try:
        with zipfile.ZipFile(fcstd) as archive:
            root = ET.fromstring(archive.read("Document.xml"))
    except (zipfile.BadZipFile, KeyError, OSError, ET.ParseError):
        return None
    types = {obj.get("name", ""): obj.get("type", "") for obj in root.findall("./Objects/Object")}
    return types, root.findall("./ObjectData/Object")


def object_labels(fcstd: Path) -> dict[str, str]:
    """``{object name: label}`` for every object in a saved document.

    A joint stores the internal name of the frame it uses (``Frame001``), and
    the rule names its label (``IF_rail_reference``). This is the bridge.
    An object with no saved label keeps its name. Empty for an unreadable file.
    """
    data = _object_data(fcstd)
    if data is None:
        return {}
    _, objects = data
    return {
        obj.get("name", ""): _property_value(obj, "Label") or obj.get("name", "")
        for obj in objects
    }


def frames(fcstd: Path) -> list[tuple[str, str]]:
    """``(name, label)`` of every mounting frame in a saved document, in order."""
    data = _object_data(fcstd)
    if data is None:
        return []
    types, objects = data
    return [
        (obj.get("name", ""), _property_value(obj, "Label") or obj.get("name", ""))
        for obj in objects
        if types.get(obj.get("name", "")) == FRAME_TYPE
    ]


def link_targets(fcstd: Path) -> dict[str, str]:
    """``{link object name: path it links to}`` for every App::Link in a document.

    An assembly holds each part as a link. The path is written relative to the
    assembly, as FreeCAD saved it. Empty for an unreadable file.
    """
    data = _object_data(fcstd)
    if data is None:
        return {}
    _, objects = data
    found: dict[str, str] = {}
    for obj in objects:
        for prop in obj.findall("./Properties/Property"):
            if prop.get("name") != "LinkedObject":
                continue
            for link in prop.iter("XLink"):
                if link.get("file"):
                    found[obj.get("name", "")] = link.get("file", "")
    return found


def joint_targets(fcstd: Path) -> list[tuple[str, str, str, str]]:
    """``(joint label, reference property, link name, sub-name)`` per reference.

    Like ``joint_references``, plus the name of the object the reference
    starts from: the App::Link that holds the part in the assembly, or an
    object of the assembly itself. ``resolve_joint_target`` turns the pair into
    a file and an object name.
    """
    data = _object_data(fcstd)
    if data is None:
        return []
    _, objects = data
    found: list[tuple[str, str, str, str]] = []
    for obj in objects:
        props = {p.get("name"): p for p in obj.findall("./Properties/Property")}
        if "JointType" not in props:
            continue
        label = _property_value(obj, "Label") or obj.get("name", "")
        for ref in JOINT_REFERENCES:
            prop = props.get(ref)
            if prop is None:
                continue
            for link in prop.iter("XLink"):
                subs = [link.get("sub")] if link.get("sub") is not None else []
                subs += [sub.get("value", "") for sub in link.iter("Sub")]
                found.extend((label, ref, link.get("name", ""), sub) for sub in subs)
    return found


def resolve_joint_target(assembly: Path, link_name: str, sub: str) -> tuple[Path, str]:
    """The file and the object name a joint reference ends on.

    ``Frame001.XY_Plane003.`` on the link ``base`` means object ``Frame001``
    in the file that ``base`` links to. A reference to an object of the
    assembly itself (no link) resolves to the assembly file. Nothing is read
    from the target file here, so the result may name a file that is missing.
    """
    first = sub.split(".", 1)[0] if sub else ""
    target = link_targets(assembly).get(link_name)
    if target is None:
        return Path(assembly), first or link_name
    return (Path(assembly).parent / target), first


def is_assembly_path(fcstd: Path) -> bool:
    """True when the document lives under a ``cad/assemblies/`` folder."""
    parts = Path(fcstd).parts
    return any(
        a == "cad" and b == "assemblies" for a, b in zip(parts, parts[1:])
    )


def cad_documents(root: Path) -> list[Path]:
    """Every committed `.FCStd` that this repository is responsible for.

    Skips the tooling submodules, and skips a mounted parts library: those
    documents were built from files a brand published, so there is no
    build_model.py to rebuild them from and no fingerprint to keep current.
    Their integrity is proved by the checksum in the library's own manifest.
    """
    from naming_rules import is_under_parts_library, is_under_tooling_submodule

    return [
        p
        for p in sorted(root.rglob("*.FCStd"))
        if not is_under_tooling_submodule(p, root)
        and not is_under_parts_library(p, root)
    ]


#: Every mounting frame label starts with this, like ``IF_mount_bottom``.
FRAME_PREFIX = "IF_"

#: The two references of an Assembly joint (FreeCAD 1.1, JointObject.py).
JOINT_REFERENCES = ("Reference1", "Reference2")

#: The last part of a reference that names one face, edge or point of a solid.
#: FreeCAD numbers these again when a feature changes, so the joint can move to
#: the wrong face, or lose its face, without any error.
_TOPOLOGY_ELEMENT = re.compile(r"^(Face|Edge|Vertex)\d+$")


def _property_value(obj, name: str) -> str:
    for prop in obj.findall("./Properties/Property"):
        if prop.get("name") == name:
            for child in prop:
                return child.get("value", "")
    return ""


def joint_references(fcstd: Path) -> list[tuple[str, str, str]]:
    """``(joint label, reference property, sub-name)`` for every joint reference.

    Read from Document.xml, so no FreeCAD is needed. A joint is any object
    with a ``JointType`` and a ``Reference1`` or ``Reference2``. A sub-name
    reads like ``Body.Pad.Face6``, ``IF_mount.`` or ``IF_mount.X_Axis``.
    Returns an empty list for a file that is not a readable FreeCAD document.
    """
    try:
        with zipfile.ZipFile(fcstd) as archive:
            root = ET.fromstring(archive.read("Document.xml"))
    except (zipfile.BadZipFile, KeyError, OSError, ET.ParseError):
        return []
    found: list[tuple[str, str, str]] = []
    for obj in root.findall("./ObjectData/Object"):
        props = {p.get("name"): p for p in obj.findall("./Properties/Property")}
        if "JointType" not in props:
            continue
        label = _property_value(obj, "Label") or obj.get("name", "")
        for ref in JOINT_REFERENCES:
            prop = props.get(ref)
            if prop is None:
                continue
            for link in prop.iter("XLink"):
                subs = [link.get("sub")] if link.get("sub") is not None else []
                subs += [sub.get("value", "") for sub in link.iter("Sub")]
                found.extend((label, ref, sub) for sub in subs)
    return found


def is_topology_reference(sub: str) -> bool:
    """True when a joint sub-name ends on a face, an edge or a point."""
    return bool(_TOPOLOGY_ELEMENT.match(sub.rsplit(".", 1)[-1]))


def joints_on_topology(references) -> list[str]:
    """One line per joint reference that uses a face, an edge or a point.

    ``references`` is what ``joint_references`` returns. Each joint is named
    once per reference, even when FreeCAD stores a face and one of its points.
    """
    out: list[str] = []
    for label, ref, sub in references:
        if not is_topology_reference(sub):
            continue
        line = f"joint {label!r} {ref} uses {sub}"
        if not any(o.startswith(f"joint {label!r} {ref} ") for o in out):
            out.append(line)
    return out
