"""Shared naming conventions for DOQS validators and tests."""
from __future__ import annotations

import re
from pathlib import Path

MODULE_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ADAPTER_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*-to-[a-z0-9]+(-[a-z0-9]+)*$")
BOM_ID = re.compile(r"^([A-Z]{2,4})-([0-9]{3})$")
MODEL_SLUG = MODULE_SLUG
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

BOM_HEADERS = (
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

_DOQS_ROOT = Path(__file__).resolve().parent.parent
_LEXICON_PATH = _DOQS_ROOT / "data" / "naming-lexicon.txt"


def repo_root_from_script() -> Path:
    """Machine repository root (parent of the doqs/ submodule)."""
    return Path(__file__).resolve().parent.parent.parent


def is_under_doqs_submodule(path: Path, root: Path) -> bool:
    """True if path is inside the machine's doqs/ tools submodule (not repo name 'doqs')."""
    try:
        return "doqs" in path.relative_to(root).parts
    except ValueError:
        return False


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
