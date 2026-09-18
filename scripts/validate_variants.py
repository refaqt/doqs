"""Validate product families: catalogue, models, compositions, vendor geometry, instances.

Gates, in order:

* **Catalogue** — every ``[[sku]]`` names a composition that exists and a model
  the core declares; SKU ids are unique and well formed.
* **Compositions** — ``[composition] core`` and ``options`` resolve.
* **Parameters** — ``[[model]]`` entries match the files in ``cad/params/``, and
  every model resolves (no cycles, no unknown aliases).
* **Length tables** — every declared model resolves to a row in each bound
  supplier table, so a length nobody stocks fails here and not at purchasing.
* **Vendor geometry** — ``[[vendor]]`` targets exist; committed files must be
  present, ``fetch-only`` files only warn.
* **Instances** — every ``[instance]`` resolves against its family and its
  generated files are current.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import tomllib
from pathlib import Path

from naming_rules import (
    PARTS_STATUS,
    csv_reader_skipping_comments,
    PARTS_TABLE_HEADERS,
    SKU_ID,
    family_root,
    is_under_tooling_submodule,
    repo_root_from_script,
)
from param_rules import ParamError, declared_models, params_dir, resolve_model
from resolve_bom import BomError, _lookup_table, load_bom, load_sources
import resolve_instance

CATALOG_NAME = "catalog.toml"
CATALOG_SCHEMA = "doqs-catalog-v1"
SKU_STATUS = ("active", "preview", "eol")
VENDOR_TERMS = ("redistributable", "fetch-only")
VENDOR_INDEX = "vendor-index.csv"
#: A library family's catalogue lives at bom/parts.csv.
PARTS_TABLE_NAME = "parts.csv"
VENDOR_INDEX_HEADERS = (
    "supplier", "pn", "relpath", "bytes", "sha256", "source_url", "terms", "retrieved_utc",
)


class Finding:
    def __init__(self, path: str, message: str, *, warning: bool = False) -> None:
        self.path = path
        self.message = message
        self.warning = warning


def load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def check_catalog(root: Path, catalog_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    rel = catalog_path.relative_to(root).as_posix()
    family = catalog_path.parent
    data = load_toml(catalog_path)

    if data.get("schema") != CATALOG_SCHEMA:
        findings.append(Finding(rel, f"schema must be {CATALOG_SCHEMA!r}"))

    seen: set[str] = set()
    for sku in data.get("sku", []):
        name = sku.get("name", "")
        if not name:
            findings.append(Finding(rel, "sku is missing 'name'"))
            continue
        if not SKU_ID.match(name):
            findings.append(Finding(rel, f"sku {name!r} must match {SKU_ID.pattern}"))
        if name in seen:
            findings.append(Finding(rel, f"duplicate sku {name!r}"))
        seen.add(name)

        status = sku.get("status", "active")
        if status not in SKU_STATUS:
            findings.append(Finding(rel, f"sku {name!r}: status must be one of {SKU_STATUS}"))

        composition = sku.get("composition", "")
        comp_dir = family / composition
        if not composition or not (comp_dir / "okh.toml").exists():
            findings.append(Finding(rel, f"sku {name!r}: composition {composition!r} not found"))
            continue

        comp = load_toml(comp_dir / "okh.toml").get("composition", {})
        core = family / comp.get("core", "")
        model = sku.get("model", "default")
        if not (core / "okh.toml").exists():
            findings.append(Finding(rel, f"sku {name!r}: composition core not found"))
            continue
        available = declared_models(core)
        if model not in available:
            findings.append(Finding(
                rel,
                f"sku {name!r}: model {model!r} is not declared by {comp.get('core')} "
                f"(available: {', '.join(available)})",
            ))
    return findings


def check_composition(root: Path, okh_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    rel = okh_path.relative_to(root).as_posix()
    comp = load_toml(okh_path).get("composition")
    if not comp:
        return findings

    family = family_root(okh_path)
    if family is None:
        findings.append(Finding(rel, "[composition] found but no catalog.toml in any parent "
                                     "— compositions live inside a family repo"))
        return findings
    if "core" not in comp:
        findings.append(Finding(rel, "[composition] is missing 'core'"))
        return findings
    for key, value in [("core", comp["core"]), *[("option", o) for o in comp.get("options", [])]]:
        if not (family / value / "okh.toml").exists():
            findings.append(Finding(rel, f"[composition] {key} {value!r} not found in the family"))
    return findings


def check_models(root: Path, okh_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    rel = okh_path.relative_to(root).as_posix()
    module_dir = okh_path.parent
    data = load_toml(okh_path)
    declared = [m.get("name", "") for m in data.get("model", [])]
    if not declared:
        return findings

    # A module may declare a single nominal model with no parametrics at all
    # (`[[model]] name = "default"` and nothing else). Only start checking the
    # correspondence once there is a cad/params/ directory or a second model.
    if not params_dir(module_dir).is_dir():
        if len(declared) > 1:
            findings.append(Finding(
                rel,
                f"declares {len(declared)} models but has no cad/params/ directory",
            ))
        return findings

    on_disk = declared_models(module_dir)
    if not (params_dir(module_dir) / "default.csv").exists():
        findings.append(Finding(rel, "has cad/params/ but no default.csv (the dense base set)"))
        return findings
    for name in declared:
        if name and name not in on_disk:
            findings.append(Finding(rel, f"model {name!r} has no cad/params/{name}.csv"))
    for name in on_disk:
        if name not in declared:
            findings.append(Finding(
                rel, f"cad/params/{name}.csv exists but is not declared as a [[model]]"))

    for name in on_disk:
        try:
            resolve_model(module_dir, name)
        except ParamError as exc:
            findings.append(Finding(rel, f"model {name!r}: {exc}"))
    return findings


def check_sources(root: Path, module_dir: Path) -> list[Finding]:
    """Length-table coverage and vendor geometry for one module."""
    findings: list[Finding] = []
    sources = load_sources(module_dir)
    if not sources:
        return findings
    rel = f"{module_dir.relative_to(root).as_posix()}/bom/sources.toml"

    bom_path = module_dir / "bom" / "bom.csv"
    try:
        ids = {row["id"] for row in load_bom(bom_path)} if bom_path.exists() else set()
    except BomError as exc:
        findings.append(Finding(rel, str(exc)))
        return findings

    models = declared_models(module_dir) or ["default"]
    for bind in sources.get("bind", []):
        part_id = bind.get("id", "")
        if part_id not in ids:
            findings.append(Finding(rel, f"bind targets unknown BOM id {part_id!r}"))
            continue
        table_path = module_dir / "bom" / bind.get("table", "")
        if not table_path.exists():
            findings.append(Finding(rel, f"bind {part_id!r}: table not found: {bind.get('table')}"))
            continue
        # Every declared model must resolve to a stocked row.
        for model in models:
            try:
                params = {a: r["value"] for a, r in resolve_model(module_dir, model).items()}
                _lookup_table(table_path, float(params[bind["key"]]), bind.get("match", "exact"))
            except (BomError, ParamError, KeyError, ValueError) as exc:
                findings.append(Finding(rel, f"bind {part_id!r}, model {model!r}: {exc}"))

    for vendor in sources.get("vendor", []):
        part_id = vendor.get("id", "")
        if part_id not in ids:
            findings.append(Finding(rel, f"vendor targets unknown BOM id {part_id!r}"))
        terms = vendor.get("terms", "redistributable")
        if terms not in VENDOR_TERMS:
            findings.append(Finding(rel, f"vendor {part_id!r}: terms must be one of {VENDOR_TERMS}"))
        for key in ("cad", "envelope"):
            target = vendor.get(key)
            if not target:
                continue
            if (module_dir / target).exists():
                continue
            message = f"vendor {part_id!r}: {key} not found: {target}"
            if terms == "fetch-only":
                findings.append(Finding(rel, f"{message} (fetch-only — fetch it before CAD work)",
                                        warning=True))
            else:
                findings.append(Finding(rel, message))
    return findings


def module_root_of(path: Path) -> Path:
    """The module directory a file belongs to: nearest ancestor with okh.toml.

    Counting a fixed number of directories up works only while every caller
    sits at the same depth. Walking to the manifest is what actually defines a
    module, so a nested vendor directory resolves against the right base.
    """
    for candidate in path.parents:
        if (candidate / "okh.toml").is_file():
            return candidate
    return path.parent


def check_vendor_index(root: Path, index_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    rel = index_path.relative_to(root).as_posix()
    reader = csv_reader_skipping_comments(index_path.read_text(encoding="utf-8"))
    headers = tuple(h.strip() for h in (reader.fieldnames or []))
    if headers != VENDOR_INDEX_HEADERS:
        findings.append(Finding(rel, f"header must be exactly {list(VENDOR_INDEX_HEADERS)}"))
        return findings
    module_dir = module_root_of(index_path)
    for row in reader:
        pn = (row.get("pn") or "").strip()
        terms = (row.get("terms") or "").strip()
        if terms not in VENDOR_TERMS:
            findings.append(Finding(rel, f"{pn}: terms must be one of {VENDOR_TERMS}"))
        relpath = (row.get("relpath") or "").strip()
        if not relpath:
            continue
        target = module_dir / relpath
        if not target.exists():
            if terms != "fetch-only":
                findings.append(Finding(rel, f"{pn}: file not found: {relpath}"))
            continue
        # A brand can revise a file and keep the part number. The checksum
        # was already recorded and nothing compared it, so the change went
        # unnoticed. See docs/decisions/2026-09-18_parts-library.md.
        recorded = (row.get("sha256") or "").strip().lower()
        if not recorded:
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != recorded:
            findings.append(Finding(
                rel,
                f"{pn}: {relpath} no longer matches its recorded checksum. "
                "Either the brand changed the file under the same part "
                "number, or it was edited here. Check which, then add a new "
                "row rather than overwriting this one.",
            ))
    return findings


def check_parts_table(root: Path, table_path: Path) -> list[Finding]:
    """A library family's catalogue: one row per orderable part number."""
    findings: list[Finding] = []
    rel = table_path.relative_to(root).as_posix()
    module_dir = module_root_of(table_path)
    reader = csv_reader_skipping_comments(table_path.read_text(encoding="utf-8"))
    headers = tuple(h.strip() for h in (reader.fieldnames or []))
    if headers != PARTS_TABLE_HEADERS:
        findings.append(
            Finding(rel, f"header must be exactly {list(PARTS_TABLE_HEADERS)}")
        )
        return findings
    seen: set[str] = set()
    for row in reader:
        pn = (row.get("pn") or "").strip()
        if not pn:
            continue
        if pn in seen:
            findings.append(Finding(rel, f"duplicate part number {pn!r}"))
        seen.add(pn)
        status = (row.get("status") or "").strip()
        if status not in PARTS_STATUS:
            findings.append(
                Finding(rel, f"{pn}: status must be one of {PARTS_STATUS}")
            )
        terms = (row.get("terms") or "").strip()
        if terms not in VENDOR_TERMS:
            findings.append(
                Finding(rel, f"{pn}: terms must be one of {VENDOR_TERMS}")
            )
        for key in ("cad", "datasheet"):
            target = (row.get(key) or "").strip()
            if not target:
                # Geometry fills up as people use parts. A row without it
                # is normal, and the table is still the full catalogue.
                continue
            if (module_dir / target).exists():
                continue
            findings.append(Finding(
                rel,
                f"{pn}: {key} not found: {target}"
                + (" (fetch-only -- fetch it before CAD work)"
                   if terms == "fetch-only" else ""),
                warning=(terms == "fetch-only"),
            ))
    return findings


def check_all(root: Path) -> tuple[list[Finding], list[Finding]]:
    errors: list[Finding] = []
    warnings: list[Finding] = []

    def add(items: list[Finding]) -> None:
        for item in items:
            (warnings if item.warning else errors).append(item)

    for catalog in sorted(root.rglob(CATALOG_NAME)):
        if is_under_tooling_submodule(catalog, root):
            continue
        add(check_catalog(root, catalog))

    for okh in sorted(root.rglob("okh.toml")):
        if is_under_tooling_submodule(okh, root):
            continue
        add(check_composition(root, okh))
        add(check_models(root, okh))
        add(check_sources(root, okh.parent))

    for index in sorted(root.rglob(VENDOR_INDEX)):
        if is_under_tooling_submodule(index, root):
            continue
        add(check_vendor_index(root, index))

    for table in sorted(root.rglob(f"bom/{PARTS_TABLE_NAME}")):
        if is_under_tooling_submodule(table, root):
            continue
        add(check_parts_table(root, table))

    for instance_dir in resolve_instance.instance_modules(root):
        rel = instance_dir.relative_to(root).as_posix()
        try:
            rendered = resolve_instance.render_all(root, instance_dir)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            errors.append(Finding(f"{rel}/okh.toml", str(exc)))
            continue
        for rel_path, content in sorted(rendered.items()):
            path = instance_dir / rel_path
            if not path.exists():
                errors.append(Finding(f"{rel}/{rel_path.as_posix()}",
                                      "missing — run resolve_instance.py and commit the result"))
            elif path.read_text(encoding="utf-8") != content:
                errors.append(Finding(f"{rel}/{rel_path.as_posix()}",
                                      "stale — run resolve_instance.py and commit the result"))
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DOQS product families.")
    parser.add_argument("--root", type=Path, default=None,
                        help="Machine repo root (default: parent of doqs/ submodule)")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors")
    args = parser.parse_args()
    root = args.root.resolve() if args.root else repo_root_from_script()

    errors, warnings = check_all(root)
    if args.strict:
        errors, warnings = errors + warnings, []

    for finding in errors:
        print(f"FAIL  {finding.path}")
        print(f"      {finding.message}")
    for finding in warnings:
        print(f"WARN  {finding.path}")
        print(f"      {finding.message}")
    if not errors:
        print("ok    variants" + (" (with warnings)" if warnings else ""))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
