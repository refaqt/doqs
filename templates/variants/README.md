# Product-family templates

Copy these into a family repository (or into `modules/<family>/` while the
family is still embedded). See [`docs/variants.md`](../../docs/variants.md) for
what each one does and when you need it.

| Template | Copy to | Purpose |
|---|---|---|
| `catalog.toml` | family root | Commercial SKU → composition + model |
| `core-okh.toml` | `modules/<core>/okh.toml` | The shared core; declares the length models |
| `composition-okh.toml` | `modules/<core>-<opts>/okh.toml` | A thin composition module |
| `instance-okh.toml` | **consumer repo** `modules/<name>/okh.toml` | A machine's choice of variant |
| `cad/params/default.csv` | `modules/<core>/cad/params/` | Dense base set, with derived values |
| `cad/params/500mm.csv` | `modules/<core>/cad/params/` | A sparse length override |
| `bom/sources.toml` | `modules/<core>/bom/` | Length-table and vendor-geometry bindings |
| `bom/tables/rail.csv` | `modules/<core>/bom/tables/` | One row per stocked length |
| `cad/vendor/vendor-index.csv` | `modules/<any>/cad/vendor/` | Provenance for purchased-part geometry |

The FreeCAD Configuration Table that lets a parent machine pick a length on a
Variant Link is written by `doqs/scripts/cad_sync_params.py` — a doqs tool, not
a per-module copy. From the core module's root, inside FreeCAD:

```python
exec(open("doqs/scripts/cad_sync_params.py").read())
sync_table()
```
