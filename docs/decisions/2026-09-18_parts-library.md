# ADR-004 — A shared library for parts we buy

- **Date:** 2026-09-18
- **Status:** Proposed
- **Extends:** [ADR-003 product families](2026-09-15_product-family-variants.md)
- **Works with:** [ADR-005 role modules](2026-09-18_role-modules.md),
  [ADR-006 money leaves the bill of materials](2026-09-18_money-out-of-the-bom.md)

## Context

ADR-003 gave purchased parts two homes inside the module that buys them:
`cad/vendor/` for the geometry and `bom/tables/<part>.csv` for the part number.
Both live in the machine repository, so every project that buys the same rail
repeats the same work: find the part, download the file, record where it came
from, write the table row.

That is the wrong place for it. A HIWIN rail belongs to no single machine. The
work of recording it should be done once and read by every project.

Three questions had to be answered before a shared home could exist.

**Where does it mount?** A separate root folder was considered and rejected.
`modules/` is already where an external repository enters a DOQS project. A
parts library is one more external DOQS project, so a second class of thing
would have been invented for nothing.

**How is it versioned?** A submodule has one commit per path, so one mount is
one version of everything in it. That seemed to block "this machine uses a rail
we specified in 2026 and a motor we specified in 2028".

**What may we redistribute?** Supplier geometry and datasheets belong to the
supplier. Committing them into a public repository is distribution, and most
download terms forbid it.

## Decision

### 1. One repository, `stoq`, mounted under `modules/`

A machine adds it like any other external module:
`git submodule add https://github.com/refaqt/stoq modules/stoq`.

It is recognised by a marker file at its root, not by its path:

```toml
# library.toml
schema = "doqs-library-v1"
name   = "stoq"
```

`library.toml` does three things. A manifest inside it requires
`CC-BY-SA-4.0` rather than `CERN-OHL-S-2.0`, because the library holds no
hardware we designed. The licence layout uses the library profile below. And a
consuming machine's gates skip the whole checkout, because it is validated in
its own repository and a machine should not re-run hundreds of supplier checks
on every commit.

One repository, not one per brand. When a brand grows big enough to deserve its
own, `git subtree split --prefix=modules/hiwin` moves it out with its history
and it returns as a submodule at the same path — the move `architecture.md`
already documents for machine modules. Because the path does not change, nothing
in a consuming machine breaks.

### 2. Brand, not supplier

The folder level is the **brand**: the name on the part, part of the part
number, stable for decades. HIWIN, Beckhoff, DIN. It is not the **supplier**,
which is where you buy the part — often several at once, and changing.

```toml
# modules/hiwin/okh.toml
[brand]
name         = "HIWIN Technologies Corp."
website      = "https://www.hiwin.tw"
cad-terms    = "https://www.hiwin.tw/terms-of-use"
redistribute = false        # default for files from this brand
```

For standards the brand is the standards body: `modules/din/modules/din-912/`.

### 3. The family is the module. A part number is a row.

A machine buys hundreds of part numbers. A folder each does not scale, and it is
not needed: ADR-003 already made a *range* the unit, with each orderable item a
row. That mechanism carries over unchanged.

Where a difference is architectural rather than a number — an HGR20 rail and an
HGR25 rail have different bolt patterns — it is a separate family, by the same
rule that governs compositions today.

### 4. Inside a library, the folders are ordinary

`cad/vendor/` exists only to carve one directory out of the hardware licence,
because the rest of `cad/` is ours and that directory is not. **Inside a library
nothing is ours**, so the carve-out moves up to the repository and the folders
go back to normal:

```
modules/stoq/modules/hiwin/modules/hgr-rail/
├── okh.toml            what this family is, [brand], [[provides-interface]]
├── bom/parts.csv       ONE row per orderable part number
├── cad/
│   ├── parts/HGR20R500.FCStd     the document a role links
│   └── original/HGR20R500.step   the untouched download
└── docs/datasheets/
```

`bom/parts.csv` replaces `catalog.toml`, `bom/bom.csv`, `bom/sources.toml` and
`bom/tables/<part>.csv` at once. In a library all four would hold one row per
part number and say the same thing four times. A library family has no bill of
materials, because it is not made of anything we know — it *is* the thing you
buy.

`cad/vendor/` stays supported in a machine repository, for a one-off bought part
that is not in a library yet.

### 5. Nothing is ever removed

This is what answers the versioning question, and it is a rule rather than a
mechanism.

**A part row is never edited in place when the part itself changed.** A revised
design is a new row with a new revision and, almost always, a new part number.
The old row and the old file stay. A discontinued part gets `status = "eol"`,
which stops new designs choosing it and never deletes what an existing machine
is made of.

So the 2028 commit of `stoq` still contains the 2026 rail. One pin gives you
both parts at once, and the question that seemed to need two checkouts does not
arise.

Checksums make the rule enforceable. `vendor-index.csv` already records a
`sha256` per file and nothing compares it; validation will, so a download that
silently changed under the same part number is caught rather than trusted.

### 6. Store the link, not the file

The library commits text by default: specifications, part numbers, dimensions,
addresses and checksums. A binary is committed only where that brand's terms
allow it, marked `terms = "redistributable"`. Everything else is
`terms = "fetch-only"`: the address, the checksum and the retrieval date are
committed, and each person downloads under the brand's own terms.

This needs no legal opinion, works in a public repository, and keeps the
repository small enough that one shared library is practical.

Facts we compile ourselves — dimensions, part numbers, masses — are not a copy
of anyone's catalogue, and ADR-006 removes prices, which is the data a supplier
is most likely to claim. A private repository is a second tier, worth adding
only for brands whose terms allow sharing with contractors but not the public.
It is not a way around terms that forbid redistribution: giving a copy to a
contractor is still making a copy.

### 7. Licence layout

| Content | Licence |
| --- | --- |
| `bom/`, `docs/` outside `datasheets/`, the manifests | CC BY-SA 4.0 — our compiled work |
| `cad/`, `docs/datasheets/` | the brand's own terms — their work, and work derived from it |

One split at one level, instead of a carve-out per module. `apply_licenses.py`
gains this as a third profile beside the machine and tools profiles.

## Consequences

- A machine mounts one submodule and writes no supplier files of its own.
- A brand's terms are recorded once, where the decision can be checked later,
  instead of being re-judged in every project.
- The library is technical only. What a part costs is answered elsewhere; see
  ADR-006.
- A library family carries four kinds of thing instead of eight. The template
  shrinks to match.
- `cad/vendor/` keeps working in machine repositories, so nothing existing
  breaks.
- The library grows a long history that is never rewritten. That is the point,
  and it means a squash or a force-push on `stoq` would break build records. The
  repository needs branch protection from the first commit.
- A machine that mounts the library must skip it in its own gates. That is one
  marker and one check in `scripts/naming_rules.py`, imported by every walker —
  the rule from `docs/mistakes/2026-09-16_validators-walked-agent-kit.md`.

## Alternatives rejected

| Alternative | Why not |
| --- | --- |
| A separate root folder, `parts/` | `modules/` is already where external repositories enter. A second class of thing for no gain. |
| One repository per brand, from the start | More repositories and more submodules before anything proves it is needed. The split path stays open and costs nothing to delay. |
| One repository per product family | Dozens of repositories within a year, for the same reason ADR-003 refused one per SKU. |
| A folder of another repository as a submodule | Git cannot do it. A submodule is always a whole repository and `.gitmodules` has no field for a subdirectory. |
| Two checkouts of the library at different commits | Only needed if the library deletes things. It does not, so this solves a problem the append-only rule removes. |
| Commit every supplier file | Most download terms forbid it, and the repository would grow past what one shared mount can carry. |
| A private library from the start | Closes an open-hardware machine to the people meant to rebuild it, and does not create permission the terms do not give. |
