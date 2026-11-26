# CSV parameters and FreeCAD

Part of the doqs specification. Start at the [overview](../architecture.md).

## Linking CSV Parameters to FreeCAD

The FreeCAD Spreadsheet workbench can drive model dimensions through **cell aliases** referenced in sketch constraints via expressions (e.g., a sketch constraint reads `Params.rail_length`). This means parameter values can be managed as plain text in a `params.csv` file and synced into FreeCAD programmatically.

### Data Flow

```
cad/params/default.csv      ← base parameter set (every alias appears here)
cad/params/<model>.csv      ← sparse override file: only rows that differ
     │
     │  cad/resolve_params.py <model>   (selects active model)
     ▼
cad/params.csv              ← ACTIVE model — generated, do not edit by hand
     │
     │  doqs/scripts/cad_sync_params.py  (run via FreeCAD Python)
     ▼
FreeCAD Spreadsheet (Params)
     │
     │  FreeCAD expressions in sketch constraints
     ▼
Model geometry (rail_length, carriage_thickness, motor_offset, …)
```

If a module has only one model, `cad/params/default.csv` is the only file in `cad/params/` and `cad/params.csv` is just a copy of it. The resolver step is still run for consistency.

SysML requirements state what the machine must do. The `default.csv` parameter file holds the numbers for the canonical model. A parameter that a requirement sets names that requirement in its `source` column, and `validate_variants.py` checks that the requirement exists in `architecture/*.sysml`. See [ADR-012](../decisions/2026-10-06_every-dimension-has-a-source.md).

### Parameter File Format

The format is the same for `default.csv` and any model override file:

```
alias,value,unit,basis,source,description
rail_length,400,mm,requirement,XAxis::TravelRequirement.rail_length_mm,Total length of X-axis linear rail
carriage_thickness,8,mm,simulation,simulation/carriage-stiffness/result.md,Carriage plate thickness
motor_offset,=rail_length / 10 + 5,mm,,,Distance from rail end to motor shaft centre
belt_pitch,2,mm,catalogue,docs/datasheets/gt2-belt.pdf p3,GT2 belt tooth pitch
pulley_teeth,20,,design,docs/decisions/2026-05-01_belt-drive.md,Number of teeth on motor pulley
```

Every dimension has a reason ([ADR-012](../decisions/2026-10-06_every-dimension-has-a-source.md)).
A row is either **independent** (a number someone chose) or **derived** (a `=` formula over
other rows). Keep the independent rows few. Each one fills `basis` and `source`:

| `basis` | Where the value comes from | `source` holds |
| --- | --- | --- |
| `requirement` | A SysML requirement | Its name, like `XAxis::TravelRequirement.rail_length_mm`. It must exist in `architecture/*.sysml` |
| `catalogue` | A supplier table or drawing | The document and page |
| `estimated` | Read off a supplier figure; a placeholder | The figure. Always a warning until replaced |
| `measured` | Measured on a real part | Who measured it, and when |
| `standard` | A standard | The standard and size, like `ISO 4762 M6` |
| `simulation` | A calculation or simulation | The file under `simulation/`. It must exist |
| `design` | A choice the designer made | A file in `docs/decisions/`, or a short reason |

A derived row leaves `basis` and `source` empty: its formula is the reason. In an override
file an empty `basis` keeps the one from `default.csv`; fill it when the reason changes too.
`validate_variants.py` warns about a row without a reason. With `--strict-parametric` it fails.

- `default.csv` must include **every** alias used by the FreeCAD Spreadsheet.
- A model override file (e.g. `500mm.csv`) includes **only the rows that differ** from `default.csv`. Aliases not present in the override inherit from `default.csv`.
- `alias` must match the alias assigned to the corresponding FreeCAD Spreadsheet cell.
- `unit` may be empty for dimensionless values.
- All param files are committed to Git — diffs show parameter changes clearly.
- The active `cad/params.csv` is **generated** by `resolve_params.py` and is `.gitignore`d.

### `cad_sync_params.py` — Sync Script

A **doqs script, not a per-module copy** — the same arrangement as
`resolve_params.py` above. It runs from within FreeCAD (the built-in Python
console or a macro), or headlessly, from the module root:

```python
# FreeCAD Python console, from the module root
exec(open("doqs/scripts/cad_sync_params.py").read())
sync_active()          # cad/params.csv      -> aliased Spreadsheet cells
sync_table()           # cad/params-table.csv -> a Configuration Table
export_params()        # Spreadsheet         -> cad/params.csv (reverse)
```

```powershell
FreeCADCmd doqs/scripts/cad_sync_params.py
```

Each entry point takes `cad_dir` to locate the module's `cad/`, defaulting to
`cwd/cad`. Pass it explicitly when the working directory is not the module root
— a generated macro, for instance, where `__file__` points at a temp file.
`sync_active()` also takes `save` (default `True`). A caller that only needs
geometry in memory — `export_variant.py`'s macro — passes `save=False`, so a
second process never writes a committed `.FCStd`.

See [`scripts/cad_sync_params.py`](../../scripts/cad_sync_params.py) for the
current source; `sync_table()` and the Configuration Table are described in
[variants.md](../variants.md#seeing-the-chosen-variant-in-cad).

### Setting Up Aliases in FreeCAD

Before the sync script can work, each cell in the Spreadsheet must have its alias set once manually:

1. Open the `.FCStd` file in FreeCAD.
2. Open the Spreadsheet workbench, add a row for each parameter.
3. Right-click each value cell → *Properties* → *Alias* → enter the alias (matching the `alias` column in `params.csv`).
4. In **every** dimension of every sketch, and in every feature size (Pad length, hole
   diameter, pattern count and length), click the expression icon and enter
   `Params.alias_name`, or a formula of aliases. Never leave a typed number.
5. Fully constrain every sketch. Repeated features are one feature plus a pattern, driven by a
   count and a pitch.

The build records every sketch that can still move and every typed size in the fingerprint,
and `validate_cad.py` reports them. See [agent-cad.md](../agent-cad.md#every-dimension-has-a-reason).

This setup is one-time. After that, all parameter updates go through `params.csv` + `cad_sync_params.py`.

### Export Params to CSV (Reverse Direction)

`export_params()` in the same script pulls current Spreadsheet values back into
`cad/params.csv`, preserving the `unit`, `basis`, `source` and `description` columns of rows that
already exist. Use it when parameters were changed interactively in FreeCAD and
the CSV needs to catch up.

```python
exec(open("doqs/scripts/cad_sync_params.py").read())
export_params()
```
