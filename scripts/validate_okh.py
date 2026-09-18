"""Validate all okh.toml manifests in the repository."""
from __future__ import annotations

import argparse
from pathlib import Path
import tomllib

from license_rules import HARDWARE_LICENSE, LIBRARY_LICENSE
from naming_rules import (
    MODEL_SLUG,
    is_parts_library,
    is_under_parts_library,
    OKH_VERSION,
    is_under_tooling_submodule,
    repo_root_from_script,
)

REQUIRED = ["okhv", "name", "repo", "version", "license", "licensor", "function"]


def validate(
    p: Path,
    *,
    expected_version: str | None = None,
    root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    with open(p, "rb") as f:
        data = tomllib.load(f)
    for field in REQUIRED:
        if field not in data:
            errors.append(f"Missing: {field}")
    license_val = data.get("license")
    # A parts library records parts other people designed, so claiming the
    # hardware licence over them would be false. What IS ours there is the
    # compiled record. See docs/decisions/2026-09-18_parts-library.md.
    in_library = root is not None and (
        is_parts_library(root) or is_under_parts_library(p, root)
    )
    expected_license = LIBRARY_LICENSE if in_library else HARDWARE_LICENSE
    if license_val is not None and str(license_val) != expected_license:
        reason = (
            "the record is ours; the parts are not"
            if in_library
            else "hardware; see LICENSE for the split"
        )
        errors.append(
            f"license must be {expected_license!r} ({reason}), got: {license_val!r}"
        )
    version = data.get("version")
    if version is not None:
        if not OKH_VERSION.match(str(version)):
            errors.append(
                f"version must be semver without 'v' prefix (e.g. 1.2.0), got: {version!r}"
            )
        if expected_version is not None and str(version) != expected_version:
            errors.append(
                f"version {version!r} does not match expected {expected_version!r}"
            )
    release = data.get("release")
    if release and version:
        tag = f"v{version}"
        if tag not in str(release):
            errors.append(f"release URL should reference tag {tag!r}")
    for key in ("bom", "readme"):
        if key in data:
            ref = p.parent / data[key]
            if not ref.exists():
                errors.append(f"{key} not found: {data[key]}")
    for item in data.get("source", []) + data.get("export", []):
        if not (p.parent / item).exists():
            errors.append(f"File not found: {item}")
    for instr in data.get("manufacturing-instructions", []):
        if not (p.parent / instr).exists():
            errors.append(f"manufacturing-instructions not found: {instr}")
    seen_models: set[str] = set()
    for model in data.get("model", []):
        name = str(model.get("name", "?"))
        if name in seen_models:
            errors.append(f"duplicate model {name!r}")
        seen_models.add(name)
        if "params" in model:
            params_path = p.parent / model["params"]
            if not params_path.exists():
                errors.append(
                    f"model '{name}' params not found: {model['params']}"
                )
    errors.extend(_validate_instance(p, data, root))
    errors.extend(_validate_composition(p, data))
    errors.extend(_validate_brand(data))
    errors.extend(_validate_role(data, root))
    for comp in data.get("hasComponent", []):
        # Selection shortcut for the zero-override case: a parent may pin the
        # composition and model directly on the component declaration instead
        # of creating an instance module. See docs/variants.md.
        model = comp.get("model")
        if model is not None and not MODEL_SLUG.match(str(model)):
            errors.append(f"hasComponent model {model!r} must be a kebab-case slug")
        if "model" in comp and "composition" not in comp:
            errors.append("hasComponent has 'model' but no 'composition'")
    for iface in data.get("provides-interface", []) + data.get("consumes-interface", []):
        if "name" not in iface or "version" not in iface:
            errors.append(f"Interface missing name or version: {iface}")
    for part in data.get("part", []):
        for item in part.get("source", []) + part.get("export", []):
            if not (p.parent / item).exists():
                errors.append(f"part '{part.get('name', '?')}' file not found: {item}")
    return errors


def _validate_role(data: dict, root: Path | None) -> list[str]:
    """Shape-check a [role] table.

    Whether the selected part still exists, is still sold and still fits is the
    job of validate_variants.py, which can read the library's catalogue.
    """
    role = data.get("role")
    if role is None:
        return []
    errors = []
    for key in ("library", "selected"):
        if not role.get(key):
            errors.append(f"[role] is missing {key!r}")
    library = role.get("library")
    if library and root is not None and not (root / library).is_dir():
        errors.append(
            f"[role] library not found: {library} "
            "(run: git submodule update --init --recursive)"
        )
    approved = role.get("approved")
    if approved is not None and not isinstance(approved, list):
        errors.append("[role] approved must be a list of parts")
        approved = []
    selected = role.get("selected")
    for part in ([selected] if selected else []) + list(approved or []):
        if "#" not in str(part):
            errors.append(
                f"[role] {part!r} must name a part number: <family>#<part number>"
            )
    if selected and approved and str(selected) not in [str(a) for a in approved]:
        errors.append(
            "[role] selected is not in approved. What you buy today must be one "
            "of the parts you decided are acceptable."
        )
    return errors


def _validate_brand(data: dict) -> list[str]:
    """Shape-check a [brand] table in a parts library.

    `brand` is the name on the part, not the supplier you buy from. `cad-terms`
    is the address of the download terms somebody read before deciding what may
    be committed; recording it means the decision can be checked later instead
    of being argued again.
    """
    brand = data.get("brand")
    if brand is None:
        return []
    errors = []
    for key in ("name", "website", "cad-terms"):
        if not brand.get(key):
            errors.append(f"[brand] is missing {key!r}")
    redistribute = brand.get("redistribute")
    if redistribute is not None and not isinstance(redistribute, bool):
        errors.append(
            f"[brand] redistribute must be true or false, got: {redistribute!r}"
        )
    return errors


def _validate_instance(p: Path, data: dict, root: Path | None) -> list[str]:
    """Shape-check an [instance] table.

    Whether the target actually resolves inside the family is the job of
    validate_variants.py, which can also report a model that upstream removed.
    """
    spec = data.get("instance")
    if spec is None:
        return []
    errors = []
    for key in ("family", "composition", "model"):
        if not spec.get(key):
            errors.append(f"[instance] is missing {key!r}")
    # `family` is repo-root relative, like build.toml `path`, so the same
    # string works from any instance module in the machine.
    family = spec.get("family")
    if family and root is not None and not (root / family).is_dir():
        errors.append(
            f"[instance] family not found: {family} "
            "(run: git submodule update --init --recursive)"
        )
    model = spec.get("model")
    if model and not MODEL_SLUG.match(str(model)):
        errors.append(f"[instance] model {model!r} must be a kebab-case slug")
    return errors


def _validate_composition(p: Path, data: dict) -> list[str]:
    """Shape-check a [composition] table on a thin composition module."""
    comp = data.get("composition")
    if comp is None:
        return []
    errors = []
    if not comp.get("core"):
        errors.append("[composition] is missing 'core'")
    options = comp.get("options", [])
    if not isinstance(options, list):
        errors.append("[composition] options must be a list of paths")
    elif len(set(options)) != len(options):
        errors.append("[composition] options contains duplicates")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OKH manifests.")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Machine repo root (default: parent of doqs/ submodule)",
    )
    parser.add_argument(
        "--expected-version",
        default=None,
        help="Require every manifest version field to equal this value (release workflow)",
    )
    args = parser.parse_args()
    root = args.root.resolve() if args.root else repo_root_from_script()

    all_ok = True
    for manifest in sorted(root.rglob("okh.toml")):
        if is_under_tooling_submodule(manifest, root):
            continue
        errors = validate(manifest, expected_version=args.expected_version, root=root)
        rel = manifest.relative_to(root)
        if errors:
            all_ok = False
            print(f"FAIL  {rel}")
            for e in errors:
                print(f"      {e}")
        else:
            print(f"ok    {rel}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
