# ADR-008 — A fixed method for taking in a supplier's files

- **Date:** 2026-09-29
- **Status:** Accepted
- **Extends:** [ADR-004 a shared library for parts we buy](2026-09-18_parts-library.md)

## Context

A parts library had two sharing levels for a supplier's file: we may publish it
(`redistributable`), or we store only its address (`fetch-only`). The decision
was one yes or no per brand, written down once by one person.

That left five gaps.

1. **No proof.** Terms pages change. Nobody kept a copy of what was read.
2. **One decision for everything.** A brand may allow its datasheet to be shared
   but not its CAD files.
3. **No middle level.** Some terms allow copies for customers, not for the
   public. Customers need those copies to service and reorder a machine after
   the part is gone from the market.
4. **No home for our own models.** A model we draw from the datasheet is our
   work, but the whole `cad/` folder was marked as the brand's.
5. **No guard against a leak.** History is never rewritten, so a file committed
   by mistake could never be taken back.

## Decision

1. **One dated decision per kind of file.** A `[[terms-review]]` entry in the
   brand's `okh.toml` records the kind (`cad` or `documentation`), the decision
   (`public`, `customers` or `internal`), the basis (`terms`, `permission` or
   `none`), a saved copy of the evidence, the reviewer and the date. Entries are
   never edited; a new one replaces the old one by date.
2. **A named person decides.** An agent may propose a decision. A person
   approves it. The check refuses a review without a reviewer.
3. **A shared file needs a public decision.** A `redistributable` row fails
   unless the newest review for its kind says `public`.
4. **Two new `terms` values.** `private`: not committed, and no public address;
   the only copy is in the private library. `own-model`: a model we drew
   ourselves, under `cad/own/`, carrying CC BY-SA 4.0 like the rest of our
   record.
5. **A check list for every own model.** Each dimension names its datasheet
   page. A separate comparison with the brand's file writes only pass or fail,
   never the brand's value, so no detail moves from their file into ours.
6. **A leak guard.** The check fails if git tracks a `fetch-only` or `private`
   file.
7. **A private library with the same layout.** It holds our copy of every file
   we may not share, and the saved evidence. It is never a submodule of a public
   repository. `doqs restore-private` copies its files into place after checking
   each checksum.

## Consequences

A brand that shares files now needs its reviews before the check passes. The
two brands in `stoq` get theirs in the same change.

A decision can now be checked years later against the copy of the terms that
was read at the time.

The comparison between an own model and the brand's file needs FreeCAD. This
change adds the record and its checks. A script that fills in the results is a
later step.

This is a way of working, not legal advice. The first reviews and the permission
email should be shown to a lawyer who knows EU intellectual property law.
