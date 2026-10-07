"""Rows, checksums and terms for a parts library, shared by the intake tools.

A library records a part as rows: one in the family's `bom/parts.csv`, and
one per file in `vendor-index.csv`. The private library keeps the same rows
at the same paths. These helpers write those rows so a tool and a person
produce the same text, keep the comment lines in the templates, and refuse
to overwrite a row that is already there. See docs/parts-library.md and
docs/decisions/2026-09-29_component-intake.md.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import io
from pathlib import Path

from intake_rules import NOT_COMMITTED, PARTS_TERMS, VENDOR_TERMS
from naming_rules import PARTS_TABLE_HEADERS, csv_reader_skipping_comments
from validate_variants import VENDOR_INDEX, VENDOR_INDEX_HEADERS, PARTS_TABLE_NAME

#: The `terms` a row carries in a private library for a file we keep.
INTERNAL = "internal"


class LibraryError(ValueError):
    """A row or file that cannot be written as asked."""


def sha256_and_size(path: Path) -> tuple[str, int]:
    """The checksum and the size of a file, as `vendor-index.csv` records them."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(131072), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def utc_now() -> str:
    """The time now, as `retrieved_utc` records it: ``2026-10-07T12:00:00Z``."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> datetime.date:
    return datetime.date.today()


def terms_for(decision: str, *, has_public_url: bool, private_library: bool) -> str:
    """The `terms` a row gets from a brand's decision.

    - ``public``: the file may be shared, so ``redistributable``.
    - Otherwise, in the private library the file is kept: ``internal``.
    - Otherwise the public library keeps the row only: ``fetch-only`` when
      the brand publishes the file at an address, else ``private``.
    """
    if decision == "public":
        return "redistributable"
    if private_library:
        return INTERNAL
    return "fetch-only" if has_public_url else "private"


def is_committed(terms: str) -> bool:
    """True when a file with these terms belongs in git."""
    return terms not in NOT_COMMITTED


def vendor_row(supplier: str, pn: str, relpath: str, file: Path, source_url: str,
               terms: str, retrieved_utc: str | None = None) -> dict:
    """One `vendor-index.csv` row for a file on disk."""
    if terms not in VENDOR_TERMS + (INTERNAL,):
        raise LibraryError(f"terms must be one of {VENDOR_TERMS + (INTERNAL,)}, got {terms!r}")
    digest, size = sha256_and_size(file)
    return {
        "supplier": supplier, "pn": pn, "relpath": relpath, "bytes": str(size),
        "sha256": digest, "source_url": source_url, "terms": terms,
        "retrieved_utc": retrieved_utc or utc_now(),
    }


def parts_row(pn: str, description: str, spec: str = "", unit_mass_g: str = "",
              cad: str = "", datasheet: str = "", terms: str = "fetch-only",
              revision: str = "A", status: str = "active", notes: str = "") -> dict:
    """One `bom/parts.csv` row."""
    if terms not in PARTS_TERMS + (INTERNAL,):
        raise LibraryError(f"terms must be one of {PARTS_TERMS + (INTERNAL,)}, got {terms!r}")
    return {
        "pn": pn, "description": description, "spec": spec, "unit_mass_g": str(unit_mass_g),
        "cad": cad, "datasheet": datasheet, "terms": terms, "revision": revision,
        "status": status, "notes": notes,
    }


def read_rows(path: Path) -> tuple[tuple[str, ...], list[dict]]:
    """The header and the rows of a table, comment lines skipped."""
    if not path.is_file():
        return (), []
    reader = csv_reader_skipping_comments(path.read_text(encoding="utf-8"))
    headers = tuple(h.strip() for h in (reader.fieldnames or []))
    return headers, [dict(r) for r in reader]


def _format_row(headers: tuple[str, ...], row: dict) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerow([row.get(h, "") for h in headers])
    return out.getvalue()


def append_row(path: Path, headers: tuple[str, ...], row: dict, key: str,
               template: str | None = None) -> bool:
    """Add a row to a table. Returns True when it was added.

    A missing table is created from ``template`` (the comment lines and the
    header) or from the header alone. A row with the same ``key`` that says
    the same thing is left alone; one that says something else is refused,
    because rows are never overwritten (add a new row instead).
    """
    key_value = row.get(key, "")
    existing_headers, rows = read_rows(path)
    if existing_headers and existing_headers != headers:
        raise LibraryError(f"{path}: header is {list(existing_headers)}, expected {list(headers)}")
    for old in rows:
        if old.get(key, "") != key_value:
            continue
        if all((old.get(h) or "") == (row.get(h) or "") for h in headers):
            return False
        same_file = old.get("relpath") == row.get("relpath") if "relpath" in headers else True
        if same_file:
            raise LibraryError(
                f"{path}: a row for {key} {key_value!r} exists and says something else. "
                "Rows are never overwritten; add a new row for a new revision.")
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        head = template if template is not None else ",".join(headers) + "\n"
        if not head.endswith("\n"):
            head += "\n"
        path.write_text(head, encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + _format_row(headers, row), encoding="utf-8")
    return True


def set_cell(path: Path, key: str, key_value: str, column: str, value: str) -> bool:
    """Change one cell of one row, keeping comments and other rows as they are.

    Returns True when something changed. Meant for cells that fill in later,
    like `cad` once a wrapper exists. It never changes the key or the terms.
    """
    if column in (key, "terms", "sha256", "bytes"):
        raise LibraryError(f"{column} is never changed in place")
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    headers: list[str] | None = None
    changed = False
    out: list[str] = []
    for line in lines:
        if line.lstrip().startswith("#") or not line.strip():
            out.append(line)
            continue
        fields = next(csv.reader([line]))
        if headers is None:
            headers = [h.strip() for h in fields]
            out.append(line)
            continue
        row = dict(zip(headers, fields))
        if row.get(key) == key_value and row.get(column, "") != value:
            row[column] = value
            out.append(_format_row(tuple(headers), row))
            changed = True
        else:
            out.append(line)
    if headers is None or column not in headers:
        raise LibraryError(f"{path}: no column {column!r}")
    if changed:
        path.write_text("".join(out), encoding="utf-8")
    return changed


def template_text(name: str) -> str:
    """The comment lines and header of a table template in `templates/parts-library/`."""
    root = Path(__file__).resolve().parent.parent / "templates" / "parts-library"
    text = (root / name).read_text(encoding="utf-8")
    kept = []
    for line in text.splitlines(keepends=True):
        kept.append(line)
        if not line.lstrip().startswith("#"):
            break  # the header row; the example rows below it are not copied
    return "".join(kept)


def mirror_diff(public: Path, private: Path) -> list[tuple[str, str]]:
    """``(path, state)`` for every library file both repositories should share.

    State is ``same``, ``differs``, ``only-public`` or ``only-private``. The
    files compared are every manifest and table under ``modules/``, and
    every file a `vendor-index.csv` row names. Paths are relative to the
    library roots, which mirror each other.
    """
    seen: dict[str, tuple[bool, bool]] = {}

    def note(rel: str, side: int) -> None:
        a, b = seen.get(rel, (False, False))
        seen[rel] = (a or side == 0, b or side == 1)

    for side, root in enumerate((public, private)):
        modules = root / "modules"
        if not modules.is_dir():
            continue
        for path in modules.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if path.name in ("okh.toml", VENDOR_INDEX, PARTS_TABLE_NAME):
                note(rel, side)
            if path.name == VENDOR_INDEX:
                for row in read_rows(path)[1]:
                    target = (row.get("relpath") or "").strip()
                    if target:
                        note((path.parent / target).relative_to(root).as_posix(), side)
    out: list[tuple[str, str]] = []
    for rel in sorted(seen):
        a, b = (public / rel).is_file(), (private / rel).is_file()
        if a and b:
            same = sha256_and_size(public / rel) == sha256_and_size(private / rel)
            out.append((rel, "same" if same else "differs"))
        elif a:
            out.append((rel, "only-public"))
        elif b:
            out.append((rel, "only-private"))
    return out


__all__ = [
    "INTERNAL", "LibraryError", "PARTS_TABLE_HEADERS", "VENDOR_INDEX_HEADERS",
    "append_row", "is_committed", "mirror_diff", "parts_row", "read_rows", "set_cell",
    "sha256_and_size", "template_text", "terms_for", "today", "utc_now", "vendor_row",
]
