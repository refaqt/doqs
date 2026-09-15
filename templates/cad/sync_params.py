"""Sync resolved parameters into a FreeCAD document.

Copy this file to `<module>/cad/sync_params.py` in a machine or family repo.

Two modes, and the second is what makes a family usable from a parent machine:

`sync_active()`
    Writes `cad/params.csv` (the single active model) into the Spreadsheet
    named `Params`, one aliased cell per parameter. This is the long-standing
    DOQS flow.

`sync_table()`
    Writes `cad/params-table.csv` (the dense, one-row-per-model table) into the
    Spreadsheet as a FreeCAD **Configuration Table**. The document then gains a
    `Configuration` enum whose values are exactly the DOQS model slugs, so a
    parent machine can insert this assembly as a **Variant Link** and pick
    `500mm` - a live parametric model at its own length, inside the parent's
    own document, with the family submodule never written to.

Usage (FreeCAD Python console):

    exec(open("cad/sync_params.py").read())

Usage (headless, from the module root):

    FreeCADCmd cad/sync_params.py

After `sync_table()`, set up the configuration binding once, by hand:
right-click cell `A2` of the `Params` spreadsheet -> *Configuration table*.
FreeCAD then adds the `Configuration` property and binds it to the table.
That step is one-time; every later model change flows through the CSVs.
"""

import csv
from pathlib import Path

SHEET_NAME = "Params"
ACTIVE_CSV = "params.csv"
TABLE_CSV = "params-table.csv"
TABLE_KEY = "configuration"


def _rows(path):
    """Read a DOQS CSV, skipping the generated `#` provenance header."""
    with open(path, newline="", encoding="utf-8") as f:
        lines = [line for line in f if not line.lstrip().startswith("#")]
    return list(csv.reader(lines))


def _sheet(doc):
    found = doc.getObjectsByLabel(SHEET_NAME)
    if not found:
        raise RuntimeError(
            f"No Spreadsheet named {SHEET_NAME!r} in {doc.Name}. "
            "Add one (Spreadsheet workbench) before syncing."
        )
    return found[0]


def _here():
    try:
        return Path(__file__).parent
    except NameError:  # exec()'d from the FreeCAD console
        return Path.cwd() / "cad"


def sync_active(doc=None, csv_path=None):
    """cad/params.csv -> aliased cells of the Params spreadsheet."""
    import FreeCAD

    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        raise RuntimeError("No active FreeCAD document.")
    sheet = _sheet(doc)
    path = Path(csv_path) if csv_path else _here() / ACTIVE_CSV
    if not path.exists():
        raise RuntimeError(
            f"{path} not found. Run: python doqs/scripts/resolve_params.py "
            "--module <module> --model <model>"
        )

    rows = _rows(path)
    header, body = rows[0], rows[1:]
    index = {name: i for i, name in enumerate(header)}
    updated = []
    for row in body:
        if not row or not row[index["alias"]].strip():
            continue
        alias = row[index["alias"]].strip()
        value = row[index["value"]].strip()
        unit = row[index["unit"]].strip() if "unit" in index and len(row) > index["unit"] else ""
        sheet.set(alias, f"{value} {unit}".strip() if unit else value)
        updated.append(alias)

    doc.recompute()
    doc.save()
    print(f"Synced {len(updated)} parameters: {', '.join(sorted(updated))}")
    return updated


def sync_table(doc=None, csv_path=None, origin="A1"):
    """cad/params-table.csv -> a FreeCAD Configuration Table.

    Row 1 is the header. Row 2 is left for FreeCAD to fill with the active
    configuration. Rows 3+ are one DOQS model each, so the `Configuration`
    enum a parent sees is exactly the list of model slugs.
    """
    import FreeCAD

    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        raise RuntimeError("No active FreeCAD document.")
    sheet = _sheet(doc)
    path = Path(csv_path) if csv_path else _here() / TABLE_CSV
    if not path.exists():
        raise RuntimeError(
            f"{path} not found. Run: python doqs/scripts/resolve_params.py --table"
        )

    rows = _rows(path)
    header, models = rows[0], [r for r in rows[1:] if r and r[0].strip()]
    if header[0] != TABLE_KEY:
        raise RuntimeError(f"{path}: first column must be {TABLE_KEY!r}")

    col0, row0 = ord(origin[0]), int(origin[1:])
    for i, name in enumerate(header):
        sheet.set(f"{chr(col0 + i)}{row0}", name)
    # Row row0+1 stays empty: FreeCAD writes the active configuration there.
    for r, model in enumerate(models, start=row0 + 2):
        for c, value in enumerate(model):
            sheet.set(f"{chr(col0 + c)}{r}", value)

    doc.recompute()
    doc.save()
    print(
        f"Wrote a {len(models)}-configuration table at {origin}: "
        f"{', '.join(m[0] for m in models)}.\n"
        f"If this is the first time, right-click {chr(col0)}{row0 + 1} -> "
        "'Configuration table' to bind it."
    )
    return [m[0] for m in models]


def export_params(doc=None, csv_path=None):
    """Pull current spreadsheet values back into params.csv, preserving text."""
    import FreeCAD

    doc = doc or FreeCAD.ActiveDocument
    sheet = _sheet(doc)
    path = Path(csv_path) if csv_path else _here() / ACTIVE_CSV

    existing = {}
    if path.exists():
        rows = _rows(path)
        header = rows[0]
        for row in rows[1:]:
            if row:
                existing[row[0]] = dict(zip(header, row))

    out = []
    for alias in sorted(p for p in dir(sheet) if not p.startswith("_")):
        try:
            value = getattr(sheet, alias)
        except Exception:
            continue
        if not isinstance(value, (int, float)):
            continue
        prior = existing.get(alias, {})
        out.append([alias, value, prior.get("unit", ""), prior.get("description", "")])

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["alias", "value", "unit", "description"])
        writer.writerows(out)
    print(f"Exported {len(out)} parameters to {path}")
    return out


if __name__ == "__main__":
    sync_active()
