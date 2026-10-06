"""Is every dimension in a FreeCAD model linked to a reason?

A dimension that is typed in as a number links to nothing. Change the reason
behind it, and nobody knows that this number has to change too. A hole pattern
with seven typed spacings needs seven edits. So DOQS asks two things of every
model:

* **Every sketch is fully constrained.** No point or line is free to move.
* **Every dimension is an expression.** It reads ``Params.<alias>`` from the
  parameter sheet, or a formula of those, or another dimension. The parameter
  file then says where each independent value comes from
  (``param_rules.PARAM_BASES``).

This module holds the rules and works on plain data, so it runs and is tested
without FreeCAD. ``cad_fingerprint.audit()`` reads the objects inside FreeCAD,
passes them here, and writes the result into the fingerprint under
``"parametric"``. ``validate_cad.py`` reads it back without FreeCAD.

See docs/decisions/2026-10-06_every-dimension-has-a-source.md.
"""
from __future__ import annotations

import math

SKETCH_TYPE = "Sketcher::SketchObject"

#: Sketch constraints that carry a number. Every other constraint (coincident,
#: horizontal, equal, symmetric, tangent ...) is a relation, not a dimension.
DIMENSIONAL_CONSTRAINTS = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")

#: Numeric properties of features that set a size, and when each one is in use.
#: A condition ``(property, values)`` means the size counts only while that
#: property holds one of those values: a Pad of type ``ThroughAll`` ignores its
#: ``Length``. ``None`` means always.
#:
#: Check new entries against a real FreeCAD 1.1 document: property names and
#: mode values change between releases.
_LENGTH_TYPES = ("Length", "TwoLengths")
DRIVEN_PROPERTIES: dict[str, tuple[tuple[str, tuple[str, tuple[str, ...]] | None], ...]] = {
    "PartDesign::Pad": (("Length", ("Type", _LENGTH_TYPES)), ("Length2", ("Type", ("TwoLengths",)))),
    "PartDesign::Pocket": (("Length", ("Type", _LENGTH_TYPES)), ("Length2", ("Type", ("TwoLengths",)))),
    "PartDesign::Revolution": (("Angle", None),),
    "PartDesign::Groove": (("Angle", None),),
    "PartDesign::Hole": (("Diameter", ("Threaded", ("False",))), ("Depth", ("DepthType", ("Dimension",)))),
    "PartDesign::Fillet": (("Radius", None),),
    "PartDesign::Chamfer": (("Size", None),),
    "PartDesign::Thickness": (("Value", None),),
    "PartDesign::Draft": (("Angle", None),),
    # FreeCAD 1.1: Mode "Extent" uses the overall Length (Angle); "Spacing" uses
    # the step between two copies, Offset.
    "PartDesign::LinearPattern": (
        ("Occurrences", None), ("Length", ("Mode", ("Extent",))), ("Offset", ("Mode", ("Spacing",)))),
    "PartDesign::PolarPattern": (
        ("Occurrences", None), ("Angle", ("Mode", ("Extent",))), ("Offset", ("Mode", ("Spacing",)))),
    "PartDesign::AdditiveBox": (("Length", None), ("Width", None), ("Height", None)),
    "PartDesign::SubtractiveBox": (("Length", None), ("Width", None), ("Height", None)),
    "PartDesign::AdditiveCylinder": (("Radius", None), ("Height", None)),
    "PartDesign::SubtractiveCylinder": (("Radius", None), ("Height", None)),
    "Part::Box": (("Length", None), ("Width", None), ("Height", None)),
    "Part::Cylinder": (("Radius", None), ("Height", None)),
}

#: Values that are a reason by themselves: nothing, or a full turn.
_SELF_EVIDENT = (0.0, 360.0)

#: Below this, a number counts as zero.
_ZERO = 1e-9


def _key(path: str) -> str:
    """An ExpressionEngine path without its leading dot: ``.Length`` -> ``Length``."""
    return path[1:] if path.startswith(".") else path


def expression_keys(expressions) -> set[str]:
    """The bound property paths of an object, from its ``ExpressionEngine``."""
    return {_key(str(item[0])) for item in expressions or ()}


def _bound(prop: str, keys: set[str]) -> bool:
    """True when the property, or a part of it, holds an expression."""
    return any(k == prop or k.startswith(prop + ".") or k.startswith(prop + "[") for k in keys)


def constraint_bound(index: int, name: str, keys: set[str]) -> bool:
    """True when sketch constraint ``index`` holds an expression.

    FreeCAD stores the path by index (``Constraints[3]``) or, for a named
    constraint, by name (``Constraints.hole_pitch``, quoted as ``<<name>>``
    when the name looks like a unit).
    """
    candidates = {f"Constraints[{index}]"}
    if name:
        candidates |= {f"Constraints.{name}", f"Constraints.<<{name}>>"}
    return bool(candidates & keys)


def _fmt(value: float) -> str:
    return f"{value:g}"


def sketch_findings(constraints: list[dict], keys: set[str], *,
                    dof: int | None, fully_constrained: bool | None) -> list[str]:
    """What is not linked in one sketch.

    ``constraints`` holds one dict per constraint, in sketch order, with
    ``type``, ``name``, ``value``, ``driving`` and ``active``. ``value`` is in
    mm, or in radians for an angle, as FreeCAD stores it.
    """
    findings: list[str] = []
    if fully_constrained is False or (dof is not None and dof > 0):
        left = f"{dof} degrees of freedom left" if dof else "not fully constrained"
        findings.append(f"{left}. Add relations (equal, symmetric, coincident) and "
                        "linked dimensions until nothing can move")
    for index, c in enumerate(constraints):
        if c.get("type") not in DIMENSIONAL_CONSTRAINTS:
            continue
        if not c.get("driving", True) or not c.get("active", True):
            continue  # a reference dimension shows a value; it drives nothing
        value = float(c.get("value") or 0.0)
        if abs(value) < _ZERO:
            continue
        if constraint_bound(index, c.get("name") or "", keys):
            continue
        label = c.get("name") or f"Constraint{index + 1}"
        shown = f"{_fmt(math.degrees(value))} deg" if c["type"] == "Angle" else f"{_fmt(value)} mm"
        findings.append(f"{label} ({c['type']}) is a typed number: {shown}")
    return findings


def _condition_holds(condition, props: dict) -> bool:
    if condition is None:
        return True
    name, allowed = condition
    if name not in props:
        return True
    return str(props[name]) in allowed


def feature_findings(type_id: str, props: dict, keys: set[str]) -> list[str]:
    """What is not linked in one feature.

    ``props`` maps property names to plain values: numbers for sizes, strings
    for modes. A property the feature does not have is skipped.
    """
    findings: list[str] = []
    for prop, condition in DRIVEN_PROPERTIES.get(type_id, ()):
        if prop not in props or not _condition_holds(condition, props):
            continue
        value = props[prop]
        if not isinstance(value, (int, float)) or abs(float(value)) in _SELF_EVIDENT:
            continue
        if prop == "Occurrences" and value == 1:
            continue  # one copy is no pattern
        if _bound(prop, keys):
            continue
        findings.append(f"{prop} is a typed number: {_fmt(float(value))}")
    return findings


def placement_findings(prop: str, base: tuple[float, float, float], angle: float,
                       keys: set[str]) -> list[str]:
    """A sketch or datum moved away from its support by a typed offset.

    ``prop`` is ``AttachmentOffset`` for an attached object and ``Placement``
    for a free one. ``angle`` is in radians.
    """
    moved = any(abs(v) > _ZERO for v in base) or abs(angle) > _ZERO
    if not moved or _bound(prop, keys):
        return []
    x, y, z = base
    return [f"{prop} is typed: ({_fmt(x)}, {_fmt(y)}, {_fmt(z)}) mm, "
            f"{_fmt(math.degrees(angle))} deg"]


def problems(parametric: dict | None) -> list[str]:
    """The fingerprint's ``parametric`` section as one line per finding."""
    if not parametric:
        return []
    out = []
    for name, entry in sorted((parametric.get("objects") or {}).items()):
        for finding in entry.get("unlinked") or []:
            out.append(f"{entry.get('label') or name}: {finding}")
    return out
