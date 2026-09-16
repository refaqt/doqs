"""Resolve a module's BOM for one parametric model.

Four things happen, in order:

1. ``bom/models/<model>.csv`` is applied as a **column-sparse** overlay: only
   the columns present in the overlay header are overridden.
2. ``bom/sources.toml`` ``[[bind]]`` entries fill columns from a supplier
   **length table**, so adding a length model needs no BOM edit at all.
3. ``{alias}`` placeholders in any cell are replaced with resolved parameters,
   for cut-to-length stock that has no per-length part number.
4. ``[[vendor]]`` entries (and the table's ``cad`` column) resolve the STEP file
   of each purchased component for the selected length.

The output keeps the exact 16-column DOQS BOM header and carries no comment
lines, so ``validate_names.check_bom_file`` reads it like any hand-written BOM.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import tomllib
from pathlib import Path

from naming_rules import BOM_HEADERS, repo_root_from_script
from param_rules import ParamError, resolve_model

SOURCES_NAME = "sources.toml"
TEMPLATE_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
MATCH_MODES = ("exact", "nearest-up", "nearest-down")


class BomError(Exception):
    """Raised for malformed BOM overlays, bindings, or unresolvable lookups."""


def load_bom(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise BomError(f"empty BOM: {path}")
        headers = tuple(h.strip() for h in reader.fieldnames)
        if headers != BOM_HEADERS:
            raise BomError(f"{path}: header must be exactly {list(BOM_HEADERS)}")
        return [{k: (v or "").strip() for k, v in row.items() if k} for row in reader
                if (row.get("id") or "").strip()]


def apply_overlay(rows: list[dict[str, str]], overlay_path: Path) -> list[dict[str, str]]:
    """Column-sparse overlay: only columns present in the overlay header change.

    An unknown ``id`` adds a row (and must then carry the full BOM header).
    ``qty = 0`` removes a row.
    """
    with open(overlay_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise BomError(f"empty overlay: {overlay_path}")
        columns = [h.strip() for h in reader.fieldnames]
        if "id" not in columns:
            raise BomError(f"{overlay_path}: overlay header must contain 'id'")
        unknown = [c for c in columns if c not in BOM_HEADERS]
        if unknown:
            raise BomError(f"{overlay_path}: unknown BOM columns {unknown}")
        overlay = [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]

    by_id = {row["id"]: row for row in rows}
    order = [row["id"] for row in rows]
    removed: set[str] = set()

    for entry in overlay:
        part_id = entry.get("id", "")
        if not part_id:
            continue
        if part_id in by_id:
            if entry.get("qty") == "0":
                removed.add(part_id)
                continue
            for column in columns:
                if column != "id":
                    by_id[part_id][column] = entry[column]
        else:
            if set(columns) != set(BOM_HEADERS):
                raise BomError(
                    f"{overlay_path}: new id {part_id!r} must carry the full BOM header"
                )
            by_id[part_id] = {k: entry.get(k, "") for k in BOM_HEADERS}
            order.append(part_id)

    return [by_id[i] for i in order if i not in removed]


def load_sources(module_dir: Path) -> dict:
    path = module_dir / "bom" / SOURCES_NAME
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _lookup_table(table_path: Path, wanted: float, mode: str) -> dict[str, str]:
    with open(table_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "key" not in reader.fieldnames:
            raise BomError(f"{table_path}: first column must be 'key'")
        table = [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]

    keys: list[tuple[float, dict[str, str]]] = []
    for row in table:
        try:
            keys.append((float(row["key"]), row))
        except ValueError as exc:
            raise BomError(f"{table_path}: non-numeric key {row['key']!r}") from exc

    if mode == "exact":
        for value, row in keys:
            if value == wanted:
                return row
        stocked = ", ".join(str(int(v)) if v.is_integer() else str(v) for v, _ in sorted(keys))
        raise BomError(
            f"{table_path.name}: no row for key {wanted:g}. Stocked: {stocked}. "
            "Either add the length to the table or pick a length a supplier sells."
        )
    if mode == "nearest-up":
        candidates = sorted((v, r) for v, r in keys if v >= wanted)
    else:
        candidates = sorted(((v, r) for v, r in keys if v <= wanted), reverse=True)
    if not candidates:
        raise BomError(f"{table_path.name}: no stocked key {mode} of {wanted:g}")
    return candidates[0][1]


def apply_bindings(
    rows: list[dict[str, str]],
    module_dir: Path,
    params: dict[str, str],
    sources: dict,
) -> None:
    by_id = {row["id"]: row for row in rows}
    for bind in sources.get("bind", []):
        part_id = bind.get("id", "")
        if part_id not in by_id:
            raise BomError(f"{SOURCES_NAME}: bind targets unknown BOM id {part_id!r}")
        mode = bind.get("match", "exact")
        if mode not in MATCH_MODES:
            raise BomError(f"{SOURCES_NAME}: bind {part_id!r} has bad match {mode!r}")
        key = bind.get("key", "")
        if key not in params:
            raise BomError(f"{SOURCES_NAME}: bind {part_id!r} key {key!r} is not a parameter")
        try:
            wanted = float(params[key])
        except ValueError as exc:
            raise BomError(f"{SOURCES_NAME}: parameter {key!r} is not numeric") from exc

        table_path = module_dir / "bom" / bind["table"]
        if not table_path.exists():
            raise BomError(f"{SOURCES_NAME}: table not found: {bind['table']}")
        entry = _lookup_table(table_path, wanted, mode)

        row = by_id[part_id]
        for column in bind.get("columns", []):
            if column not in BOM_HEADERS:
                raise BomError(f"{SOURCES_NAME}: bind {part_id!r} unknown column {column!r}")
            row[column] = entry.get(column, "")
        stocked = float(entry["key"])
        if mode != "exact" and stocked != wanted:
            note = f"stock length {stocked:g}, cut to {wanted:g}"
            row["notes"] = f"{row['notes']}; {note}".lstrip("; ")


def apply_templates(rows: list[dict[str, str]], params: dict[str, str]) -> None:
    for row in rows:
        for column, value in row.items():
            if "{" not in value:
                continue
            def replace(match: re.Match[str]) -> str:
                alias = match.group(1)
                if alias not in params:
                    raise BomError(
                        f"row {row['id']}: unknown parameter {{{alias}}} in column {column!r}"
                    )
                return params[alias]
            row[column] = TEMPLATE_RE.sub(replace, value)


def collect_vendor(
    rows: list[dict[str, str]],
    module_dir: Path,
    params: dict[str, str],
    sources: dict,
    module_rel: str,
) -> list[dict[str, str]]:
    """Resolve the geometry file of each purchased component for this model."""
    by_id = {row["id"] for row in rows}
    out: list[dict[str, str]] = []
    for vendor in sources.get("vendor", []):
        part_id = vendor.get("id", "")
        if part_id not in by_id:
            raise BomError(f"{SOURCES_NAME}: vendor targets unknown BOM id {part_id!r}")
        cad = vendor.get("cad", "")
        if not cad:
            # Length-dependent: the bound table carries a `cad` column.
            bind = next((b for b in sources.get("bind", []) if b.get("id") == part_id), None)
            if bind is None:
                raise BomError(
                    f"{SOURCES_NAME}: vendor {part_id!r} has no `cad` and no bound table"
                )
            entry = _lookup_table(
                module_dir / "bom" / bind["table"],
                float(params[bind["key"]]),
                bind.get("match", "exact"),
            )
            cad = entry.get("cad", "")
            if not cad:
                raise BomError(
                    f"{SOURCES_NAME}: vendor {part_id!r} table row has no `cad` column value"
                )
        out.append({
            "id": part_id,
            "module": module_rel,
            "cad": cad,
            "envelope": vendor.get("envelope", ""),
            "terms": vendor.get("terms", "redistributable"),
        })
    return out


def resolve(module_dir: Path, model: str, module_rel: str = "") -> tuple[list[dict], list[dict]]:
    """Return ``(bom rows, vendor geometry rows)`` for one module and model."""
    bom_path = module_dir / "bom" / "bom.csv"
    if not bom_path.exists():
        return [], []
    rows = load_bom(bom_path)

    params: dict[str, str] = {}
    if (module_dir / "cad" / "params" / "default.csv").exists():
        params = {a: r["value"] for a, r in resolve_model(module_dir, model).items()}

    overlay = module_dir / "bom" / "models" / f"{model}.csv"
    if overlay.exists():
        rows = apply_overlay(rows, overlay)

    sources = load_sources(module_dir)
    apply_bindings(rows, module_dir, params, sources)
    apply_templates(rows, params)
    vendor = collect_vendor(rows, module_dir, params, sources, module_rel or module_dir.name)
    return rows, vendor


def render(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(BOM_HEADERS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in BOM_HEADERS})
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a module BOM for one model.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--module", type=Path, required=True,
                        help="Module directory, relative to --root")
    parser.add_argument("--model", default="default")
    parser.add_argument("--out", type=Path, default=None,
                        help="Write the resolved BOM here (default: stdout)")
    args = parser.parse_args()

    root = args.root.resolve() if args.root else repo_root_from_script()
    module_dir = (root / args.module).resolve()
    try:
        rows, vendor = resolve(module_dir, args.model, args.module.as_posix())
    except (BomError, ParamError) as exc:
        print(f"FAIL  {args.module.as_posix()}")
        print(f"      {exc}")
        return 1

    content = render(rows)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(content, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(content, end="")
    for entry in vendor:
        print(f"# vendor {entry['id']}: {entry['cad']} ({entry['terms']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
