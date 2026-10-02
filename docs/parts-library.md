# Parts library

One home for the parts we buy, so nobody researches the same rail twice.

Read [architecture.md](architecture.md) first for the module layout this builds
on, and [roles.md](roles.md) for how a machine uses a part once it is here. The
decision behind this page is
[ADR-004: a shared library for parts we buy](decisions/2026-09-18_parts-library.md).

---

## What it is

`stoq` is an ordinary DOQS repository holding parts other people make. A machine
mounts it like any other external module:

```bash
git submodule add https://github.com/refaqt/stoq modules/stoq
```

It is recognised by a marker file at its root, not by where it is mounted:

```toml
# library.toml
schema = "doqs-library-v1"
name   = "stoq"
```

That marker does three things:

1. A manifest inside it must declare `CC-BY-SA-4.0`, not `CERN-OHL-S-2.0`. The
   library holds no hardware we designed.
2. `apply_licenses.py` writes the library licence layout instead of the machine
   one.
3. A consuming machine's checks skip the whole checkout. The library is
   validated in its own repository, and a machine should not re-run hundreds of
   supplier checks on every commit.

---

## Brand, family, part

Three levels, and only two of them are folders.

| Level | Where | What it is |
| --- | --- | --- |
| **Brand** | `modules/hiwin/` | The name on the part. Stable for decades. |
| **Family** | `modules/hiwin/modules/hgr-rail/` | One product range. **This is the module.** |
| **Part** | a row in `bom/parts.csv` | One orderable part number. Not a folder. |

A machine buys hundreds of part numbers. A folder each does not scale, and it is
not needed — [variants.md](variants.md) already made a range the unit, with each
orderable item a row.

**Brand is not supplier.** HIWIN is the brand: on the part, in the part number,
unchanging. RS or Misumi is the supplier: where you buy it, often several at
once, and changing. The bill of materials holds no distributors at all
([ADR-006](decisions/2026-09-18_money-out-of-the-bom.md)), so nothing competes
for the word.

For standards the brand is the standards body: `modules/din/modules/din-912/`.

---

## Layout

```
modules/stoq/modules/hiwin/modules/hgr-rail/
├── okh.toml            what this family is, [brand], [[provides-interface]]
├── bom/parts.csv       ONE row per orderable part number
├── vendor-index.csv    provenance: address, checksum, date, for every file
├── cad/
│   ├── parts/HGR20R500.FCStd     the document a role links
│   ├── original/HGR20R500.step   the untouched download
│   └── own/HGR20R800.FCStd       a model we drew from the datasheet, with
│       own/HGR20R800.build.py    the script that builds it, and
│       own/HGR20R800.*.csv       the record of how we drew it
└── docs/datasheets/              catalogues and datasheets
```

**One manifest, one table, the files.** A library family has no bill of
materials, because it is not made of anything we know — it *is* the thing you
buy. So `bom/parts.csv` replaces `catalog.toml`, `bom/bom.csv`,
`bom/sources.toml` and `bom/tables/<part>.csv`, which in a library would all hold
one row per part number and say the same thing four times.

Note there is no `cad/vendor/`. That folder exists only to carve one directory
out of the hardware licence, because the rest of `cad/` is ours and that
directory is not. Inside a library nothing is ours, so the carve-out moves up to
the repository and the folders go back to normal. `cad/vendor/` stays supported
in a **machine** repository, for a one-off bought part not yet in a library.

### The brand manifest

```toml
# modules/hiwin/okh.toml
[brand]
name         = "HIWIN Technologies Corp."
website      = "https://www.hiwin.tw"
cad-terms    = "https://www.hiwin.tw/terms-of-use"
redistribute = false        # default for files from this brand
```

`cad-terms` is the address of the terms you read before deciding what may be
committed. Recording it means the decision can be checked later instead of
re-argued.

### The part table

```csv
# modules/hiwin/modules/hgr-rail/bom/parts.csv
pn,description,spec,unit_mass_g,cad,datasheet,terms,revision,status,notes
HGR20R300,HGR20 rail 300 mm,rail width 20 mm; hole pitch 60 mm,1290,cad/parts/HGR20R300.FCStd,docs/datasheets/hgr-series.pdf,redistributable,A,active,
HGR20R500,HGR20 rail 500 mm,rail width 20 mm; hole pitch 60 mm,2150,cad/parts/HGR20R500.FCStd,docs/datasheets/hgr-series.pdf,redistributable,A,active,
HGR20R800,HGR20 rail 800 mm,rail width 20 mm; hole pitch 60 mm,3440,,docs/datasheets/hgr-series.pdf,fetch-only,A,active,
```

| Column | Meaning |
| --- | --- |
| `pn` | The brand's own part number, verbatim. You order by this. |
| `description` | What it is, in words |
| `spec` | The technical figures that matter for selection |
| `unit_mass_g` | Mass. A physical property, so it belongs here. |
| `cad` | The FreeCAD document a role links. Empty until someone needs it. |
| `datasheet` | Where the paper lives, or where to fetch it |
| `terms` | `redistributable`, `fetch-only`, `private` or `own-model`; `internal` in a [private library](#a-private-library) only. See [Taking in a supplier's files](#taking-in-a-suppliers-files). |
| `revision` | The brand's revision of this part. Never reused. |
| `status` | `active` or `eol` |
| `notes` | Free text. On a discontinued row, name the replacement part number. |

Lines starting with `#` are comments and are skipped, so the template can be
copied as it is.

**No price and no distributor.** The library is technical. What a part costs is
answered by a different system; see
[ADR-006](decisions/2026-09-18_money-out-of-the-bom.md).

**You do not have to store every file.** The table is complete — every size,
every part number. The geometry is a cache that fills as people use parts. A row
whose file is missing is normal, and validation warns instead of failing.

Where a family is genuinely parametric — a DIN 912 screw range — add
`cad/params/` and declare `[[model]]` exactly as our own families do, instead of
downloading hundreds of files.

---

## Nothing is ever removed

This is the rule that makes one pin enough, and it is worth understanding before
you add anything.

A submodule has one commit per path, so one mount is one version of the whole
library. That looks like a problem: what if this machine uses a rail specified
in 2026 and a motor specified in 2028?

It is not a problem, because **the library never removes anything**:

- A part row is never edited in place when the part itself changed. A revised
  design is a new row with a new revision and, almost always, a new part number.
- A part you can no longer buy gets `status = "eol"`. That stops new designs
  choosing it. It never deletes what an existing machine is made of.

So the 2028 commit still contains the 2026 rail. One pin gives you both.

Two consequences follow. The library's history is never rewritten — no squash,
no force-push, or every build record that points into it breaks. And checksums
are checked, not just recorded: a download that silently changed under the same
part number is caught rather than trusted.

---

## Copyright: store the link, not the file

Commit text by default. Specifications, part numbers, dimensions, addresses and
checksums are facts we compile, and they are the bulk of the value.

- **`terms = "fetch-only"`** — the default. The address, the checksum and the
  retrieval date are committed. The file is not. Each person downloads under the
  brand's own terms. This needs no legal opinion and works in a public
  repository.
- **`terms = "redistributable"`** — only where that brand's terms or a written
  permission allow it, with a `public` decision recorded on the brand.
- **`terms = "private"`** — like `fetch-only`, but there is no public address.
  The file came with a quotation or an email, so the only copy is in the
  [private library](#a-private-library), where its row says `internal`.
- **`terms = "own-model"`** — a model we drew ourselves from the datasheet. It
  is ours, so it is always committed, under our licence.
- **`terms = "internal"`** — only in a [private library](#a-private-library).
  The file is committed there and may not be passed on to anyone.

Two things to check with a lawyer before committing any brand's files: the
download terms of your main suppliers, and whether the EU database right affects
copying a large part of a catalogue. This page is not legal advice.

---

## Licence layout

| Content | Licence |
| --- | --- |
| `bom/`, `docs/` outside `datasheets/`, the manifests | CC BY-SA 4.0 — our compiled work |
| `cad/`, `docs/datasheets/` | the brand's own terms — their work, and work derived from it |
| `cad/own/` | CC BY-SA 4.0 — models we drew ourselves from the datasheet |

One split at one level, instead of a carve-out per module. A FreeCAD document
built from a supplier STEP is derived from their file, so it sits on their side
of the line. A model we draw from the published dimensions is not: dimensions
are facts, and the model is ours. That is why it has its own folder. A
[private library](#a-private-library) has no split: nothing in it is under a
licence of ours.

---

## A private library

Some files cannot go in `stoq` at all: supplier CAD models, datasheets under a
confidentiality agreement, catalogues whose terms forbid redistribution. A
**private library** stores them for internal use. It is a second repository
with the same layout, and one line in its marker:

```toml
# library.toml
schema  = "doqs-library-v1"
name    = "stoq-private"
private = true
```

That line changes four things. The decision is
[ADR-008](decisions/2026-09-29_private-parts-library.md).

| In a private library | Instead of |
| --- | --- |
| The root `LICENSE` says: internal use only, each file keeps its supplier's licence | CC BY-SA 4.0 for the record, with a carve-out |
| `okh.toml` `license` names the supplier's licence: an SPDX id or `LicenseRef-<name>` | `CC-BY-SA-4.0` |
| Rows may use `terms = "internal"`: committed, never passed on | Only `redistributable` or `fetch-only` |
| No `LICENSES/` and no directory stubs: `apply_licenses.py` never writes inside `modules/` | Stubs in every `cad/` and `docs/datasheets/` |

**Record each file's licence** from the most specific to the least. The most
specific one wins.

1. `<file>.license` next to one file, when that file has its own terms.
2. `LICENSE` in a brand or family folder, copied from the supplier.
3. The `license` field of the brand's or family's `okh.toml`, with the address
   of the terms in `[brand] cad-terms`.

**Keep it private.** Share nothing from it outside the organisation — not with
the public and not with contractors. A public machine cannot mount it, because
the people who rebuild the machine could not fetch it. Refer to a part by its
reference and part number instead.

`internal` is refused anywhere outside a private library, so a file marked that
way fails the checks of `stoq` or a machine rather than being published.

---

## Taking in a supplier's files

The full method, step by step, lives in the library itself
(`docs/adding-components.md` in `stoq`). The checks enforce this much of it.

### One decision per kind of file

A brand's files come in two kinds: `cad` (geometry) and `documentation`
(datasheets, manuals, drawings). They often come under different terms, so each
kind gets its own dated decision in the brand's `okh.toml`:

```toml
[[terms-review]]
kind     = "cad"             # cad | documentation
decision = "public"          # public | customers | internal
basis    = "terms"           # terms | permission | none
source   = "https://www.hiwin.de/en/agb"
evidence = "evidence/hiwin/2026-09-21_agb.pdf"   # a path in the private library
reviewer = "First Last"      # the named person who approved it
reviewed = 2026-09-21
```

- `public`: we may publish the files. Only then may a row say `redistributable`.
- `customers`: we may give copies to our customers, not to the public. The
  files stay out of git and go to customers through the private library.
- `internal`: we keep a copy for ourselves only.

An agent may propose an entry. A named person approves it, in the pull request.
Entries are never edited or deleted: when the terms change, add a new one. The
newest entry for a kind is the one that counts.

What the checks do:

| Situation | Result |
| --- | --- |
| A `redistributable` file, and no review for its kind | error |
| A `redistributable` file, and the newest review is not `public` | error |
| A review without a reviewer or a date | error |
| `basis = "permission"` without `evidence` | error |
| `decision = "public"` with `basis = "none"` | warning |
| `redistribute` on `[brand]` disagrees with the newest `cad` review | error |

### Files we may not share never enter git

History is never rewritten, so a file that was committed once can never be
taken back. The check fails when git tracks a file whose row says `fetch-only`
or `private`. List those paths in `.gitignore`.

The copy we keep lives in the [private library](#a-private-library), at the
same path, where its row says `internal`. `doqs restore-private --from
../stoq-private` copies those files from a checkout of the private library into
place, after checking each checksum. It is never a submodule of a public
repository, because a public clone could not fetch it.

**When terms change.** A file that git already tracks can become `fetch-only` or
`private`: the brand changes its terms, or the file turns out to have come with a
quotation. Take it out of git with one command:

```bash
bash doqs.sh unshare --from ../stoq-private modules/hiwin/modules/hgr-rail/cad/original/HGR20R500.step
```

It first checks that the private library holds the same file, with the same
checksum. If any path fails, it changes nothing. Then it runs `git rm --cached`
and adds the exact paths to `.gitignore`. The file stays on your disk, and the
command prints how to delete it and how to get it back. Set the row's `terms` to
`fetch-only` or `private` in the same commit. The file is still in earlier
commits: history is never rewritten.

A `customers` decision is the one case where a file from the private library
may leave the organisation: to our own customers, for the machines they bought,
handed over by a named person. Everything else in the private library stays
inside.

### Our own models

A row with `terms = "own-model"` points at `cad/own/<pn>.FCStd`. The model is
ours, and it must be able to replace the brand's model in an assembly. So it is
checked like a part of a machine, not like a supplier file. The decision is
[ADR-011](decisions/2026-10-02_own-models-are-our-designs.md).

Several own models share one `cad/own/` folder. Each has six files, all named
after its part number. Templates are in
[`templates/parts-library/cad/own/`](../templates/parts-library/cad/own/).

| File | What it holds |
| --- | --- |
| `<pn>.features.csv` | Every feature of the part, filled in **before** you model |
| `<pn>.params.csv` | Every value the build uses, and where it came from |
| `<pn>.build.py` | The script that builds the model, and its axes |
| `<pn>.FCStd` and `<pn>.fingerprint.json` | The model, and what it measures |
| `<pn>.checks.csv` | Whether it matches the brand's model |

#### 1. List every feature first

Before you draw anything, fill `<pn>.features.csv`. Give one row to every
labelled dimension in the catalogue table, and one to every feature the figure
shows, with or without a size. Look for the features without a size: reference
edges, end caps, end seals, grease nipples, plugs, screw heads, ports,
connectors and cables.

```csv
feature,kind,outside_envelope,source,page,status,reason
grease nipple,drawn-unsized,yes,docs/datasheets/hg-series.pdf,70,estimated,
```

| Column | Values |
| --- | --- |
| `kind` | `sized` (the table gives its size), `drawn-unsized` (the figure shows it with no size), `not-drawn` (only the text names it) |
| `outside_envelope` | `yes` when it sticks out of the main shape |
| `status` | `modelled`, `estimated`, `measured` or `left-out` |
| `reason` | Why it is left out. Required for `left-out` |

A feature that sticks out of the main shape may **never** be left out. An
assembly would not see the collision. The checks fail on an empty row, on
`left-out` without a reason, and on a feature with `outside_envelope = yes` that
is left out.

#### 2. Say where every value comes from

`<pn>.params.csv` and `<pn>.checks.csv` mark each value in the `basis` column:

| `basis` | Meaning | Required |
| --- | --- | --- |
| `catalogue` | A size printed in the brand's table or drawing | `source` and `page` |
| `estimated` | Read off a figure | `source` and `page`. The check warns: it is a placeholder |
| `measured` | Measured on a real part | `measured_by` (a named person) and `measured_utc` (the date) |

Four rules for values you did not find in a table:

- **A catalogue figure is often drawn for one size and used for all sizes.**
  Before you read a size off a figure, work out the drawing scale from several
  sized dimensions in the same view. If they give different scales, the figure
  is not to scale for this size, and an estimate from it is only a placeholder.
- **An estimate for a feature that sticks out errs on the large side.** A
  collision check then stays safe.
- **Replace an estimate with a measurement of a real part or a value from the
  brand.** Never with a value from the brand's CAD file.
- **A part number option is a parameter until the brand confirms it.** For
  example a lubrication unit on one end: build the plain part, and keep the
  option as a parameter, until the brand says which option this part number has.

#### 3. Build it with a script, on the brand's axes

`<pn>.build.py` reads `<pn>.params.csv` and nothing else. Never build or change
an own model by hand in the GUI, and never save it again after a build. Run:

```bash
FreeCADCmd modules/<brand>/modules/<family>/cad/own/<pn>.build.py
```

The model uses the **same axes and origin as the brand's model**, so it can take
its place in an assembly. The script says which in one line:

```python
AXES = "X along the rail from its start, Z up from the mounting face; origin at the centre of the bottom face"
```

`doqs check` fails an own model without a build script, without `AXES`, without
`<pn>.params.csv`, without a fingerprint from a saved build, or with a
fingerprint that no longer matches the file. That last one catches a model saved
again after its build. It also fails a Body that is not inside a Part
container, and a `.FCBak` backup or a `__pycache__/` folder that git tracks.

#### 4. Compare it with the brand's model

`<pn>.checks.csv` lists every dimension, where it came from, how it is measured,
and whether the brand's model agrees:

```csv
dimension,value_mm,basis,source,page,measured_by,measured_utc,method,result,checked_utc
envelope X (block length L),61.4,catalogue,docs/datasheets/hg-series.pdf,70,,,"Extent along X of the bounding box of all solids, measured the same way on both models in a headless FreeCAD run by doqs compare-own",pass,2026-10-02T00:00:00Z
```

The list must hold:

- `envelope X`, `envelope Y` and `envelope Z`: the overall size along each axis,
  **as the catalogue defines it**. A block length that the catalogue gives with
  its end seals is checked with its end seals.
- `symmetry YZ`, `symmetry XZ` or `symmetry XY` for each mirror plane through
  the origin, or `symmetry none`. Its `value_mm` is `-`.

`method` says in words how the dimension was measured on both models, so someone
else can repeat it. It never holds a value. A `pass` without a method fails.

Run the comparison from the library root:

```bash
bash doqs.sh compare-own hiwin/hgr-rail HGR20R1000 --from ../stoq-private
```

It needs FreeCAD and a checkout of the private library, which holds the brand's
STEP file. It copies both models into a temporary folder outside both
repositories and measures them there, in a separate FreeCAD run. That run turns
every measurement into words before anything leaves it. So the command never
prints, logs or saves a brand value. It writes only `pass`, `fail` or
`not-confirmed` and the method into the envelope and symmetry rows. It also
says:

- whether both models use the same axes and origin,
- the mirror planes of each model,
- every brand feature that sticks out of our model and has no counterpart in
  ours, and on which side.

An envelope that is smaller than the brand's is a `fail`: something is missing.
One that is larger is `not-confirmed`: an estimate on the large side is safe, but
it is still an estimate. The command never saves either model. It checks our
model against its fingerprint and the brand's file against its recorded checksum
before it starts and again afterwards, and writes nothing if anything changed.

A `fail` is an error: read the drawing again and fix the value from the drawing.
Our models carry no logos and no brand text.

---

## Keeping the checkout small

Storing links rather than files keeps `stoq` small, so neither of these is
urgent. Both exist when it stops being true.

**Fetch less of a big repository.** `git clone --filter=blob:none
--also-filter-submodules` fetches file contents only when a file is checked out,
and `git sparse-checkout set` inside the submodule limits which folders appear
at all. Git does not store this in `.gitmodules`, so it belongs in
`setup-tooling.sh`.

**Split the repository.** When one brand grows big enough,
`git subtree split --prefix=modules/hiwin` moves it out with its history and it
returns as a submodule at the same path — the move
[architecture.md](architecture.md) already documents. The path does not change,
so nothing in a consuming machine breaks.

**What you cannot do:** check out one folder of a repository as a submodule. A
submodule is always a whole repository, and `.gitmodules` has no field for a
subdirectory. The size of the repository you choose is the size you get.

---

## Recipes

### Add a part to an existing family

1. A row in `bom/parts.csv`. Part number, description, the figures that matter,
   mass, terms, revision, `status = "active"`.
2. If someone needs the geometry now: download the STEP to `cad/original/<pn>.step`,
   build `cad/parts/<pn>.FCStd` from it, and fill the `cad` column. If not, leave
   it empty. If the brand's `cad` review is not `public`, keep the file out of
   git, or draw your own model under `cad/own/` instead.
3. A row in `vendor-index.csv` with the address, the checksum and the date.
4. `python doqs/doqs.py check`.

### Add a family

1. `modules/<brand>/modules/<family>/okh.toml` with `[brand]` and, where the
   family has a mechanical interface, `[[provides-interface]]`.
2. `bom/parts.csv` with the parts you know about.
3. `python doqs/doqs.py check`.

### Add a brand

1. `modules/<brand>/okh.toml` with `[brand]`, including `cad-terms`.
2. Read those terms. Save a dated copy in the private library. Write one
   `[[terms-review]]` for `cad` and one for `documentation`, and set
   `redistribute` to match the `cad` one. A named person approves them.
3. Then add a family.

### Retire a part

Set `status = "eol"`. Do not delete the row and do not delete the file. Add the
replacement part number to `notes` if there is one, so a role that selects the
old part gets a useful warning.

---

## Related

- [Role modules](roles.md) — how a machine uses a part from here
- [A private parts library](decisions/2026-09-29_private-parts-library.md) — files that may not be passed on
- [Money leaves the bill of materials](decisions/2026-09-18_money-out-of-the-bom.md) — why there are no prices here
- [Architecture](architecture.md) — folder layout and licensing
- [Variants](variants.md) — our own product families, which work differently
