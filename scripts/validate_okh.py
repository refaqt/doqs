"""Validate all okh.toml manifests in the repository."""
from __future__ import annotations

import argparse
from pathlib import Path
import tomllib

from naming_rules import OKH_VERSION, is_under_doqs_submodule, repo_root_from_script

REQUIRED = ["okhv", "name", "repo", "version", "license", "licensor", "function"]


def validate(p: Path, *, expected_version: str | None = None) -> list[str]:
    errors: list[str] = []
    with open(p, "rb") as f:
        data = tomllib.load(f)
    for field in REQUIRED:
        if field not in data:
            errors.append(f"Missing: {field}")
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
    for model in data.get("model", []):
        if "params" in model:
            params_path = p.parent / model["params"]
            if not params_path.exists():
                errors.append(
                    f"model '{model.get('name', '?')}' params not found: {model['params']}"
                )
    for iface in data.get("provides-interface", []) + data.get("consumes-interface", []):
        if "name" not in iface or "version" not in iface:
            errors.append(f"Interface missing name or version: {iface}")
    for part in data.get("part", []):
        for item in part.get("source", []) + part.get("export", []):
            if not (p.parent / item).exists():
                errors.append(f"part '{part.get('name', '?')}' file not found: {item}")
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
        errors = validate(manifest, expected_version=args.expected_version)
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
