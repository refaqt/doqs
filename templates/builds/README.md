# Build records

A `builds/<id>/` folder records **one physical machine**: what went into it, on
the day it was built. One folder per machine — a shipped customer machine, a
prototype, the one in your own workshop.

It is not a design document. The design says what the machine should be; this
says what one machine actually is. They drift apart the moment somebody repairs
something, and that is normal.

## Starting one

1. Copy `example-baseline.toml` to `builds/<your-id>/build.toml`.
2. Fill in the machine, the date, the owner and the location.
3. For every module, record where it came from, its readable version, and its
   exact commit.
4. `python doqs/doqs.py check` — validation says what is missing.

Beside `build.toml` you may keep a `notes.md` and a `photos/` folder. Both are
for the things a file of versions cannot hold: what was different about this
one, and what it looked like on the day it left.

## Why the exact commit

A version tag can be moved to a different commit, or deleted. If that happens,
your record still reads `v1.0.0` and now describes something else, or nothing —
and nothing about the file would look wrong.

The commit cannot be moved. It is what turns the record into something somebody
can still open in five years, usually because something broke and they were not
there when it was built.

## Checking that a record can still be opened

```bash
python doqs/doqs.py restore-build builds/serial-0042 --check
```

Fetches nothing and asks whether every pinned commit is still reachable. Worth
running on a schedule: it finds a record that has gone unopenable while somebody
can still do something about it.

It exits `1` when a commit is genuinely gone and `2` when a repository could not
be reached — different problems with different answers.

## Opening one

```bash
python doqs/doqs.py restore-build builds/serial-0042 --out /tmp/serial-0042
```

Clones every pinned repository at its exact commit. You get the editable design
files that machine was built from, not the latest ones.
