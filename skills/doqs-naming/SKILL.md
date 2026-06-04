---
name: doqs-naming
description: >-
  Apply DOQS naming and versioning rules when creating or renaming modules,
  BOM rows, parts, adapters, or release tags. Run validate_all after structural changes.
---

# DOQS naming and validation

## When to use

- New or renamed folders under `modules/`
- BOM `id` / `name` rows or `bom/bom.csv` headers
- `[[part]]`, `[[model]]`, or adapter paths
- Release tagging and `okh.toml` `version` bumps
- Exported drawings (title block revision)

## Rules (summary)

Read the canonical spec:

- `doqs/docs/naming.md`
- `doqs/docs/naming-lexicon.md`

Quick reference:

| Item | Rule |
|------|------|
| Module folder | kebab-case function: `x-axis`, `drive-belt` |
| Adapter | `modules/adapters/<from>-to-<to>/` |
| BOM `id` | `PREFIX-NNN` per module (e.g. `MEC-001`) |
| `okh.toml` version | semver without `v`: `1.2.0` |
| Git tag | `v1.2.0` |
| FreeCAD `Comment` | `Module: <slug> — see okh.toml` (no per-release bump) |
| Drawing export | Title block `Rev: <semver>` at export time |

## Mandatory validation

From the **machine repository root** after OKH, BOM, or path changes:

```powershell
python doqs/scripts/validate_all.py
```

Before tagging:

```powershell
python doqs/scripts/validate_okh.py --expected-version X.Y.Z
```

Gradual adoption on existing machines: `python doqs/scripts/check_names.py --warnings-only` until BOM and folder names are migrated.

## Do not

- Put dimensions or materials in module folder names
- Use `v` prefix in `okh.toml` `version`
- Bump FreeCAD file metadata on every patch release
- Duplicate BOM `id` within one module BOM file

See [reference.md](reference.md) for examples.
