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
├── cad/
│   ├── parts/HGR20R500.FCStd     the document a role links
│   └── original/HGR20R500.step   the untouched download
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
pn,description,spec,unit_mass_g,cad,datasheet,terms,revision,status
HGR20R300,HGR20 rail 300 mm,rail width 20 mm; hole pitch 60 mm,1290,cad/parts/HGR20R300.FCStd,docs/datasheets/hgr-series.pdf,redistributable,A,active
HGR20R500,HGR20 rail 500 mm,rail width 20 mm; hole pitch 60 mm,2150,cad/parts/HGR20R500.FCStd,docs/datasheets/hgr-series.pdf,redistributable,A,active
HGR20R800,HGR20 rail 800 mm,rail width 20 mm; hole pitch 60 mm,3440,,docs/datasheets/hgr-series.pdf,fetch-only,A,active
```

| Column | Meaning |
| --- | --- |
| `pn` | The brand's own part number, verbatim. You order by this. |
| `description` | What it is, in words |
| `spec` | The technical figures that matter for selection |
| `unit_mass_g` | Mass. A physical property, so it belongs here. |
| `cad` | The FreeCAD document a role links. Empty until someone needs it. |
| `datasheet` | Where the paper lives, or where to fetch it |
| `terms` | `redistributable` or `fetch-only` |
| `revision` | The brand's revision of this part. Never reused. |
| `status` | `active` or `eol` |

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
- **`terms = "redistributable"`** — only where that brand's terms allow it, with
  `cad-terms` on the brand recording what you read.

A private repository is a second tier, worth adding only for brands whose terms
allow sharing with contractors but not the public. It is **not** a way around
terms that forbid redistribution: giving a copy to a contractor is still making
a copy, and a confidentiality agreement limits what they may then do rather than
creating permission. It also closes an open-hardware machine to the people meant
to be able to rebuild it.

Two things to check with a lawyer before committing any brand's files: the
download terms of your main suppliers, and whether the EU database right affects
copying a large part of a catalogue. This page is not legal advice.

---

## Licence layout

| Content | Licence |
| --- | --- |
| `bom/`, `docs/` outside `datasheets/`, the manifests | CC BY-SA 4.0 — our compiled work |
| `cad/`, `docs/datasheets/` | the brand's own terms — their work, and work derived from it |

One split at one level, instead of a carve-out per module. A FreeCAD document
built from a supplier STEP is derived from their file, so it sits on their side
of the line.

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
   it empty.
3. A row in `vendor-index.csv` with the address, the checksum and the date.
4. `python doqs/doqs.py check`.

### Add a family

1. `modules/<brand>/modules/<family>/okh.toml` with `[brand]` and, where the
   family has a mechanical interface, `[[provides-interface]]`.
2. `bom/parts.csv` with the parts you know about.
3. `python doqs/doqs.py check`.

### Add a brand

1. `modules/<brand>/okh.toml` with `[brand]`, including `cad-terms`.
2. Read those terms and set `redistribute`.
3. Then add a family.

### Retire a part

Set `status = "eol"`. Do not delete the row and do not delete the file. Add the
replacement part number to `notes` if there is one, so a role that selects the
old part gets a useful warning.

---

## Related

- [Role modules](roles.md) — how a machine uses a part from here
- [Money leaves the bill of materials](decisions/2026-09-18_money-out-of-the-bom.md) — why there are no prices here
- [Architecture](architecture.md) — folder layout and licensing
- [Variants](variants.md) — our own product families, which work differently
