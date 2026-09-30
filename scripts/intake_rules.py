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
#: The clean-room record next to every own model.
CHECKS_SUFFIX = ".checks.csv"
CHECKS_HEADERS = ("dimension", "value_mm", "source", "page", "result", "checked_utc")
CHECK_RESULTS = ("pass", "fail", "not-confirmed")


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
