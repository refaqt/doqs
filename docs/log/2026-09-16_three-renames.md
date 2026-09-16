# 2026-09-16 — Three scripts renamed, sixteen left alone

**Role(s):** software

## What happened

Two gates were called `check_*` while seven identical ones were called
`validate_*`. Both build an internal `check_all()` and return 0 or 1; there was no
difference to find. And `build_graph.py` had nothing to do with `builds/`,
`build.toml`, or `validate_build.py`, which is what a reader expects from that
prefix.

| Old | New |
| --- | --- |
| `check_names.py` | `validate_names.py` |
| `check_links.py` | `validate_links.py` |
| `build_graph.py` | `resolve_graph.py` |

**Three, not nineteen.** Once `doqs.py` exists, script names are internal: nobody
types `validate_okh.py`, they type `doqs check`. Renaming a file whose only readers
are doqs maintainers buys a tidier `ls` and costs a red CI run in a repository we
cannot see. These three were renamed because the old name actively misleads.

## Two names that can never change

`install_root_tools.py` is named inside `setup-tooling.sh`, which every consumer
copies **once** and never refreshes. `cad_build.py` is found by filename in every
`build_model.py` already copied into a module. Renaming either strands copies we
cannot reach. Both facts are now in `CONTRIBUTING.md` and in
`tests/test_renames.py`, which fails if either file moves.

## The stubs exit 2

Each old name is still there until 16 December 2026, printing the new name and
exiting **2**. Not 0: a stub that quietly succeeded is how a repository stops
running a gate, or stops regenerating a file, and nobody notices for months.
qarve's CI calls `build_graph.py`, so it will get a clear message rather than a
silent skip.

## The rule, written down

`CONTRIBUTING.md` now carries it: a script is `<verb>_<object>.py` with one of six
verbs, a library is `<topic>_rules.py`, and `cad_` marks code that runs inside
FreeCAD. `tests/test_renames.py` checks every file against it, so the next script
cannot drift.

## Records, not rewritten

Two decision records name `check_names.py`. A decision record says what was decided
and when, so the sentence stays; the current filename is added beside it.

## Numbers

280 tests pass, up from 272.

## Next Steps

doqs is done. Step 6 is aqtuator: move its CI to `doqs check`, delete its local
hook copy once `doqs setup` installs one, and bump the pin.
