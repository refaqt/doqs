# ADR-008 — A private parts library

- **Date:** 2026-09-29
- **Status:** Accepted
- **Amends:** [ADR-004 a shared library for parts we buy](2026-09-18_parts-library.md), sections 6 and 7

## Context

ADR-004 made `stoq` public. Files whose terms forbid redistribution stay out of
it: only the address, the checksum and the date are committed (`fetch-only`).
ADR-004 also rejected a private library, because it said a private repository
does not create permission to share with contractors.

That leaves a gap. Many of the files we use most — supplier CAD models,
datasheets under NDA, catalogues with restrictive terms — cannot be in `stoq`.
Each person then downloads and stores them on their own computer. Nobody can
see which version a design was built from, and the checksums in `stoq` are the
only shared record.

Refaqt needs one internal place for those files. It is not a way to share them
with anyone outside Refaqt, and not with contractors.

## Decision

A parts library may declare itself private in its marker:

```toml
# library.toml
schema  = "doqs-library-v1"
name    = "stoq-private"
private = true
```

In a private library:

1. **No open licence of ours.** `apply_licenses.py` writes a root `LICENSE`
   that says the library is for internal use only, and that each file keeps its
   supplier's licence. There is no CC BY-SA, no `LICENSES/` folder, and no
   directory stubs.
2. **Each file keeps its supplier's licence**, recorded from the most specific
   to the least: a `<file>.license` next to one file, a `LICENSE` copied from
   the supplier into a brand or family folder, then the `license` field of the
   brand's or family's `okh.toml`. That field takes any licence — an SPDX id, or
   `LicenseRef-<name>` for the supplier's own terms — instead of `CC-BY-SA-4.0`.
3. **A third value for `terms`:** `internal`. The file is committed and must be
   present, and it may not be passed on to anyone. `validate_variants.py`
   refuses `internal` anywhere outside a private library, so such a file cannot
   end up in `stoq` or in a machine by mistake.
4. **The generator never writes inside `modules/`.** A `LICENSE` there is the
   supplier's own text. Writing a stub over it would replace their terms with
   ours.

Everything else is the same as ADR-004: the brand, family and part layout, the
append-only rule, checksums in `vendor-index.csv`, and no prices.

## Consequences

- Supplier files have one internal home, with provenance and checksums.
- A public library cannot hold an `internal` row. A leak through `stoq` fails
  its checks.
- A private library cannot be mounted by a public machine: people who rebuild
  the machine could not fetch it. A machine that needs a part from it records
  the reference and the part number, as for any fetch-only file.
- Whether a supplier's terms allow a copy in an internal repository is a
  question about that supplier. Read the terms, and record their address in
  `cad-terms`, before committing the first file of a brand.
- Moving a library from public to private leaves the old CC BY-SA files in
  place. Delete `LICENSES/` and the old directory stubs by hand.

## Alternatives rejected

| Alternative | Why not |
| --- | --- |
| Skip the licence gates in the private repository | `doqs generate` would still write a CC BY-SA licence over files that are not ours to license. |
| A separate schema, `doqs-private-library-v1` | Everything except the licence is the same as a public library. One flag is enough. |
| A licence column in `bom/parts.csv` | Changes the header of every existing library. A `.license` file or a folder `LICENSE` holds the supplier's full text, which a column cannot. |
