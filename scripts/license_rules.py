"""Split-licensing helpers for DOQS machine and extracted-module repos.

Canonical layout (per Git repository root): CERN-OHL-S-2.0 for hardware
directories, GPL-3.0 for firmware/software/simulation, CC BY-SA 4.0 for
docs/measurement, plus root LICENSE overview, LICENSES/ full texts, and
TRADEMARKS.md. See docs/architecture.md (Licensing).
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

HARDWARE_LICENSE = "CERN-OHL-S-2.0"
DEFAULT_ORGANISATION = "REFAQT"

DIR_KIND: dict[str, str] = {
    "cad": "hardware",
    "architecture": "hardware",
    "manufacturing": "hardware",
    "bom": "hardware",
    "builds": "hardware",
    "modules": "hardware",
    "firmware": "software",
    "software": "software",
    "simulation": "software",
    "docs": "media",
    "measurement": "media",
}

FULL_TEXT_FILES: dict[str, tuple[str, ...]] = {
    "CERN-OHL-S-2.0.txt": (
        "CERN Open Hardware Licence Version 2 - Strongly Reciprocal",
    ),
    "GPL-3.0.txt": ("GNU GENERAL PUBLIC LICENSE", "Version 3"),
    "CC-BY-SA-4.0.txt": ("Creative Commons Attribution-ShareAlike 4.0",),
}

ROOT_LICENSE_MARKERS = (
    "CERN-OHL-S",
    "GPL-3.0",
    "CC BY-SA",
    "TRADEMARKS.md",
    "LICENSES",
)

STUB_MARKERS: dict[str, tuple[str, ...]] = {
    "hardware": ("CERN-OHL-S", "LICENSES"),
    "software": ("GPL-3.0", "LICENSES"),
    "media": ("CC BY-SA", "LICENSES"),
}

_GITMODULE_PATH = re.compile(r"^\s*path\s*=\s*(.+)$")
_README_HEADING = re.compile(r"(?im)^#{1,6}\s+licen[cs]e\b")
_README_LICENSE_LINK = re.compile(r"(?i)\[licen[cs]e\]\(licen[cs]e\)")

_DOQS_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = _DOQS_ROOT / "templates" / "licensing"


def templates_dir() -> Path:
    return TEMPLATES_DIR


def _as_str(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if str(v).strip())
    if value is None:
        return ""
    return str(value).strip()


def load_identity(root: Path) -> tuple[str, str]:
    """Return (project_name, organisation) from root okh.toml, with defaults."""
    name = root.name
    organisation = DEFAULT_ORGANISATION
    okh = root / "okh.toml"
    if not okh.is_file():
        return name, organisation
    with open(okh, "rb") as f:
        data = tomllib.load(f)
    name = _as_str(data.get("name")) or name
    organisation = _as_str(data.get("organisation")) or organisation
    return name, organisation


def render(template: str, project_name: str, organisation: str) -> str:
    return template.replace("{{PROJECT_NAME}}", project_name).replace(
        "{{ORGANISATION}}", organisation
    )


def read_template(relative: str) -> str:
    path = TEMPLATES_DIR / relative
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    return text


def expected_root_license(project_name: str, organisation: str) -> str:
    return render(read_template("LICENSE"), project_name, organisation)


def expected_trademarks(project_name: str, organisation: str) -> str:
    return render(read_template("TRADEMARKS.md"), project_name, organisation)


def expected_stub(kind: str) -> str:
    return read_template(f"dir/{kind}.LICENSE")


def expected_readme_section(project_name: str, organisation: str) -> str:
    return render(
        read_template("README-licence-section.md"), project_name, organisation
    )


def expected_okh_comment() -> str:
    return read_template("okh-license-comment.toml")


def iter_submodule_paths(root: Path) -> list[Path]:
    """Submodule working trees under root, excluding the doqs/ tools submodule."""
    gitmodules = root / ".gitmodules"
    if not gitmodules.is_file():
        return []
    paths: list[Path] = []
    for line in gitmodules.read_text(encoding="utf-8").splitlines():
        m = _GITMODULE_PATH.match(line)
        if not m:
            continue
        rel = m.group(1).strip().strip("'\"")
        child = (root / rel).resolve()
        try:
            parts = child.relative_to(root.resolve()).parts
        except ValueError:
            continue
        if "doqs" in parts:
            continue
        if child.is_dir():
            paths.append(child)
    return paths


def iter_repo_roots(root: Path) -> list[Path]:
    """root plus extracted-module submodule roots (not doqs/)."""
    roots = [root.resolve()]
    for sub in iter_submodule_paths(root):
        roots.extend(iter_repo_roots(sub))
    return roots


def _contains_markers(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return all(marker.lower() in lowered for marker in markers)


def _file_ok(path: Path, markers: tuple[str, ...]) -> bool:
    if not path.is_file():
        return False
    return _contains_markers(path.read_text(encoding="utf-8"), markers)


def mapped_dirs(root: Path) -> list[tuple[Path, str]]:
    """Existing first-level directories that need a LICENSE stub."""
    found: list[tuple[Path, str]] = []
    for name, kind in DIR_KIND.items():
        d = root / name
        if d.is_dir():
            found.append((d, kind))
    return found


def check_generated_files(root: Path) -> list[str]:
    """Errors for LICENSE / TRADEMARKS / LICENSES / directory stubs."""
    errors: list[str] = []
    name, org = load_identity(root)
    if not _file_ok(root / "LICENSE", ROOT_LICENSE_MARKERS):
        errors.append(
            "LICENSE missing or incomplete (must name CERN-OHL-S, GPL-3.0, "
            "CC BY-SA, TRADEMARKS.md, and LICENSES/)"
        )
    tm_markers = ("trademark", name)
    if not _file_ok(root / "TRADEMARKS.md", tm_markers):
        errors.append(
            f"TRADEMARKS.md missing or incomplete (must mention {name!r} "
            "and trademarks)"
        )
    licenses_dir = root / "LICENSES"
    if not licenses_dir.is_dir():
        errors.append("LICENSES/ directory missing")
    else:
        for filename, markers in FULL_TEXT_FILES.items():
            path = licenses_dir / filename
            if not _file_ok(path, markers):
                errors.append(f"LICENSES/{filename} missing or is not the expected licence text")
    for directory, kind in mapped_dirs(root):
        stub = directory / "LICENSE"
        if not _file_ok(stub, STUB_MARKERS[kind]):
            rel = directory.relative_to(root)
            errors.append(
                f"{rel}/LICENSE missing or does not declare the {kind} licence"
            )
    return errors


def check_readme(root: Path) -> list[str]:
    path = root / "README.md"
    if not path.is_file():
        return ["README.md missing (needs a Licence section)"]
    text = path.read_text(encoding="utf-8")
    if not _README_HEADING.search(text):
        return ["README.md has no Licence/License heading"]
    lowered = text.lower()
    names_ok = all(
        token in lowered for token in ("cern-ohl-s", "gpl-3.0", "cc by-sa")
    )
    if names_ok or _README_LICENSE_LINK.search(text):
        return []
    return [
        "README.md Licence section must name CERN-OHL-S, GPL-3.0, and CC BY-SA, "
        "or link to LICENSE"
    ]


def check_okh_license(root: Path) -> list[str]:
    path = root / "okh.toml"
    if not path.is_file():
        return ["okh.toml missing"]
    with open(path, "rb") as f:
        data = tomllib.load(f)
    value = data.get("license")
    if value is None:
        return ["okh.toml missing license field"]
    if str(value) != HARDWARE_LICENSE:
        return [
            f"okh.toml license must be {HARDWARE_LICENSE!r} "
            f"(hardware; see LICENSE for the split), got: {value!r}"
        ]
    return []


def check_repo(root: Path) -> list[str]:
    """All licence-layout errors for one Git repository root."""
    return (
        check_generated_files(root)
        + check_readme(root)
        + check_okh_license(root)
    )


def advice_messages(root: Path) -> list[str]:
    """Hints for files apply_licenses does not rewrite."""
    notes: list[str] = []
    name, org = load_identity(root)
    if check_readme(root):
        notes.append(
            "Add this Licence section to README.md:\n"
            + expected_readme_section(name, org)
        )
    okh = root / "okh.toml"
    if okh.is_file():
        text = okh.read_text(encoding="utf-8")
        if "GPL-3.0" not in text or "CC BY-SA" not in text:
            notes.append(
                "Add this comment next to license in okh.toml:\n"
                + expected_okh_comment()
            )
    notes.extend(f"okh.toml: {e}" for e in check_okh_license(root))
    return notes


def _write_if_needed(
    path: Path, content: str, markers: tuple[str, ...]
) -> str | None:
    if path.is_file() and _contains_markers(
        path.read_text(encoding="utf-8"), markers
    ):
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content += "\n"
    path.write_text(content, encoding="utf-8")
    return f"wrote {path}"


def apply_repo(root: Path) -> list[str]:
    """Write missing/invalid generated licence files. Returns action messages."""
    name, org = load_identity(root)
    actions: list[str] = []
    wrote = _write_if_needed(
        root / "LICENSE",
        expected_root_license(name, org),
        ROOT_LICENSE_MARKERS,
    )
    if wrote:
        actions.append(wrote)
    wrote = _write_if_needed(
        root / "TRADEMARKS.md",
        expected_trademarks(name, org),
        ("trademark", name),
    )
    if wrote:
        actions.append(wrote)
    for filename, markers in FULL_TEXT_FILES.items():
        dest = root / "LICENSES" / filename
        source = TEMPLATES_DIR / "LICENSES" / filename
        wrote = _write_if_needed(
            dest, source.read_text(encoding="utf-8"), markers
        )
        if wrote:
            actions.append(wrote)
    for directory, kind in mapped_dirs(root):
        wrote = _write_if_needed(
            directory / "LICENSE",
            expected_stub(kind),
            STUB_MARKERS[kind],
        )
        if wrote:
            actions.append(wrote)
    return actions
