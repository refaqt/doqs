"""Rules for taking a supplier's files into a parts library.

A brand's files arrive in two kinds: geometry (`cad`) and paper
(`documentation`: datasheets, manuals, drawings). The two often come under
different terms, so each kind gets its own decision. A decision is a
``[[terms-review]]`` entry in the brand's ``okh.toml``:

    [[terms-review]]
    kind     = "cad"            # cad | documentation
    decision = "public"         # public | customers | internal
    basis    = "terms"          # terms | permission | none
    source   = "https://..."    # the terms page, or who gave the permission
    evidence = "evidence/..."   # the saved copy, a path in the private library
    reviewer = "A. Person"      # the named person who approved it
    reviewed = 2026-09-29

Reviews are never edited or deleted. When terms change, add a new entry; the
newest one for a kind is the one that counts. See
docs/decisions/2026-09-29_component-intake.md.
"""
from __future__ import annotations

import datetime
import re
import tomllib
from pathlib import Path

REVIEW_KINDS = ("cad", "documentation")
REVIEW_DECISIONS = ("public", "customers", "internal")
REVIEW_BASES = ("terms", "permission", "none")

#: `terms` values in vendor-index.csv. `private` means there is no public
#: address: the only copy is in the private library.
VENDOR_TERMS = ("redistributable", "fetch-only", "private")
#: Terms whose file is not committed. A missing file is then normal.
NOT_COMMITTED = ("fetch-only", "private")
#: `terms` values in bom/parts.csv. `own-model` is a model we drew ourselves
#: from the datasheet, under `cad/own/`, so it is ours and always committed.
PARTS_TERMS = VENDOR_TERMS + ("own-model",)

#: Our own models live here, inside a family's `cad/`. They carry CC BY-SA,
#: not the brand's terms.
OWN_MODEL_DIR = "own"
#: Where a value came from. `catalogue`: a size printed in the brand's table
#: or drawing. `estimated`: read off a figure, so only a placeholder.
#: `measured`: measured on a real part, by a named person on a date.
VALUE_BASES = ("catalogue", "estimated", "measured")

#: The clean-room record next to every own model.
CHECKS_SUFFIX = ".checks.csv"
CHECKS_HEADERS = (
    "dimension", "value_mm", "basis", "source", "page", "measured_by",
    "measured_utc", "method", "result", "checked_utc",
)
CHECK_RESULTS = ("pass", "fail", "not-confirmed")

#: The values an own model's build script reads: `cad/own/<pn>.params.csv`.
OWN_PARAMS_SUFFIX = ".params.csv"
OWN_PARAMS_HEADERS = (
    "alias", "value", "unit", "basis", "source", "page", "measured_by",
    "measured_utc", "description",
)

#: Every feature of the part, listed before anything is modelled:
#: `cad/own/<pn>.features.csv`.
FEATURES_SUFFIX = ".features.csv"
FEATURES_HEADERS = (
    "feature", "kind", "outside_envelope", "source", "page", "status", "reason",
)
#: `sized`: the catalogue gives its size. `drawn-unsized`: the figure shows it
#: without a size. `not-drawn`: the text names it, no figure shows it.
FEATURE_KINDS = ("sized", "drawn-unsized", "not-drawn")
FEATURE_STATUS = ("modelled", "estimated", "measured", "left-out")
YES_NO = ("yes", "no")

#: The checks list must hold the overall size along each axis, named
#: `envelope X`, `envelope Y` and `envelope Z`, and at least one symmetry row:
#: `symmetry YZ` (or XZ, XY) for each mirror plane, or `symmetry none`.
ENVELOPE_ROW = re.compile(r"^envelope\s+([XYZ])\b")
SYMMETRY_ROW = re.compile(r"^symmetry\s+(XY|XZ|YZ|none)\b")

#: A method says how something was measured, never what it measured. A number
#: with a unit in it is almost always a value, and maybe the brand's.
_VALUE_IN_TEXT = re.compile(r"\d+(?:[.,]\d+)?\s*(?:mm\b|deg\b|°)")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _empty(row: dict, key: str) -> bool:
    return not (row.get(key) or "").strip()


def basis_problems(label: str, row: dict) -> tuple[list[str], list[str]]:
    """Where one value came from, and whether the row proves it."""
    errors: list[str] = []
    warnings: list[str] = []
    basis = (row.get("basis") or "").strip()
    if basis not in VALUE_BASES:
        return [f"{label}: basis must be one of {VALUE_BASES}, got: {basis!r}"], warnings
    if basis in ("catalogue", "estimated"):
        for key in ("source", "page"):
            if _empty(row, key):
                errors.append(f"{label}: {key} is empty. Name the document and page this value is read from.")
    if basis == "estimated":
        warnings.append(
            f"{label}: estimated from a figure, so only a placeholder. Replace it "
            "with a measurement of a real part or a value from the brand, never "
            "with a value from the brand's CAD file.")
    if basis == "measured":
        if _empty(row, "measured_by"):
            errors.append(f"{label}: measured_by is empty. Name the person who measured the real part.")
        if not _DATE.match((row.get("measured_utc") or "").strip()):
            errors.append(f"{label}: measured_utc must give the date of the measurement, like 2026-10-02.")
    return errors, warnings


def params_problems(rows: list[dict]) -> tuple[list[str], list[str]]:
    """An own model's parameters: each value with its basis."""
    errors: list[str] = []
    warnings: list[str] = []
    for row in rows:
        alias = (row.get("alias") or "").strip()
        if not alias:
            errors.append("a row has no alias")
            continue
        if _empty(row, "value"):
            errors.append(f"{alias}: value is empty")
        e, w = basis_problems(alias, row)
        errors += e
        warnings += w
    return errors, warnings


def features_problems(rows: list[dict]) -> list[str]:
    """The feature inventory: every feature, and what happened to it."""
    if not rows:
        return ["the feature list is empty. List every feature the catalogue "
                "table sizes and every feature the figure shows."]
    errors: list[str] = []
    for n, row in enumerate(rows, start=1):
        feature = (row.get("feature") or "").strip()
        if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
            errors.append(f"row {n} is empty. Remove it or fill it in.")
            continue
        label = feature or f"row {n}"
        for key in FEATURES_HEADERS[:-1]:
            if _empty(row, key):
                errors.append(f"{label}: {key} is empty")
        kind = (row.get("kind") or "").strip()
        outside = (row.get("outside_envelope") or "").strip()
        status = (row.get("status") or "").strip()
        if kind and kind not in FEATURE_KINDS:
            errors.append(f"{label}: kind must be one of {FEATURE_KINDS}, got: {kind!r}")
        if outside and outside not in YES_NO:
            errors.append(f"{label}: outside_envelope must be yes or no, got: {outside!r}")
        if status and status not in FEATURE_STATUS:
            errors.append(f"{label}: status must be one of {FEATURE_STATUS}, got: {status!r}")
        if status == "left-out" and _empty(row, "reason"):
            errors.append(f"{label}: left out without a reason. Say why in reason.")
        if status == "left-out" and outside == "yes":
            errors.append(
                f"{label}: sticks out of the main shape, so it may never be left "
                "out. An assembly would miss the collision. Model it, from an "
                "estimate on the large side if there is no size.")
        if kind == "drawn-unsized" and status == "modelled":
            errors.append(
                f"{label}: the catalogue gives no size, so the model holds an "
                "estimate or a measurement. Set status to estimated or measured.")
    return errors


def checks_problems(rows: list[dict]) -> tuple[list[str], list[str]]:
    """The comparison record of an own model. Never holds a brand value."""
    errors: list[str] = []
    warnings: list[str] = []
    if not rows:
        # A list that checks nothing proves nothing.
        return ["the check list has no dimensions"], warnings
    axes = set()
    symmetry = False
    for row in rows:
        dim = (row.get("dimension") or "").strip()
        envelope = ENVELOPE_ROW.match(dim)
        if envelope:
            axes.add(envelope.group(1))
        is_symmetry = bool(SYMMETRY_ROW.match(dim))
        symmetry = symmetry or is_symmetry
        result = (row.get("result") or "").strip()
        method = (row.get("method") or "").strip()
        if result not in CHECK_RESULTS:
            errors.append(f"{dim}: result must be one of {CHECK_RESULTS}")
        elif result == "fail":
            errors.append(
                f"{dim}: the model does not match. Read the drawing again and fix the "
                "value from the datasheet, never from the brand's model.")
        elif result == "not-confirmed":
            warnings.append(f"{dim}: not confirmed yet")
        if result == "pass" and not method:
            errors.append(
                f"{dim}: pass without a method. Say in words how it was measured on "
                "both models, so someone else can repeat it.")
        if _VALUE_IN_TEXT.search(method):
            errors.append(
                f"{dim}: the method holds a value. Describe how it was measured, "
                "never what was measured: a brand value may not enter this file.")
        value = (row.get("value_mm") or "").strip()
        if not value or (value == "-" and not is_symmetry):
            errors.append(f"{dim}: value_mm is empty")
        e, w = basis_problems(dim, row)
        errors += e
        warnings += w
    missing = [axis for axis in "XYZ" if axis not in axes]
    if missing:
        errors.append(
            "the check list has no " + ", ".join(f"'envelope {a}'" for a in missing)
            + " row. Check the overall size along each axis as the catalogue "
            "defines it, for example a block length with its end seals.")
    if not symmetry:
        errors.append(
            "the check list has no symmetry row. Add 'symmetry YZ' (or XZ, XY) for "
            "each mirror plane of the part, or 'symmetry none'.")
    return errors, warnings


def kind_of(relpath: str) -> str | None:
    """Which review covers a file, from its path inside a module."""
    parts = Path(relpath).parts
    if not parts:
        return None
    if parts[0] == "cad":
        return "cad"
    if parts[0] == "docs":
        return "documentation"
    return None


def brand_dir_of(path: Path, root: Path) -> Path | None:
    """The brand folder a library file belongs to: `modules/<brand>/`.

    A brand sits directly under the library's `modules/`, and nowhere else,
    so this looks there only.
    """
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return None
    if len(parts) < 3 or parts[0] != "modules":
        return None
    return root / parts[0] / parts[1]


def reviews_of(data: dict) -> list[dict]:
    reviews = data.get("terms-review", [])
    return reviews if isinstance(reviews, list) else []


def latest_review(brand_okh: Path, kind: str) -> dict | None:
    """The newest review of one kind in a brand manifest, or None."""
    if not brand_okh.is_file():
        return None
    with open(brand_okh, "rb") as f:
        return latest_review_of(tomllib.load(f), kind)


def latest_review_of(data: dict, kind: str) -> dict | None:
    """The newest review of one kind in parsed manifest data, or None."""
    found = [r for r in reviews_of(data) if isinstance(r, dict) and r.get("kind") == kind]
    dated = [r for r in found if isinstance(r.get("reviewed"), datetime.date)]
    if not dated:
        return found[-1] if found else None
    return max(dated, key=lambda r: r["reviewed"])


def review_errors(data: dict) -> tuple[list[str], list[str]]:
    """Shape-check every ``[[terms-review]]``. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    raw = data.get("terms-review")
    if raw is None:
        return errors, warnings
    if not isinstance(raw, list):
        return ["terms-review must be a list: write [[terms-review]]"], warnings
    if "brand" not in data:
        errors.append("[[terms-review]] belongs next to a [brand] table")
    for i, review in enumerate(raw, start=1):
        label = f"[[terms-review]] #{i}"
        if not isinstance(review, dict):
            errors.append(f"{label}: must be a table")
            continue
        kind = review.get("kind")
        if kind not in REVIEW_KINDS:
            errors.append(f"{label}: kind must be one of {REVIEW_KINDS}, got: {kind!r}")
        decision = review.get("decision")
        if decision not in REVIEW_DECISIONS:
            errors.append(
                f"{label}: decision must be one of {REVIEW_DECISIONS}, got: {decision!r}")
        basis = review.get("basis")
        if basis not in REVIEW_BASES:
            errors.append(f"{label}: basis must be one of {REVIEW_BASES}, got: {basis!r}")
        if not str(review.get("reviewer", "")).strip():
            errors.append(
                f"{label}: reviewer is missing. A named person approves every decision.")
        if not isinstance(review.get("reviewed"), datetime.date):
            errors.append(f"{label}: reviewed must be a date, like 2026-09-29")
        if basis == "terms" and not review.get("source"):
            errors.append(f"{label}: basis is 'terms', so source must give their address")
        if basis == "permission" and not review.get("evidence"):
            errors.append(
                f"{label}: basis is 'permission', so evidence must name the saved "
                "letter or email in the private library")
        if decision == "public" and basis == "none":
            warnings.append(
                f"{label}: files are public, but nothing allows it (basis = 'none'). "
                "Find the terms or ask the brand for written permission.")
    return errors, warnings
