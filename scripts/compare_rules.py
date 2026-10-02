"""Turn measurements of two models into words, with no numbers in them.

`doqs compare-own` compares a model we drew with the brand's own model. The
brand's numbers may not enter our files, our logs or our screen. So these
functions run inside the FreeCAD process that measures both models, and they
hand back only verdicts and words: pass, fail, not-confirmed, an axis name, a
plane name, a side. Nothing here returns a number.

They import nothing from FreeCAD, so the test suite runs them as plain Python.
A box is `[xmin, ymin, zmin, xmax, ymax, zmax]`; a centre is `[x, y, z]`.
"""
from __future__ import annotations

AXES = ("X", "Y", "Z")

#: A mirror plane through the origin, and the axis it flips.
PLANES = {"YZ": 0, "XZ": 1, "XY": 2}

#: Below this share of common volume, two models are not in the same place.
OVERLAP_SAME_PLACE = 0.9


def extents(box: list[float]) -> list[float]:
    return [box[i + 3] - box[i] for i in range(3)]


def extent_verdicts(own: list[float], brand: list[float], tol: float) -> dict[str, str]:
    """Per axis: pass when the sizes agree.

    Ours smaller is a fail: something of theirs is missing and could collide.
    Ours larger is not-confirmed: an estimate on the large side is the safe
    side, but it is still an estimate.
    """
    result = {}
    for axis, mine, theirs in zip(AXES, extents(own), extents(brand)):
        if abs(mine - theirs) <= tol:
            result[axis] = "pass"
        elif mine < theirs:
            result[axis] = "fail"
        else:
            result[axis] = "not-confirmed"
    return result


def axes_and_origin(own: list[float], brand: list[float], overlap: float, tol: float) -> tuple[bool, str]:
    """Do both models use the same axes and origin? `(same, words)`."""
    same_box = all(abs(a - b) <= tol for a, b in zip(own, brand))
    if same_box or overlap >= OVERLAP_SAME_PLACE:
        return True, "same axes and origin"
    mine, theirs = extents(own), extents(brand)
    order_mine = sorted(range(3), key=lambda i: mine[i])
    order_theirs = sorted(range(3), key=lambda i: theirs[i])
    if order_mine != order_theirs:
        longest = AXES[order_theirs[-1]]
        return False, (
            f"different axes: the brand model is longest along {longest}, ours "
            f"along {AXES[order_mine[-1]]}. Turn ours to match.")
    return False, (
        "same axes, but the origin is in a different place: the two models "
        "hardly overlap. Move ours to the brand's origin.")


def symmetry_planes(box: list[float], centre: list[float] | None, tol: float) -> list[str]:
    """Mirror planes through the origin that the box and the centre allow.

    A necessary test, not a full one: a part can pass it and still not be
    symmetric in its details.
    """
    planes = []
    for name, axis in PLANES.items():
        balanced = abs(box[axis] + box[axis + 3]) <= tol
        centred = centre is None or abs(centre[axis]) <= tol
        if balanced and centred:
            planes.append(name)
    return planes


def symmetry_verdict(claim: str, own: list[str], brand: list[str]) -> str:
    """The result of one `symmetry <claim>` row."""
    if claim == "none":
        return "pass" if not brand and not own else "fail"
    return "pass" if claim in brand and claim in own else "fail"


def protrusion_sides(own: list[float], pieces: list[list[float]], tol: float) -> list[list[str]]:
    """For each brand piece missing in ours: the sides where it sticks out.

    A piece inside our envelope is left out: the question is what could collide.
    """
    found = []
    for piece in pieces:
        sides = []
        for i, axis in enumerate(AXES):
            if piece[i] < own[i] - tol:
                sides.append(f"-{axis}")
            if piece[i + 3] > own[i + 3] + tol:
                sides.append(f"+{axis}")
        if sides:
            found.append(sides)
    return found


def verdicts(*, own_box, own_centre, brand_box, brand_centre, overlap, missing, tol) -> dict:
    """Everything `compare-own` may know, as words. No number leaves here."""
    same, axes_words = axes_and_origin(own_box, brand_box, overlap, tol)
    return {
        "envelope": extent_verdicts(own_box, brand_box, tol),
        "same_axes": same,
        "axes": axes_words,
        "symmetry_own": symmetry_planes(own_box, own_centre, tol),
        "symmetry_brand": symmetry_planes(brand_box, brand_centre, tol),
        "protrusions": protrusion_sides(own_box, missing, tol),
    }


def holds_a_number(value) -> bool:
    """True when a result holds a number anywhere. The last guard before use."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, dict):
        return any(holds_a_number(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(holds_a_number(v) for v in value)
    return False
