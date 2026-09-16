# ADR-003 — Product families: parameters, compositions, and instance modules

- **Date:** 2026-09-15
- **Status:** Accepted
- **Supersedes:** nothing. Extends [ADR-001 naming and versioning](2026-06-04_naming-and-versioning.md).

## Context

DOQS described two variant mechanisms in `architecture.md` — `[[model]]` with
`cad/params/<model>.csv` for numbers, and thin composition modules for
architecture — but neither was implemented. `resolve_params.py` existed only as
a code snippet inside the prose.

REFAQT is publishing a linear-stage **family**: several standard lengths × a few
motor options × a few feedback options, which a later machine project must be
able to drop into a larger assembly. The aqtuator ADR
[2026-08-31 linear-stage variant structure](https://github.com/refaqt/aqtuator/blob/cursor/linear-stage-variant-structure-1aee/docs/decisions/2026-08-31_linear-stage-variant-structure.md)
(ref-1) chose the right split and then listed seven spec gaps in DOQS that
block it.

Its recommendation is sound and is adopted unchanged: length is a parameter of a
shared core, motor and feedback are compositions, the extractable unit is the
**family** rather than the SKU, and FreeCAD suppression is not a product
configurator.

One question ref-1 leaves open turned out to drive most of this decision. A Git
submodule is a frozen mirror of another repository: everyone who adds it gets
identical files, and there is **no slot inside it** for "my machine wants the
500 mm servo version". ref-1 answers "pin it in `builds/<id>/build.toml`" — but
a build lockfile records a machine that already exists. It cannot help while the
machine is still being designed, and it has nowhere to put a resolved BOM, so a
supplier change upstream could reach purchasing with no reviewable diff.

## Decision

### 1. Adopt ref-1's split, and implement it

Length is a parametric `[[model]]` on the shared core. Drive and feedback are
option modules combined by thin composition modules, which are **sibling folders
in the family repo referencing the core by relative path** — never nested
submodules. Model slugs never mix axes (`800mm-servo-linear` is forbidden).

### 2. Parameters may be derived

A `value` beginning with `=` is an arithmetic expression over other aliases,
evaluated by a whitelist-only evaluator (arithmetic, parentheses, `min max abs
round ceil floor`; no attribute access, indexing or imports; cycles reported by
name).

This is not a convenience. Without it, every length override must restate every
number that follows from length, and changing one derivation means editing every
model file — "sparse" in name only, and the propagation problem ref-1 exists to
avoid. With it, a length override is typically one row.

### 3. Off-the-shelf lengths resolve from a supplier table

`bom/tables/<part>.csv` holds one row per stocked length — part number, price,
mass, and the vendor STEP — bound to a BOM row by `bom/sources.toml`.
`bom/bom.csv` keeps its exact 16-column header, so every existing validator
reads it unchanged.

Adding a length then needs **no BOM edit**. `match = "exact"` refuses a length no
supplier stocks, turning "I invented a 640 mm variant" into a CI failure rather
than a purchasing surprise. `nearest-up` buys the next stock length and records
the cut in `notes`.

### 4. A consumer's choice lives in an instance module

A machine repo commits a small folder of its own — not a submodule — holding an
`[instance]` table (family, composition, model, optional SKU and extra
overrides), the machine-side assembly, and the **committed** resolved
parameters, resolved BOM and resolved vendor geometry.

The folder holds the choice, never the design, so nothing can drift. The
committed generated files are the point: their git diff is exactly "what did
this family update change for *my* variant". `--check` fails on staleness and
validation fails when the family no longer declares the selected model or
composition, so a family update cannot silently change what a machine buys.

For the zero-override case, `[[hasComponent]]` gains `composition` and `model`
keys (ref-1 gap 5) as a shortcut needing no folder.

**Configuration and pinning are separate.** `[instance]` says which variant, at
design time. `builds/<id>/build.toml` says which version of it, after the fact.

### 5. A parent sees real parametric geometry

`resolve_params.py --table` emits a dense `cad/params-table.csv`, one row per
model, which `sync_params.py` writes into the FreeCAD spreadsheet as a
**Configuration Table**. The composition document then exposes a `Configuration`
enum whose values are the DOQS model slugs, and a parent machine inserts it as a
**Variant Link** at its chosen length — live parametric geometry, in the
parent's own document, with the submodule never written to. Two instances of one
family can sit at different lengths in the same machine.

This carries a known risk (see *Consequences*).

### 6. Variant geometry is not committed per model

ref-1 gap 3 asked for model-aware `cad/exports/`. **Rejected.** A family with a
handful of lengths and a few compositions would carry a growing export matrix
that every core change invalidates. A module with more than one `[[model]]`
omits `export` from `okh.toml`, `**/cad/exports/` is gitignored, and
`export_variant.py` produces geometry on demand. The one place it is committed
is `builds/<id>/`, recording what a real machine was built to.

### 7. Purchased-component geometry has a home

`cad/vendor/`, inside the module whose BOM buys the part, so the module stays
independently extractable. It carries its own `LICENSE` stub — writing the
CERN-OHL-S hardware stub over supplier files would claim a licence on files we
do not own — and a `vendor-index.csv` manifest in the same shape as
`measurement/data-index.csv`. Files marked `fetch-only` are not committed; only
their manifest row is, and validation warns rather than fails on their absence
so CI stays green on a fresh clone. Vendor files keep the supplier's part number
verbatim, an explicit exception to kebab-case.

This was not in ref-1's list. It surfaced from the same question: length
variants of a rail need one STEP per length, so the vendor `cad` path resolves
from the same table as the part number.

### 8. A declarative option space is specified but not built

ref-1 says not yet, and that is right at this size. `docs/variants.md` documents
the shape and states the trigger: build it when the curated composition list
would exceed about six, or when a third option axis appears.

## Consequences

- A mounting-point change is one commit in the core. Every composition and every
  length picks it up, because they link the same files.
- A machine vendors **one** submodule and commits one small folder per use.
- Adding a length costs one sparse CSV and one table row. Adding an option costs
  one module. Neither costs a repository.
- The usage graph answers "who uses the 500 mm servo-linear?" — `used_by`
  entries now carry `model`, `composition` and `sku`.
- `aggregate_bom.py` had to become family-aware: naively walking
  `**/bom/bom.csv` would double-count a vendored catalogue and quote
  unresolved `{alias}` rows for lengths nobody selected.
- **Open risk.** Variant links keep a private copy inside the consuming
  document, and there are open FreeCAD bugs where config-table variants get
  confused about fillet edges
  ([FreeCAD#19182](https://github.com/FreeCAD/FreeCAD/issues/19182)). The spec
  requires a two-configuration spike on real geometry before a project relies on
  it, and documents the fallback: one `.FCStd` per composition, length still a
  spreadsheet configuration inside it, linked directly. Nothing on the text side
  changes either way.
- Machine repos that already commit `cad/exports/` are unaffected: the gitignore
  rule ships in the DOQS template, and single-model modules keep their `export`
  keys.
- `check_names.py` (now `validate_names.py`) no longer flags a nested `modules/` container as an orphan —
  a latent bug that only appeared once a fixture nested modules the way
  `architecture.md` has always described.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| One repo or long-lived branch per SKU | A shared fix must be cherry-picked across every SKU; fights "versions are tags on one history" |
| One parent repo per SKU with the core as a child submodule | Every shared fix means a pointer bump in every parent — the submodule tax × the catalogue |
| One mega-assembly with `Visibility` / `Suppressed` flags | Not a DOQS mechanism and a weak FreeCAD one; invisible to `git diff`, validators and agents; different SKUs genuinely provide different interfaces |
| Model slugs spanning both axes (`800mm-servo-linear`) | Turns the catalogue into a cartesian `[[model]]` list |
| Selection only on `[[hasComponent]]`, no instance module | Nowhere to commit a resolved BOM, so a family update can change what you buy with no reviewable diff |
| Committed per-model STEP exports | An export matrix every core change invalidates |
