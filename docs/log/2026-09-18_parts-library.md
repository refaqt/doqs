# 2026-09-18 — One home for the parts we buy

**Role(s):** software

## What happened

Every machine project recorded bought parts on its own. The specification gave a
purchased part two homes inside the module that buys it: one folder for the
geometry, one table for the part number. Both sat in the machine repository, so
two projects buying the same rail did the same work twice and kept two copies of
the same file.

This entry covers the written decisions only. No validator or script changed
yet.

Work done:

- Three decision records. The first gives bought parts one shared repository,
  called `stoq`, mounted like any other external project. The second gives every
  bought part with requirements a stable name of its own, so changing brand does
  not move anything above it. The third takes prices and distributors out of the
  parts list.
- Two guides: one for the shared library, one for naming and filling a job in a
  machine.
- The decisions folder gained the index it was missing. The other two living-doc
  folders had one; this one did not.

## Decisions

**A part number is a row, not a folder.** A machine buys hundreds of part
numbers. The unit that gets a folder is the product range, exactly as it already
is for our own product families.

**Nothing in the library is ever removed.** A revised part is a new row. A part
you can no longer buy is marked as such and stays. This is what lets one pinned
version serve a machine whose parts were chosen years apart, and it replaces a
mechanism we would otherwise have had to build.

**Write a file only when the value belongs to someone else.** An earlier draft
had each job keep a generated copy of what it buys. That copy protects against a
change that cannot happen: the job names an exact part number, so a library
update cannot substitute a different one. The copy went, and checks took its
place. The most useful one compares the design document against the text, which
no generated file could do.

**The parts list answers what is inside, not what it costs.** Seven of sixteen
columns held prices and distributors. A price changes every week and a design
changes rarely, so the two do not belong in one history. A separate system joins
prices to the list using one identifier per row.

## Next Steps

The written decisions are for review first, because they are still marked as
proposed. After that, in order: take money out of the parts list, which is one
self-contained change that touches many files; then make the library validate on
its own; then let a machine buy from it; then make build records openable again.

One thing needs proving by hand before anyone relies on it: swap two brands of
the same rail in FreeCAD and confirm the parent assembly holds. The result goes
into the second decision record either way.

## Related

- [ADR-004 — A shared library for parts we buy](../decisions/2026-09-18_parts-library.md)
- [ADR-005 — Role modules: a stable name for a changing part](../decisions/2026-09-18_role-modules.md)
- [ADR-006 — Money leaves the bill of materials](../decisions/2026-09-18_money-out-of-the-bom.md)
- [Parts library](../parts-library.md)
- [Role modules](../roles.md)
