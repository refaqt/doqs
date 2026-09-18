# Naming conventions

Canonical rules for **machines**, **modules**, **parts**, and **version fields** in DOQS projects. Enforced by `doqs/scripts/validate_names.py` and documented in [ADR: naming and versioning](decisions/2026-06-04_naming-and-versioning.md).

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
| Family option module | `drive-stepper`, `feedback-linear` — `<axis>-<value>`, under the core's `modules/` |
| Family composition module | `linear-stage-servo-linear` — `<core>-<option>-<option>` |
| Instance module (consumer repo) | `x-stage`, `y-stage` — name the **role in this machine**, not the product bought |
| Adapter | `modules/adapters/<from>-to-<to>/` e.g. `spindle-mount-v1-to-v2` |

**Do not** encode dimensions or materials in module folder names. A composition
names its *options*, never its length: `linear-stage-servo-linear`, never
`linear-stage-500mm`. Length is a model slug — see below.

### Where a module may sit

A module folder sits in one of two places, and nowhere else:

- directly under a `modules/` folder, for example `modules/x-axis/`
- directly under `modules/adapters/`, for example `modules/adapters/spindle-mount-v1-to-v2/`

Every module may carry its own `modules/` folder, so the same rule repeats at
every depth: `modules/x-axis/modules/drive-belt/` is a module too.

Everything else inside a module is **content**, not a module. The first-level
folders `bom/`, `cad/`, `architecture/`, `docs/`, `manufacturing/`,
`simulation/` and `measurement/`, and every folder inside them, hold files for
the module they belong to. They never need an `okh.toml`. See
[Architecture — Folder Structure](architecture.md#folder-structure) for the
full list.

`validate_names.py` uses this rule. It warns about a folder in a module
position that has no `okh.toml`, and leaves content folders alone.

### Extracted module repositories

When a module becomes its own Git repo, keep the **same slug** as the folder (`x-axis`). The `repo` URL and organization disambiguate globally. Avoid prefixed names like `qarve-x-axis` unless publishing a fork.

### Machine repositories

A product codename (`qarve`) is fine. Descriptive repo names (`cnc-mill-300`) are optional for new products.

## Parametric model slugs

Declared in `[[model]]` / `cad/params/<model>.csv`:

- Same charset as module slugs: `default`, `500mm`, `800mm`
- Dimensions are **expected** here — this is the one place they belong. They
  stay out of module folder names.
- One axis of variation per slug. `500mm-hd` mixes length with a rail grade and
  turns the catalogue into a cartesian list; prefer a length model × a
  composition. Keep it only as a last resort.
- The slug is also the FreeCAD `Configuration` value a parent selects on a
  Variant Link, and appears verbatim in `catalog.toml` and `build.toml`.

## Commercial SKU ids

Declared in `catalog.toml` (`[[sku]] name`):

**Pattern:** `^[A-Z0-9]+(-[A-Z0-9]+)*$` (e.g. `ALS-SL-500`)

Uppercase, so a SKU never reads like a module slug. Commercial names live only
in `catalog.toml`; pricing sheets join on them and never dictate folder names.

## Supplier geometry under `cad/vendor/`

Files and folders keep the **supplier's own part number, verbatim** — `AM8113`,
`HGR20R500`, `beckhoff/`, `hiwin/`. This is an explicit exception to kebab-case:
the part number is the identifier you order by and search for, and rewriting it
breaks that link. Provenance goes in `cad/vendor/vendor-index.csv`.

## Variant export paths

Variant geometry is generated on demand, not committed per model
([variants.md](variants.md#exports-are-not-committed-per-model)). Where it is
written — `cad/exports/<model>/` or `builds/<id>/exports/` — the **model slug is
allowed in the path**, dimensions and all. The rule forbidding dimensions
applies to module folder names only.

## Simulation case slugs

Folders under `simulation/cases/` and matching `simulation/results/`:

- Same kebab-case charset as module slugs: `carriage-deflection`, `thermal-soak`
- Name the **study**, not dimensions or materials — put numeric values in case config files
- See [Architecture — Simulation](architecture.md#simulation) for layout and traceability rules

## Measurement campaign slugs

Folders under `measurement/cases/` and matching `measurement/results/`, and the `campaign` column of
`measurement/data-index.csv`:

- Same kebab-case charset as module slugs: `tap-tests`, `stability-tests`, `thermal-drift`
- Name the **study**, not the conditions — spindle speed, feed, material and axis are data, and belong
  in the manifest columns and case config, never in the folder name
- Individual runs inside a campaign are dated directories, `YYYY-MM-DD_NNN[_variant]/`, e.g.
  `2026-05-07_001_stepper` — the date and sequence stay in the run folder, not in the campaign slug
- See [Architecture — Measurement](architecture.md#measurement) for layout and manifest rules

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

### `spec`, `equiv_class`, `brand` and `part`

- **`spec`:** Human-readable requirement or norm designation (e.g. `DIN912 M4x10 A4-70`, `SPDT 5A lever`).
- **`equiv_class`:** Short interchange tag for parts you may swap without a design change (e.g. `SPDT-5A-LEVER`).
- **`id`:** Internal handle; keep stable across sourcing changes.
- **`brand`:** The name on the part — `HIWIN`, `Beckhoff`, `DIN`. Stable for decades. **Not** the
  supplier you buy from: that is commercial and left the bill of materials with the prices.
- **`brand_pn`:** The brand's own part number, **verbatim** (`HGR20R500`, `AM8113-0F20`). The same
  exception to kebab-case that `cad/vendor/` paths get, and for the same reason: it is the string
  you order by and search for.
- **`part`:** Optional reference into a parts library, `stoq:hiwin/hgr-rail#HGR20R500`. When it is
  set, `brand` and `brand_pn` must agree with the library. See [parts-library.md](parts-library.md).

### No prices in the bill of materials

Cost, distributors and distributor part numbers are not design data and left these columns on
2026-09-18. A separate application answers what a machine costs, joining on `part`, or on `brand`
plus `brand_pn`. See [ADR-006](decisions/2026-09-18_money-out-of-the-bom.md).

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
python doqs/scripts/validate_names.py
python doqs/scripts/validate_okh.py
python doqs/scripts/validate_licenses.py
```

Flags: `--root PATH`, `--strict-lexicon`, `--warnings-only` (naming), `--expected-version` (OKH).

## Related

- [Variants](variants.md) — product families, model slugs, SKU catalogue, instance modules
- [Architecture](architecture.md) — folder layout, BOM columns, design session checklist
- [CONTRIBUTING.md](../CONTRIBUTING.md) — PR validation gates
- [Using doqs](using-doqs.md) — what to run, and which page to read for which job
