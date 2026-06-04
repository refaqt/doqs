# Naming conventions

Canonical rules for **machines**, **modules**, **parts**, and **version fields** in DOQS projects. Enforced by `doqs/scripts/check_names.py` and documented in [ADR: naming and versioning](decisions/2026-06-04_naming-and-versioning.md).

## Principles

- Names are stable, URL-safe, and meaningful in Git paths.
- Name the **function**, not the shape or material (`x-axis`, not `aluminium-plate-assembly`).
- Parametric variants (300 mm vs 500 mm) live in `cad/params/`, not in folder names.
- A **machine** is the top-level product (repository root module).
- A **module** is any folder with the standard DOQS layout and an `okh.toml`.
- A **part** is a manufactured item declared as `[[part]]` in OKH or as a leaf module.

## Module and folder names

**Pattern:** `^[a-z0-9]+(-[a-z0-9]+)*$` (kebab-case)

| Rule | Example |
|------|---------|
| Functional noun | `x-axis`, `frame`, `spindle` |
| Structural variant suffix | `x-axis-belt`, `x-axis-ballscrew` |
| Nested shared sub-module | `drive-belt`, `drive-ballscrew` under `modules/x-axis/modules/` |
| Adapter | `modules/adapters/<from>-to-<to>/` e.g. `spindle-mount-v1-to-v2` |

**Do not** encode dimensions or materials in module folder names.

### Extracted module repositories

When a module becomes its own Git repo, keep the **same slug** as the folder (`x-axis`). The `repo` URL and organization disambiguate globally. Avoid prefixed names like `qarve-x-axis` unless publishing a fork.

### Machine repositories

A product codename (`qarve`) is fine. Descriptive repo names (`cnc-mill-300`) are optional for new products.

## Parametric model slugs

Declared in `[[model]]` / `cad/params/<model>.csv`:

- Same charset as module slugs: `default`, `500mm`, `500mm-hd`
- No bare dimensions in module folder names

## BOM part IDs

**Pattern:** `^[A-Z]{2,4}-[0-9]{3}$` (e.g. `MEC-001`, `SW-001`)

| Prefix | Category |
|--------|----------|
| MEC | Machined / manufactured mechanical parts |
| STD | Standard purchased parts (fasteners, bearings) |
| ELC | Electrical / electronic components |
| SW | Switches and sensors |
| MOT | Motors and actuators |
| HW | Generic hardware / fasteners |
| PRF | Profiles and extrusions |
| BRK | Brackets and fabricated sheet/plate parts |

Sequences are **scoped per module** `bom/bom.csv`. The same `MEC-001` may appear in different modules; the module path disambiguates globally.

Duplicate `id` values within one BOM file are not allowed.

### `spec` and `equiv_class`

- **`spec`:** Human-readable requirement or norm designation (e.g. `DIN912 M4x10 A4-70`, `SPDT 5A lever`).
- **`equiv_class`:** Short interchange tag for LTS supplier substitutions (e.g. `SPDT-5A-LEVER`).
- **`id`:** Internal handle; keep stable across sourcing changes.

## Interface names

**Pattern:** `{Assembly}{Role}Interface` (PascalCase), e.g. `XAxisOutputInterface`, `FrameMountInterface`.

Interface **version** lives in `okh.toml` (`version = "1.0"`), not in folder or file names.

## Display names and lexicon

BOM `name` and `[[part]].name` should use words from the [naming lexicon](naming-lexicon.md). The validator reports unknown tokens as **warnings** (or **errors** with `--strict-lexicon`).

## Versioning (three surfaces)

| Where | Value | Notes |
|-------|-------|-------|
| `okh.toml` `version` | `1.2.0` (semver, **no** `v`) | Authoritative for the module |
| Git tag | `v1.2.0` | Git convention |
| `builds/*/build.toml` | `version = "v1.2.0"` | Pins exact tag per module |
| FreeCAD document `Comment` | `Module: x-axis — see okh.toml` | Stable pointer; do not bump each release |
| Drawing title block (export) | `Rev: 1.2.0` | Set at export time for machinists |

Before tagging a release:

```powershell
python doqs/scripts/validate_okh.py --expected-version 1.2.0
```

## Validation

From the **machine repository root**:

```powershell
python doqs/scripts/validate_all.py
```

Individual checks:

```powershell
python doqs/scripts/check_names.py
python doqs/scripts/validate_okh.py
```

Flags: `--root PATH`, `--strict-lexicon`, `--warnings-only` (naming), `--expected-version` (OKH).

## Related

- [Architecture](architecture.md) — folder layout, BOM columns, design session checklist
- [CONTRIBUTING.md](../CONTRIBUTING.md) — PR validation gates
- [Agent guide](agent-guide.md) — Cursor skill install
