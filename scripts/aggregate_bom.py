"""Aggregate every module BOM into one purchasing list at the machine root.

Naively walking ``**/bom/bom.csv`` breaks once a product family is vendored as
a submodule: the family ships *every* composition and *every* length, and its
base BOMs still carry ``{alias}`` placeholders and empty supplier part numbers
because no length has been chosen yet.  A machine that aggregated those would
double-count the catalogue and quote the wrong rail.

So this aggregator:

* takes each instance module's committed ``bom/resolved.csv`` — the flattened,
  length-resolved list for the variant that machine actually selected — and
* skips the family checkout it points at, since the instance already speaks
  for it.

Everything else is an ordinary module and contributes its ``bom/bom.csv``.
"""
from __future__ import annotations

import argparse
import csv
import io
import tomllib
from pathlib import Path

from naming_rules import BOM_HEADERS, family_root, is_under_tooling_submodule, repo_root_from_script

OUT_HEADERS = ("module", *BOM_HEADERS)


def load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _read(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items() if k}
                for row in csv.DictReader(f) if (row.get("id") or "").strip()]


def collect(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    covered: list[Path] = []

    instances: list[tuple[Path, dict]] = []
    for okh in sorted(root.rglob("okh.toml")):
        if is_under_tooling_submodule(okh, root):
            continue
        try:
            data = load_toml(okh)
        except tomllib.TOMLDecodeError:
            continue
        if "instance" in data:
            instances.append((okh.parent, data["instance"]))
            family = root / data["instance"].get("family", "")
            if family.is_dir():
                covered.append(family.resolve())

    for instance_dir, _spec in instances:
        resolved = instance_dir / "bom" / "resolved.csv"
        if not resolved.exists():
            raise SystemExit(
                f"{instance_dir.relative_to(root).as_posix()}: bom/resolved.csv is missing — "
                "run doqs/scripts/resolve_instance.py first"
            )
        prefix = instance_dir.relative_to(root).as_posix()
        for row in _read(resolved):
            source = row.get("module", "")
            rows.append({**row, "module": f"{prefix} <- {source}" if source else prefix})

    for bom in sorted(root.rglob("bom/bom.csv")):
        if is_under_tooling_submodule(bom, root):
            continue
        module_dir = bom.parent.parent
        if module_dir == root:
            continue  # the aggregated root BOM itself
        resolved = module_dir.resolve()
        if any(resolved == c or c in resolved.parents for c in covered):
            continue  # spoken for by an instance module
        if any(d[0].resolve() == resolved for d in instances):
            continue  # the instance's own rows are already in resolved.csv
        if family_root(bom) is not None:
            continue  # a family's own modules are selected by an instance
        for row in _read(bom):
            rows.append({**row, "module": module_dir.relative_to(root).as_posix()})
    return rows


def render(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(OUT_HEADERS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in OUT_HEADERS})
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate module BOMs at the machine root.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None,
                        help="Default: <root>/bom/bom.csv (generated; gitignored)")
    args = parser.parse_args(argv)

    root = args.root.resolve() if args.root else repo_root_from_script()
    rows = collect(root)
    out = args.out or (root / "bom" / "bom.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(rows), encoding="utf-8")
    print(f"Wrote {out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
