# 2026-09-18 — A machine can buy from the shared library

**Role(s):** software

## What happened

The shared library could check itself, but no machine could use it. This adds
the two ways in, and the checks that replace the file an earlier design would
have generated.

Work done:

- An ordinary bought part is now one extra cell on a row you already write. No
  folder, no extra file, nothing generated. The reference is checked: it must
  resolve, still be sold, and agree with the brand and part number written
  beside it.
- A part that carries requirements gets a job container instead, named after the
  job. It holds the requirements and one line saying what fills the job today.
- Five checks replace the generated file. The most useful one reads the drawing
  and compares it against the text, which no generated file could do.
- The worked machine example now mounts the library, buys a screw by one cell,
  and holds a job filled by a rail with a second brand recorded as acceptable.

## Decisions

**Changing brand changes one file.** That is the whole promise of the job
container, so it is tested as a real before-and-after comparison rather than a
passing check. Switching the rail from one brand to the other rewrites the job's
own manifest and nothing else: every row identifier, every folder name and every
file above it stay identical.

**A reference names the brand and the family, not the folders between them.**
Short enough to read in a table cell, and it stays correct if the library
changes how it arranges its own folders.

**What you buy must be one of the parts you approved.** The list of acceptable
parts was going to be optional record-keeping. Making the current choice have to
appear in it costs nothing and turns the list into something that stays true.

**A part that does not fit is refused by name.** A screw cannot fill a
linear-guide job, and the message says which connection is missing rather than
only that something is wrong.

## Mistakes caught while building

**A generated file quietly ate a hand-written row.** A test row was added to a
folder whose parts list is written by a script. The script rewrote the file and
the row vanished without a word. It belonged in the job container, which is
written by people. Worth remembering: check whether a file is yours to edit
before editing it.

**Drawings from the library were being checked as if we had drawn them.** The
check that proves a drawing still matches its recorded measurements ran over
files that came from a brand. There is nothing to rebuild them from. They are
now skipped wherever they are mounted, not only in the library itself.

## Next Steps

One piece of the written plan is left: making a build record something you can
open again, by recording exactly which version of everything went into a machine
and adding a command that fetches it all back.

One thing still needs hands on the drawing software: prove that a job whose
parent connects only to its own reference geometry survives a brand change.

## Related

- [ADR-005 — Role modules: a stable name for a changing part](../decisions/2026-09-18_role-modules.md)
- [Role modules](../roles.md)
- [The shared parts library checks itself](2026-09-18_parts-library-validates.md)
