"""Validate all okh.toml manifests in the repository."""
from __future__ import annotations

import argparse
from pathlib import Path
import tomllib

from license_rules import HARDWARE_LICENSE
from naming_rules import (
    MODEL_SLUG,
    OKH_VERSION,
    is_under_doqs_submodule,
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
    if license_val is not None and str(license_val) != HARDWARE_LICENSE:
        errors.append(
            f"license must be {HARDWARE_LICENSE!r} "
            f"(hardware; see LICENSE for the split), got: {license_val!r}"
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
        if is_under_doqs_submodule(manifest, root):
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
