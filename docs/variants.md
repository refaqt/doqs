# Product families and variants

How to publish one design in many configurations — several lengths, a few motor
options, a few feedback options — without the module count exploding, and how a
machine project consumes one configuration of it.

Read [architecture.md](architecture.md) first for the module layout this builds
on. The decision behind this page is
[ADR: product-family variants](decisions/2026-09-15_product-family-variants.md).

---

## The two kinds of difference

DOQS splits variation along one line, and nearly everything follows from it:

| The difference is… | Mechanism | Cost of one more |
|---|---|---|
| **Numbers only** — 300 mm vs 500 mm travel | A parametric `[[model]]` on the shared core: `cad/params/<model>.csv` | One sparse CSV, one length-table row |
| **Architecture** — stepper vs servo, encoder or none | A nested **option module** plus a thin **composition module** | One option module, one thin composition |

Do not flatten these into each other. A model slug like `800mm-servo-linear`
mixes both axes and turns the catalogue into a cartesian `[[model]]` list.
Length stays a parameter; drive and feedback stay compositions. Three
compositions × five length CSVs is a fifteen-SKU catalogue built from eight
files, not fifteen CAD trees.

---

## The five nouns

| Noun | Where it lives | What it holds |
|---|---|---|
| **Family** | One repo (or `modules/<family>/` while still embedded) | `okh.toml`, `catalog.toml` |
| **Core module** | `<family>/modules/<core>/` | *All* the shared geometry, `cad/params/`, the base BOM |
| **Option module** | `<family>/modules/drive-*`, `feedback-*` | One architectural choice: its own CAD, BOM, interfaces |
| **Composition module** | `<family>/modules/<core>-<opts>/` | Thin: an assembly linking core + one option per axis, its own purchased-parts BOM, the interfaces *this* SKU offers |
| **Instance module** | The **consumer** repo, `modules/x-stage/` — *not* a submodule | The choice, plus the resolved parameters and BOM, plus the machine-side assembly |

```
linear-stage/                          ← the FAMILY repo
├── catalog.toml                       commercial SKU → composition + model
└── modules/
    ├── linear-stage/                  ← CORE: all shared geometry
    │   ├── cad/params/{default,500mm,800mm}.csv
    │   ├── cad/params-table.csv       generated, committed → FreeCAD config table
    │   ├── bom/{bom.csv,sources.toml,tables/hgr20-rail.csv}
    │   ├── cad/vendor/                purchased-component geometry
    │   └── modules/
    │       ├── drive-stepper/  drive-servo/          ← OPTIONS
    │       └── feedback-none/  feedback-linear/
    ├── linear-stage-stepper/          ← COMPOSITION: core + stepper + none
    └── linear-stage-servo-linear/     ← COMPOSITION: core + servo + encoder
```

### Compositions do not contain the core as a submodule

They are **sibling folders in the same repository**, referencing the core by a
family-root-relative path in a `[composition]` table. A submodule there would
mean a pointer bump in every composition on every shared-core commit — the
submodule tax multiplied by the catalogue. Because they are plain folders, one
commit to the core is visible to every composition and every length at once.

### Keep compositions few

Each one is a real module with its own BOM and assembly guide. Before adding a
fourth, ask whether a parameter can absorb the difference. A cover strip, a hole
pattern every carriage tolerates, or a fastener length that follows travel is a
parameter. Prefer over-holing a shared carriage to a second carriage module,
unless the holes hurt stiffness, sealing, or the machining setup.

---

## Sparse overrides

`cad/params/default.csv` is the **dense** base: every alias appears exactly
once. `cad/params/<model>.csv` is a **sparse override**: only the rows that
differ. Merging replaces matching aliases and inherits `unit` and `description`,
so an override row can be just `alias,value`.

The thing that makes them genuinely sparse is **derived values**. A `value` that
starts with `=` is an arithmetic expression over other aliases:

```csv
# cad/params/default.csv
alias,value,unit,description
rail_length,300,mm,Guide rail length — INDEPENDENT
carriage_travel,=rail_length - 180,mm,Usable carriage travel — DERIVED
extrusion_length,=rail_length + 40,mm,Base extrusion cut length — DERIVED
cover_length,=extrusion_length - 10,mm,Dust cover strip length — DERIVED
```

```csv
# cad/params/500mm.csv — the whole file
alias,value,unit,description
rail_length,500,mm,Guide rail length
```

Without derivations every override would have to restate every number that
follows from length, and changing one rule would mean editing every model file —
sparse in name only. With them, a length is one row, and a rule change is one
edit that every length picks up.

Expressions may use `+ - * / // % **`, parentheses, and `min max abs round ceil
floor`, over alias names only. Nothing else parses: there is no attribute
access, no indexing, no imports. Order does not matter — resolution iterates —
and a circular reference is reported by name. A model override *may* pin a
derived alias to a literal; prefer not to.

```bash
python doqs/scripts/resolve_params.py --module modules/linear-stage --model 500mm
python doqs/scripts/resolve_params.py --table          # every module, every model
python doqs/scripts/resolve_params.py --table --check  # CI: fail if stale
```

Two outputs, deliberately different in lifecycle:

| File | Committed? | What it is |
|---|---|---|
| `cad/params.csv` | No — gitignored | The single **active** model. Feeds `cad_sync_params.py` and BOM resolution |
| `cad/params-table.csv` | **Yes** | Dense, one row per model. Becomes the FreeCAD Configuration Table |

---

## Seeing the chosen variant in CAD

`cad/params-table.csv` is what makes a family usable from a parent machine.

```csv
configuration,carriage_travel,cover_length,end_plate_thickness,extrusion_length,rail_count,rail_length,screw_length
default,120,330,12,340,2,300,270
500mm,320,530,12,540,2,500,470
800mm,620,830,16,840,2,800,770
```

From the core module's root, run `sync_table()` inside FreeCAD:

```python
exec(open("doqs/scripts/cad_sync_params.py").read())
sync_table()
```

It writes that table into the `Params` spreadsheet; right-click cell `A2` →
*Configuration table* once to bind it. The document then carries a `Configuration` property whose values are
exactly the DOQS model slugs.

A parent machine inserts the composition assembly as a **Variant Link** and sets
`Configuration` to `500mm`. It gets a live, fully parametric model at 500 mm,
inside its own document. A second variant link in the same machine can sit at
`300mm`. The family submodule is never written to.

> **Verify before you rely on it.** Configuration Tables and Variant Links are
> mainline FreeCAD since 0.20, but a variant link keeps a private copy inside
> the consuming document, and there are open bugs where config-table variants
> get confused about fillet edges
> ([FreeCAD#19182](https://github.com/FreeCAD/FreeCAD/issues/19182)). Build a
> two-configuration throwaway first: variant-link it from a parent, change a
> core dimension, refresh, confirm the parent updates and keeps its own
> configuration. If it does not hold for your geometry, keep one `.FCStd` per
> composition with length still a spreadsheet configuration inside it, and link
> it directly — nothing on the text side of this page changes.

### Exports are not committed per model

A family with a handful of lengths and a few compositions would otherwise carry
a growing matrix of STEP files that every core change invalidates. So a module
with more than one `[[model]]` **omits** `export` from its `okh.toml`, and
`**/cad/exports/` is gitignored. Geometry is produced when someone asks:

```bash
python doqs/scripts/export_variant.py --module modules/linear-stage-servo-linear \
    --model 500mm --out builds/serial-0042/exports/x-stage.step
```

The one place variant geometry *is* committed is under `builds/<id>/`, where it
records what a real machine was actually built to.

---

## Off-the-shelf parts that come in lengths

Rails, ballscrews and belts come in discrete stocked lengths, each with its own
part number **and its own vendor STEP**. One table gives all of it.

```csv
# bom/tables/hgr20-rail.csv
key,spec,unit_cost_eur,unit_mass_g,supplier_1,supplier_1_pn,supplier_2,supplier_2_pn,cad
300,HGR20 rail 300 mm,18.40,1290,HIWIN,HGR20R300,CPC,ARR20-300,cad/vendor/hiwin/HGR20R300.step
500,HGR20 rail 500 mm,27.10,2150,HIWIN,HGR20R500,CPC,ARR20-500,cad/vendor/hiwin/HGR20R500.step
800,HGR20 rail 800 mm,41.80,3440,HIWIN,HGR20R800,,,cad/vendor/hiwin/HGR20R800.step
```

```toml
# bom/sources.toml
[[bind]]
id      = "PRF-001"                 # the BOM row to fill
table   = "tables/hgr20-rail.csv"
key     = "rail_length"             # parameter alias selecting the row
match   = "exact"                   # exact | nearest-up | nearest-down
columns = ["spec", "unit_cost_eur", "unit_mass_g",
           "supplier_1", "supplier_1_pn", "supplier_2", "supplier_2_pn"]
```

`bom/bom.csv` keeps its exact 16-column DOQS header, so every existing validator
reads it unchanged; the binding lives in the sidecar. **Adding a length needs no
BOM edit at all.**

- `match = "exact"` refuses a length no supplier stocks. Declaring a `640mm`
  model then fails CI with *"no row for key 640. Stocked: 300, 500, 800"* —
  rather than surfacing as a purchasing surprise.
- `match = "nearest-up"` buys the next stock length and records
  `stock length 800, cut to 640` in `notes`.

### Cut-to-length stock with no per-length part number

Any BOM cell may carry `{alias}` placeholders, resolved from the parameters:

```csv
PRF-002,Extrusion,"40x80 profile, cut to {extrusion_length} mm",mechanical,1,pc,...
```

### When a table is not enough

`bom/models/<model>.csv` is a **column-sparse** overlay: only the columns
present in its header are overridden, everything else inherits.

```csv
# bom/models/800mm.csv
id,qty,notes
STD-004,6,Extra carriage bolts for the 800 mm variant
```

An unknown `id` adds a row (and must then carry the full 16-column header).
`qty = 0` removes one.

---

## Geometry of purchased components

`cad/parts/` is for parts **we manufacture**, each an OKH `[[part]]`. A bought
motor is a BOM row, not a `[[part]]`, but it still needs a solid in the
assembly. It lives in `cad/vendor/`, inside the module whose BOM buys it — not
in a shared folder at the root, because a module must stay independently
extractable. A motor STEP duplicated across two modules is cheap; a broken
relative link after extraction is not.

```
modules/drive-servo/
├── bom/bom.csv                 MOT-001, Beckhoff AM8113
├── bom/sources.toml            binds MOT-001 → the file below
└── cad/
    ├── parts/                  OUR manufactured parts
    └── vendor/
        ├── LICENSE             supplier terms — NOT CERN-OHL-S
        ├── vendor-index.csv    provenance for every file here
        └── beckhoff/
            ├── AM8113.step             supplier original
            └── AM8113-envelope.FCStd   optional simplified solid
```

```toml
[[vendor]]
id       = "MOT-001"
cad      = "cad/vendor/beckhoff/AM8113.step"
envelope = "cad/vendor/beckhoff/AM8113-envelope.FCStd"   # optional
source   = "https://www.beckhoff.com/…"
terms    = "redistributable"                             # or "fetch-only"
```

For a length-dependent part, omit `cad`: the bound table's `cad` column supplies
one file per length, so choosing `500mm` resolves the part number *and* the
geometry together.

**Licensing.** `cad/` maps to CERN-OHL-S, and writing that stub over supplier
files would claim a licence on files we do not own. So `apply_licenses.py`
writes a separate `cad/vendor/LICENSE` carving the directory out, at any module
depth. Never list a vendor file in `okh.toml` `source` or `export`.

**Files we may not redistribute.** `terms = "fetch-only"` means the file is
gitignored and only its row in `cad/vendor/vendor-index.csv` is committed — the
same manifest pattern as `measurement/data-index.csv`, with the columns
`supplier,pn,relpath,bytes,sha256,source_url,terms,retrieved_utc`. Validation
**warns** rather than fails when such a file is absent, so CI stays green on a
fresh clone.

**Naming.** Vendor folders and files keep the **supplier's own part number,
verbatim** (`AM8113`, `HGR20R500`) — an explicit exception to kebab-case.

**Assemblies link the envelope** where one exists; supplier originals are often
unusably detailed.

---

## Using a family in a machine

> A Git submodule is a frozen mirror of another repository. Everyone who adds it
> gets identical files, and **there is no slot inside it for "my machine wants
> the 500 mm servo version"**. So the choice lives in the consumer repo, beside
> the submodule, in a small folder of its own.

```
machine-repo/
├── modules/
│   ├── linear-stage/          ← submodule = THE DESIGN. You only read it.
│   └── x-stage/               ← YOUR folder = THE CHOICE. Not a submodule.
│       ├── okh.toml               [instance] — 7 lines
│       ├── cad/x-stage.FCStd      Variant Link, Configuration = "500mm"
│       ├── cad/resolved/params.csv      generated, committed
│       ├── cad/resolved/vendor-cad.csv  generated, committed
│       ├── cad/resolved/provenance.toml generated, committed
│       ├── bom/bom.csv            this instance's own rows, resolved
│       └── bom/resolved.csv       flattened purchasing list, committed
└── builds/serial-0042/build.toml  ← pins the VERSION of all of it
```

```toml
# modules/x-stage/okh.toml
[instance]
family      = "modules/linear-stage"                  # repo-root-relative
composition = "modules/linear-stage-servo-linear"     # path INSIDE the family
model       = "500mm"
sku         = "ALS-SL-500"                            # optional
# params    = "cad/params/instance.csv"               # optional extra override
```

```bash
git submodule add https://github.com/ORG/linear-stage modules/linear-stage
# write modules/x-stage/okh.toml, then:
python doqs/scripts/resolve_instance.py modules/x-stage
```

Point `[[hasComponent]]` in the machine's root `okh.toml` at
`modules/x-stage/okh.toml`, like any other module.

### Configuration is not pinning

Two different jobs, two different files, and conflating them is why a lockfile
alone cannot answer this:

| | Says | Lives in | Answers |
|---|---|---|---|
| **Configuration** | *which variant* | `[instance]` in the consumer repo | "What am I designing against, right now?" |
| **Pinning** | *which version of it* | `builds/<id>/build.toml` | "What is installed on serial-0042?" |

A build lockfile is a record of a machine that already exists. It cannot help
you while you are still drawing.

### How it stays in sync

The instance folder holds the **choice**, never the **design**. There are three
kinds of thing in it and each one has a clear sync story:

1. **The choice** (`okh.toml`) never needs syncing — it is your decision, not
   their design. But it *is* checked: if the family renames `500mm` or
   discontinues the composition, validation fails and names the problem.
   Silent breakage is not possible.
2. **The assembly** holds links, not copies — with one caveat. Because you asked
   for 500 mm and the source may sit at 300 mm, FreeCAD keeps a private copy so
   the link can hold your length. Use the link's **Refresh** action, or
   `LinkCopyOnChange = Tracking` to re-copy automatically.
3. **The generated text files** are re-made by one command — and that is a
   feature. Their git diff is exactly *"what did this family update change for
   my 500 mm servo stage?"* If the family swapped an HGR20 rail for an HGR25,
   you see it in the parts-list diff **before** you order anything.

```bash
git submodule update --remote modules/linear-stage        # take the new family
python doqs/scripts/resolve_instance.py modules/x-stage   # refresh generated files
# open x-stage.FCStd, refresh the variant link, save
python doqs/scripts/validate_all.py                       # fails if a step was skipped
```

`resolve_instance.py --check` and `validate_variants.py` both fail on stale
generated files, so forgetting is caught by CI rather than by an invoice.

### Two instances of one family

`modules/x-stage` at `500mm` and `modules/y-stage` at `default` resolve to
different rails, different motors and different STEP files, from one read-only
submodule. This is the case a single shared `params.csv` inside the submodule
cannot do at all.

### The shortcut, for the zero-override case

If you change nothing — no parameters, no machine-side assembly, no resolved
BOM to review — skip the folder and pin on the component declaration:

```toml
[[hasComponent]]
component   = ".../modules/linear-stage/modules/linear-stage-stepper/okh.toml"
composition = "modules/linear-stage-stepper"
model       = "300mm"
```

Use an instance module whenever you need to *see* the variant, override a
parameter, or review what you are buying.

### Aggregating the machine BOM

`doqs/scripts/aggregate_bom.py` takes each instance's `bom/resolved.csv` and
**skips the family checkout it points at**. Walking `**/bom/bom.csv` naively
would double-count the whole catalogue and quote unresolved `{alias}` rows for
lengths nobody selected.

### In the lockfile

```toml
[[module]]
path    = "modules/x-stage"
version = "v0.1.0"

[[module]]
path        = "modules/linear-stage"
version     = "v0.1.0"
composition = "modules/linear-stage-servo-linear"
model       = "500mm"
sku         = "ALS-SL-500"
```

`validate_build.py` reads the **composition's** interfaces, not the family
root's — a stepper SKU and a servo SKU genuinely offer different ones.

---

## Commercial names

`catalog.toml` at the family root is the join to pricing, and the only place
commercial names appear. Module folders keep functional slugs.

```toml
schema = "doqs-catalog-v1"
family = "linear-stage"

[[sku]]
name        = "ALS-SL-500"                        # commercial / pricing key
composition = "modules/linear-stage-servo-linear"
model       = "500mm"
status      = "active"                            # active | preview | eol
```

Validation refuses a SKU naming a composition that does not exist, a model the
core does not declare, a duplicate name, or a lowercase id.

---

## Recipes

### Add a length

1. `cad/params/<length>.csv` — only the **independent** rows that change.
   Derived values follow on their own.
2. Add a row to each bound length table (`bom/tables/*.csv`) — part number,
   price, mass, and the vendor `cad` path. **If the supplier does not stock it,
   stop here**: validation will refuse the model, which is the point.
3. `[[model]]` entry in the core's `okh.toml`.
4. Only if a table cannot express it: `bom/models/<length>.csv`.
5. `python doqs/scripts/resolve_params.py --table`, then `sync_table()` in
   FreeCAD.
6. `catalog.toml` rows for each composition × length you actually sell.
7. `python doqs/scripts/validate_all.py`.

No new module. No new submodule. No new repository.

### Add an option

1. A full module under `<core>/modules/<axis>-<name>/` — its own CAD, BOM,
   `architecture/` with the port definitions.
2. Declare `[[provides-interface]]` / `[[consumes-interface]]`.
3. A thin composition module combining it, with a `[composition]` table and the
   interfaces that SKU offers.
4. `catalog.toml` rows.
5. `python doqs/scripts/validate_all.py`.

### Use a family in a machine

See *Using a family in a machine* above.

---

## Anti-patterns

**Do not use FreeCAD `Visibility` or `Suppressed` as the product configurator.**
Spreadsheet-driven *dimensions* are first-class and are what the model system is
for. Spreadsheet-driven *presence of a motor* is not:

- `Suppressed` can only be bound to a spreadsheet through a hidden expression
  ([forum t=93265](https://forum.freecad.org/viewtopic.php?t=93265)).
- Suppressing geometry that fillets, binders or joints depend on breaks the
  model ([forum t=105096](https://forum.freecad.org/viewtopic.php?t=105096)).
- `Visibility` is a view property, not "omit from BOM, STEP and CAM".
- BOMs, `[[part]]` rows, SysML ports and manufacturing files are text. A hidden
  flag inside an LFS `.FCStd` is invisible to `git diff`, to validators and to
  agents.
- A stepper SKU and a servo SKU **provide different interfaces**. That belongs
  in `[[provides-interface]]` on the composition, not in a boolean named
  `has_linear_encoder`.

*Allowed exception:* optional features on a single manufactured part — an extra
hole pattern the stepper carriage can keep. If the part is genuinely different,
it belongs in the option module.

**Do not create one repository per SKU**, and do not make the core a submodule
of each composition. A shared fix must reach every SKU with one commit.

**Do not put dimensions in module folder names.** `linear-stage-servo-linear`,
never `linear-stage-500mm`. See [naming.md](naming.md).

---

## Not implemented: a declarative option space

With two option axes and a curated composition list, hand-written compositions
are the cheaper mechanism, and DOQS deliberately stops here. The migration path,
should it ever be needed:

```toml
# variants.toml — NOT IMPLEMENTED. No schema, no generator, no validator.
[[option]]
axis   = "drive"
values = ["stepper", "servo"]

[[option]]
axis   = "feedback"
values = ["none", "rotary", "linear"]

[[rule]]
when     = { feedback = "linear" }
requires = { drive = "servo" }

[[rule]]
when      = { drive = "stepper" }
conflicts = { model = ["1200mm"] }        # resonance
```

**Build it when** the curated composition list would exceed about six, or when a
third option axis appears. Below that a configurator language costs more than
the compositions it would replace. Until then, the composition list *is* the
statement of which combinations are supported.

---

## Tooling reference

| Script | Job |
|---|---|
| `resolve_params.py` | Sparse overrides + expressions → `cad/params.csv` and `cad/params-table.csv` |
| `resolve_bom.py` | Overlays, `{alias}` templates, length tables, vendor geometry, for one module |
| `resolve_instance.py` | A consumer's `[instance]` → resolved params, BOM and vendor CAD. `--check` for CI |
| `validate_variants.py` | Catalogue, models, compositions, length-table coverage, vendor files, instance freshness |
| `aggregate_bom.py` | Machine-root purchasing list that understands families and instances |
| `export_variant.py` | Geometry for one composition × model, on demand |

Schemas: [`catalog.schema.json`](../schemas/catalog.schema.json),
[`instance.schema.json`](../schemas/instance.schema.json),
[`sources.schema.json`](../schemas/sources.schema.json),
[`build.schema.json`](../schemas/build.schema.json).

Templates: [`templates/variants/`](../templates/variants/).
The sync script is a doqs tool: [`scripts/cad_sync_params.py`](../scripts/cad_sync_params.py).

Worked examples: `tests/fixtures/variant-family/` (the family) and
`tests/fixtures/variant-machine/` (a machine consuming it at two lengths).
