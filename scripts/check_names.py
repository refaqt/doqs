"""Validate module slugs, BOM ids, model names, and naming lexicon usage."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import tomllib

from naming_rules import (
    BOM_HEADERS,
    load_lexicon,
    lexicon_violations,
    is_under_doqs_submodule,
    repo_root_from_script,
    validate_adapter_slug,
    validate_bom_id,
    validate_module_slug,
    MODEL_SLUG,
)


class Finding:
    def __init__(self, path: str, message: str, *, warning: bool = False) -> None:
        self.path = path
        self.message = message
        self.warning = warning


def module_slug_from_path(modules_dir: Path, mod_dir: Path) -> str:
    rel = mod_dir.relative_to(modules_dir)
    parts = rel.parts
    if parts[0] == "adapters":
        return parts[1] if len(parts) > 1 else ""
    return parts[-1]


def check_module_directories(root: Path, modules_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not modules_dir.is_dir():
        return findings

    for okh in sorted(modules_dir.rglob("okh.toml")):
        if is_under_doqs_submodule(okh, root):
            continue
        mod_dir = okh.parent
        rel = mod_dir.relative_to(root)
        slug = module_slug_from_path(modules_dir, mod_dir)
        if not slug:
            continue
        rel_parts = mod_dir.relative_to(modules_dir).parts
        if rel_parts[0] == "adapters":
            if not validate_adapter_slug(slug):
                findings.append(Finding(
                    str(rel),
                    f"adapter slug {slug!r} must match <from>-to-<to> (kebab-case)",
                ))
        elif not validate_module_slug(slug):
            findings.append(Finding(
                str(rel),
                f"module slug {slug!r} must be kebab-case functional name",
            ))

    for child in modules_dir.rglob("*"):
        if not child.is_dir() or child == modules_dir:
            continue
        if is_under_doqs_submodule(child, root):
            continue
        if (child / "okh.toml").exists():
            continue
        if child.name in ("adapters",) or child.parent == modules_dir and child.name == "adapters":
            continue
        rel = child.relative_to(root)
        if any(p == "cad" or p == "bom" or p == "architecture" for p in child.parts):
            continue
        if child.parent == modules_dir / "adapters":
            continue
        if list(child.glob("okh.toml")):
            continue
        if not any(child.iterdir()):
            continue
        findings.append(Finding(
            str(rel),
            "directory under modules/ has no okh.toml (orphan?)",
            warning=True,
        ))

    return findings


def check_bom_file(bom_path: Path, rel: str, lexicon: frozenset[str]) -> list[Finding]:
    findings: list[Finding] = []
    with open(bom_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            findings.append(Finding(rel, "empty BOM file"))
            return findings
        headers = [h.strip() for h in reader.fieldnames]
        if tuple(headers) != BOM_HEADERS:
            findings.append(Finding(
                rel,
                f"BOM header mismatch; expected {list(BOM_HEADERS)}",
            ))
            return findings
        seen_ids: set[str] = set()
        for row in reader:
            part_id = (row.get("id") or "").strip()
            if not part_id:
                continue
            ok, err = validate_bom_id(part_id)
            if not ok:
                findings.append(Finding(rel, f"id {part_id!r}: {err}"))
            elif part_id in seen_ids:
                findings.append(Finding(rel, f"duplicate id {part_id!r}"))
            else:
                seen_ids.add(part_id)
            name = (row.get("name") or "").strip()
            if name:
                for token in lexicon_violations(name, lexicon):
                    findings.append(Finding(
                        rel,
                        f"name {name!r}: token {token!r} not in naming lexicon",
                        warning=True,
                    ))
    return findings


def check_okh_manifest(
    okh_path: Path,
    root: Path,
    lexicon: frozenset[str],
) -> list[Finding]:
    findings: list[Finding] = []
    rel = str(okh_path.relative_to(root))
    with open(okh_path, "rb") as f:
        data = tomllib.load(f)

    for model in data.get("model", []):
        name = model.get("name", "")
        if name and not MODEL_SLUG.match(name):
            findings.append(Finding(rel, f"model name {name!r} must be kebab-case slug"))

    for part in data.get("part", []):
        name = part.get("name", "")
        if name:
            for token in lexicon_violations(name, lexicon):
                findings.append(Finding(
                    rel,
                    f"part {name!r}: token {token!r} not in naming lexicon",
                    warning=True,
                ))

    if "bom" in data:
        bom_path = okh_path.parent / data["bom"]
        if bom_path.exists():
            findings.extend(check_bom_file(bom_path, f"{rel} → {data['bom']}", lexicon))

    return findings


def check_all(root: Path, *, strict_lexicon: bool) -> tuple[list[Finding], list[Finding]]:
    lexicon = load_lexicon()
    errors: list[Finding] = []
    warnings: list[Finding] = []

    modules_dir = root / "modules"
    for f in check_module_directories(root, modules_dir):
        (warnings if f.warning else errors).append(f)

    for okh in sorted(root.rglob("okh.toml")):
        if is_under_doqs_submodule(okh, root):
            continue
        for f in check_okh_manifest(okh, root, lexicon):
            (warnings if f.warning else errors).append(f)

    if strict_lexicon:
        errors.extend(warnings)
        warnings = []

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DOQS naming conventions.")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Machine repo root (default: parent of doqs/ submodule)",
    )
    parser.add_argument(
        "--strict-lexicon",
        action="store_true",
        help="Treat lexicon warnings as errors",
    )
    parser.add_argument(
        "--warnings-only",
        action="store_true",
        help="Exit 0 when only warnings (no errors)",
    )
    args = parser.parse_args()
    root = args.root.resolve() if args.root else repo_root_from_script()

    errors, warnings = check_all(root, strict_lexicon=args.strict_lexicon)

    all_ok = True
    for f in errors:
        all_ok = False
        print(f"FAIL  {f.path}")
        print(f"      {f.message}")
    for f in warnings:
        print(f"WARN  {f.path}")
        print(f"      {f.message}")

    if all_ok and not warnings:
        print("ok    naming conventions")
    elif all_ok:
        print("ok    naming conventions (with warnings)")

    if not all_ok:
        return 1
    if warnings and not args.warnings_only:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
