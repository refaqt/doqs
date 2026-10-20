# 2026-10-20 — Checks failed on CAD files that nobody had changed

## What happened

Agents in cloud sessions kept reporting the same thing in aqtuator: "the checks
fail only on CAD files that this change does not touch". Every session lost time
on it, and some agents tried to explain or fix the failures.

The cause: a cloud session clones without Git LFS content. Each CAD file
(`.FCStd`, `.step`) is then a placeholder of about 130 bytes that starts with
`version https://git-lfs.github.com/spec/v1`. Two checks hashed these
placeholders and compared them with the recorded checksums:

- `validate_cad.py` said the file "changed since its fingerprint was written"
  and that it was "saved again after its build, by hand or in the GUI".
- `validate_variants.py` said the file "no longer matches its recorded
  checksum" and that the brand may have changed it.

Both messages were wrong. Nobody had changed the files. On 2026-10-20 a clone
without LFS content failed on six compact-stage documents and twelve supplier
files in `modules/stoq`. After `git lfs pull`, all checks passed. GitHub CI
passed all along, because its workflow runs `git lfs pull`.

## Why it went wrong

1. The checks were written and tested on full clones only. Nobody ran them on a
   clone without LFS content.
2. A placeholder and an edited file gave the same result: a checksum that does
   not match. The checks did not ask why it did not match.

## What we changed

Both checks now recognise a placeholder before they hash it. They skip it and
print one warning line that names the placeholders. The check still passes.
CI still compares the real files, because it pulls LFS content first.

We did not add `git lfs pull` to the session hook. The owner does not want cloud
sessions to use LFS bandwidth (GitHub's free tier gives 1 GB a month).

## Rule

When a check compares a file with a recorded checksum, test it on a clone
without LFS content too. A placeholder is not a changed file. Say what it is.
