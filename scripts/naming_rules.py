"""Shared naming conventions for DOQS validators and tests."""
from __future__ import annotations

import csv
import io
import re
from functools import lru_cache
from pathlib import Path

MODULE_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ADAPTER_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*-to-[a-z0-9]+(-[a-z0-9]+)*$")
BOM_ID = re.compile(r"^([A-Z]{2,4})-([0-9]{3})$")
MODEL_SLUG = MODULE_SLUG
#: Commercial catalogue id, e.g. ALS-SL-500. Uppercase so it never reads
#: like a module slug: folder names stay functional, SKUs stay commercial.
SKU_ID = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)*$")
OKH_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
GIT_TAG = re.compile(
    r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)

BOM_PREFIXES = frozenset({
    "MEC",
    "STD",
    "ELC",
    "SW",
    "MOT",
    "HW",
    "PRF",
    "BRK",
})

# Design data only. What a part costs is answered by a different system, which
# joins on `part` (or on `brand` + `brand_pn` where there is no library entry).
# See docs/decisions/2026-09-18_money-out-of-the-bom.md.
BOM_HEADERS = (
    "id",
    "name",
    "spec",
    "category",
    "qty",
    "unit",
    "unit_mass_g",
    "equiv_class",
    "brand",
    "brand_pn",
    "part",
    "notes",
)

# The header used before 2026-09-18. Kept so validate_names.py can recognise a
# file that has not migrated yet and say what to do, instead of only reporting
# that the columns are wrong.
LEGACY_BOM_HEADERS = (
    "id",
    "name",
    "spec",
    "category",
    "qty",
    "unit",
    "unit_cost_eur",
    "unit_mass_g",
    "equiv_class",
    "supplier_1",
    "supplier_1_pn",
    "supplier_2",
    "supplier_2_pn",
    "supplier_3",
    "supplier_3_pn",
    "notes",
)

# Columns that left the bill of materials, and where the first two went.
# supplier_1 held a brand in practice -- our own fixtures wrote HIWIN there --
# which is the confusion the decision record is about.
BOM_COLUMNS_REMOVED = (
    "unit_cost_eur",
    "supplier_1",
    "supplier_1_pn",
    "supplier_2",
    "supplier_2_pn",
    "supplier_3",
    "supplier_3_pn",
)
BOM_COLUMNS_RENAMED = {
    "supplier_1": "brand",
    "supplier_1_pn": "brand_pn",
}

# A reference into a parts library: <library>:<family path>#<part number>.
LIBRARY_PART_REF = re.compile(
    r"^[a-z0-9]+(-[a-z0-9]+)*:"          # library name, e.g. stoq
    r"[a-z0-9]+(-[a-z0-9]+)*"            # brand
    r"(/[a-z0-9]+(-[a-z0-9]+)*)*"        # family, and any deeper nesting
    r"#[^\s]+$"                          # the brand's own part number, verbatim
)

#: Marks a repository as a parts library: parts other people make, which we
#: only record. It is the marker and not the mount path that identifies one, so
#: a machine may mount a library anywhere under modules/ and still skip it.
#: See docs/decisions/2026-09-18_parts-library.md.
LIBRARY_MARKER = "library.toml"

#: One row per orderable part number, in a library family's bom/parts.csv.
#: No price and no distributor: a library is technical. See ADR-006.
PARTS_TABLE_HEADERS = (
    "pn",
    "description",
    "spec",
    "unit_mass_g",
    "cad",
    "datasheet",
    "terms",
    "revision",
    "status",
    "notes",
)

#: What a library row's `status` may say. A part you can no longer buy is
#: marked, never deleted: an existing machine is still made of it.
PARTS_STATUS = ("active", "eol")


def csv_reader_skipping_comments(text: str) -> "csv.DictReader":
    """A CSV reader over `text` with leading `#` comment lines removed.

    Every table a person edits by hand ships as a template with comments
    explaining what to write. Feeding those straight to csv.DictReader makes
    the first comment the header row, and the failure then blames the header
    rather than the comment. Strip them once, here, so the templates can be
    copied as they are.
    """
    lines = text.splitlines(keepends=True)
    body = "".join(line for line in lines if not line.lstrip().startswith("#"))
    return csv.DictReader(io.StringIO(body))


def is_parts_library(root: Path) -> bool:
    """True when `root` is a parts-library repository."""
    return (root / LIBRARY_MARKER).is_file()


@lru_cache(maxsize=None)
def _library_roots_cached(root: Path) -> tuple[Path, ...]:
    """Cached because callers ask once per manifest.

    Without this the cost is manifests x paths: a validator walks the whole
    tree again for every okh.toml it checks, which is seconds on a fixture and
    minutes on a real library. Validators are read-only single passes, so the
    set of mounted libraries cannot change underneath a run. A test that mounts
    a library after calling this must clear the cache.
    """
    found: list[Path] = []
    for marker in sorted(root.rglob(LIBRARY_MARKER)):
        if marker.parent == root:
            continue
        found.append(marker.parent.resolve())
    return tuple(found)


def library_roots(root: Path) -> list[Path]:
    """Every parts library mounted under `root`, at any depth."""
    return list(_library_roots_cached(root.resolve()))


def forget_library_roots() -> None:
    """Drop the cache above. For tests that change a tree between calls."""
    _library_roots_cached.cache_clear()


def is_under_parts_library(path: Path, root: Path) -> bool:
    """True when `path` sits inside a parts library mounted under `root`.

    A machine's own gates skip a mounted library: it is validated in its own
    repository, and a machine should not re-run hundreds of supplier checks on
    every commit. Compares the path relative to the repository root, never the
    absolute path -- see
    docs/mistakes/2026-09-18_orphan-check-read-the-path-to-the-repository.md.
    """
    try:
        resolved = path.resolve()
        root = root.resolve()
        resolved.relative_to(root)
    except (ValueError, OSError):
        return False
    for library in library_roots(root):
        try:
            resolved.relative_to(library)
        except ValueError:
            continue
        return True
    return False


_DOQS_ROOT = Path(__file__).resolve().parent.parent
_LEXICON_PATH = _DOQS_ROOT / "data" / "naming-lexicon.txt"


def repo_root_from_script() -> Path:
    """Machine repository root (parent of the doqs/ submodule)."""
    return Path(__file__).resolve().parent.parent.parent


#: Submodules that carry tooling, not machine content. A machine repo mounts
#: this tools repo at `doqs/` and the shared agent kit at `.agents/`. Neither
#: holds machine files, so every validator that walks the machine root skips
#: both. See docs/architecture.md (Tooling submodules).
TOOLING_SUBMODULE_NAMES = frozenset({"doqs", ".agents"})


def is_under_tooling_submodule(path: Path, root: Path) -> bool:
    """True if path is inside a tooling submodule (`doqs/` or `.agents/`).

    The name is matched at any depth, because an extracted module under
    `modules/` mounts the same two submodules for itself. Paths outside root
    are not under one.
    """
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return any(part in TOOLING_SUBMODULE_NAMES for part in parts)


CATALOG_NAME = "catalog.toml"


def family_root(path: Path) -> Path | None:
    """Nearest ancestor holding a ``catalog.toml`` — the product family root.

    Composition modules reference their core and options with paths relative to
    this directory, so the whole family moves as one unit when it is extracted.
    """
    for parent in path.parents:
        if (parent / CATALOG_NAME).exists():
            return parent
    return None


def load_lexicon(path: Path | None = None) -> frozenset[str]:
    """Load lowercase words from data/naming-lexicon.txt."""
    lex_path = path or _LEXICON_PATH
    words: set[str] = set()
    for line in lex_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words.add(line.lower())
    return frozenset(words)


def validate_module_slug(slug: str) -> bool:
    return bool(MODULE_SLUG.match(slug))


def validate_adapter_slug(slug: str) -> bool:
    return bool(ADAPTER_SLUG.match(slug))


def validate_bom_id(part_id: str) -> tuple[bool, str | None]:
    m = BOM_ID.match(part_id)
    if not m:
        return False, "expected PREFIX-NNN (e.g. MEC-001)"
    prefix = m.group(1)
    if prefix not in BOM_PREFIXES:
        return False, f"unknown prefix {prefix!r} (see docs/naming.md)"
    return True, None


def tokenize_name(name: str) -> list[str]:
    """Split a display name into lowercase tokens for lexicon checks."""
    tokens: list[str] = []
    for part in re.split(r"[\s\-_/]+", name):
        part = part.strip()
        if not part:
            continue
        if part.isupper() and len(part) > 1:
            continue
        if re.fullmatch(r"[0-9.]+", part):
            continue
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", part)
        if cleaned:
            tokens.append(cleaned.lower())
    return tokens


def lexicon_violations(name: str, lexicon: frozenset[str]) -> list[str]:
    return [t for t in tokenize_name(name) if t not in lexicon]
