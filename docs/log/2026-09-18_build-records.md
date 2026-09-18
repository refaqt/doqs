# 2026-09-18 — A build record you can open again

**Role(s):** software

## What happened

A build record says what went into one physical machine. It is the thing
somebody reaches for years later, usually because something broke. It could not
actually be opened, and nobody had noticed because nobody had tried.

Work done:

- Every entry now records where to fetch it from and the exact version, not only
  a readable label. A label can be moved to point at something else, or deleted,
  and nothing about the file would look wrong.
- A new command fetches back the editable files a machine was built from. A
  second mode asks whether everything can still be fetched, without fetching
  anything, so a record that has quietly become unopenable turns up while
  somebody can still act.
- The starter files for a build record now exist. The specification had referred
  to them for a long time and they were never written.

## Decisions

**"It is gone" and "I could not ask" are different answers.** A version that has
been removed needs somebody to act. A server that could not be reached needs a
network. Reporting the second as the first sends people hunting through a
history that is perfectly fine. The check reports them separately, and a network
problem does not fail a build — a check that goes red whenever the connection
hiccups is a check people learn to ignore.

**The new command is not one of the standard checks.** It needs a network. Every
machine project would then depend on every supplier of every module being online
to pass its own checks. It stays a command you run when you want the answer.

**No stored copy of the files, for now.** That would answer the case where a
whole project disappears, and it costs storage and somewhere to put large files.
Written down so it can be picked up on purpose rather than by accident.

## Mistakes caught while building

**A test corrupted the address it was testing.** A web address was passed
through a path helper, which quietly turned the double slash into a single one.
The result looked like a folder on disk, so the failure was classified
correctly for what it was actually given — and the test blamed the code. The
code was right.

## Next Steps

The written plan for buying parts from a shared library is now complete. One
thing still needs hands on the drawing software: prove that a job whose parent
connects only to its own reference geometry survives a change of brand.

## Related

- [ADR-007 — A build record you can open](../decisions/2026-09-18_build-records.md)
- [A machine can buy from the shared library](2026-09-18_buying-from-the-library.md)
