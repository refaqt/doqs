# 2026-09-18 — The parts list says what is inside, not what it costs

**Role(s):** software

## What happened

Seven of the sixteen fixed columns in a parts list held prices and distributors.
A price changes every week and a design changes rarely, so the two do not belong
in one file or one history. In practice nobody updated the numbers, and they
quietly went stale while people kept trusting them.

Work done:

- The parts list now has twelve columns instead of sixteen. Cost, distributors
  and their part numbers are gone. What the part is, how many, what it weighs and
  who makes it all stay.
- A file that still has the old sixteen columns now fails with a message that
  names each step of the fix and links the reasoning. It does not just say the
  columns are wrong.
- A new column holds a reference to a part in the shared library we are
  building. Its shape is checked, so a typo fails at once instead of at ordering
  time.
- Three written decisions moved from proposed to accepted, and the question
  about our own product families is answered rather than left open.

## Decisions

**We found the confusion in our own data.** The old files wrote HIWIN in the
first supplier column. HIWIN makes the rail; it does not sell it to us. So that
column was never a supplier at all, and the migration renames it to brand rather
than deleting it. That is better evidence for the change than any argument.

**A second source is not a column.** Three fixed distributor slots were always a
guess at how many alternatives a part could have. The existing interchange tag
says "take either one of these" without limiting the count.

**What we owe a pricing system is one identifier per row.** This project answers
what is inside a machine and how many. Something else multiplies that by whatever
prices are true today. Neither side has to know how the other works.

**Our own product families keep their generated files.** With the shared library
you name the exact part, so an update cannot substitute a different one behind
your back. With one of our own families, the family names the parts, so taking a
newer version really can change your design without you choosing it. Two
different situations, so two different answers.

## Next Steps

Machine repositories must migrate their own parts lists. Delete five columns,
rename two, add one empty column. The check names every step when it finds an old
file. The prices being deleted are almost certainly out of date, which is the
argument for the change.

Next in this line of work: make the shared parts library validate on its own.

## Related

- [ADR-006 — Money leaves the bill of materials](../decisions/2026-09-18_money-out-of-the-bom.md)
- [ADR-005 — Role modules: a stable name for a changing part](../decisions/2026-09-18_role-modules.md)
- [One home for the parts we buy](2026-09-18_parts-library.md)
