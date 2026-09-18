# 2026-09-18 — The shared parts library checks itself

**Role(s):** software

## What happened

The written decision for a shared parts library existed, but nothing could
check one. This adds the checks, a worked example, and the files somebody needs
to start a library of their own.

Work done:

- A repository is a parts library when it carries one marker file at its root.
  The marker decides it, not the folder it is mounted in, so a machine can put a
  library anywhere and still leave it out of its own checks.
- A library has its own licence layout. The record we compile is ours and is
  shared under the documentation licence. Every geometry file and datasheet
  belongs to the brand that made it, and is carved out.
- A family's catalogue is one table: one row per part number you can order.
  Missing status, missing terms and a repeated part number are all refused.
- Checksums are now compared, not just stored. A worked example proves that a
  file changed after it was recorded is caught.
- A worked library ships as a test fixture: two brands with a rail family each,
  one that allows us to keep its files and one that does not.

## Decisions

**The drawing check does not run on a library.** It exists to prove that a
drawing still matches the measurements recorded beside it, and to tell you to
rebuild it when it does not. In a library there is nothing to rebuild from: the
file came from the brand. Its integrity is proved by an exact checksum, which is
a stronger test and does not need drawing software installed.

**Comment lines in a table are now skipped.** Every table a person edits ships
as an example with comments explaining what to write. Following that example
used to break the reader, and the failure blamed the header rather than the
comments. Found by copying our own example and running the checks. One shared
reader now handles it, so the examples can be used exactly as they ship.

**The catalogue gained a notes column.** The written guide told people to record
a replacement part number there, and the table had no such column. The guide was
right, so the table changed.

**One lookup is remembered instead of repeated.** A check asked "is this inside a
library?" once per file, and each question searched the whole project again. On
a realistic library that is minutes of waiting. It is now asked once and the
answer reused, which is forty times faster on the test alone.

## Next Steps

A machine cannot buy from a library yet: that is the next piece of work. It adds
the job container in a machine, the checks that its choice still fits, and the
one cell that points a parts-list row at a library part.

## Related

- [ADR-004 — A shared library for parts we buy](../decisions/2026-09-18_parts-library.md)
- [Parts library](../parts-library.md)
- [Role modules](../roles.md)
