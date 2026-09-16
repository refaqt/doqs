# ADR — CAD tools live in doqs, not as per-module copies

- **Date:** 2026-09-16
- **Status:** Accepted

## Context

`templates/cad/` shipped three scripts that were copied into every module's
`cad/` directory. Only 19 of their 532 lines were per-module content:

| File | Lines | Per-module content |
| --- | ---: | --- |
| `fingerprint.py` | 193 | none — generic measurement |
| `sync_params.py` | 180 | none — generic CSV → Spreadsheet sync |
| `build_model.py` | 159 | 19 (`build()`) |

The rest was a harness the file's own docstring told you not to edit. Three
problems followed.

**The copies were unversioned forks.** `doqs` is a submodule that
`setup-tooling.sh` tracks with `--remote`. A copy bypasses that, so a fix to the
save discipline — the thing preventing the FreeCAD #8924 data loss described in
`agent-cad.md` — never reached a module already created.

**The fingerprint schema could desync silently.** `fingerprint.py` wrote
`"schema": rules.FINGERPRINT_SCHEMA`, read **live** from `cad_rules.py`, while
the `measure()` producing that payload was the **frozen copy**. Bumping
`FINGERPRINT_SCHEMA` would make every stale copy stamp the new number on an old
payload; `load_fingerprint()` would see a matching schema, accept it, and
compare fields that had moved — a silent wrong comparison in the file whose job
is catching silent geometry regressions.

**There was no technical reason for the copy.** `fingerprint.py` already walked
up to `doqs/scripts/` to import `cad_rules` from inside FreeCAD. The mechanism
existed and was in use.

The project had already made this move for the sibling script: "Resolution is a
doqs script, not a per-module copy" (`architecture.md`, on `resolve_params.py`).

## Decision

1. `fingerprint.py` → `doqs/scripts/cad_fingerprint.py` and `sync_params.py` →
   `doqs/scripts/cad_sync_params.py`, unchanged in behaviour. `cad_rules` is now
   a sibling import, which deletes the upward-walk helper.
2. The scaffolding half of `build_model.py` → `doqs/scripts/cad_build.py`,
   exposing `run(build_fn, cad_dir=None, document=None)`, `open_document()`,
   `fcstd_path()` and `sheet()`.
3. `templates/cad/build_model.py` becomes a ~65-line seed: a bootstrap that
   walks up to `doqs/scripts/`, and `build()`. It stays a per-module file
   because it **is** the design — the reviewable text diff standing in for an
   opaque `.FCStd`.
4. Every entry point takes an explicit `cad_dir` instead of inferring its
   location from `__file__`.
5. `validate_cad.py` gains a fourth gate that FAILs on a leftover
   `cad/fingerprint.py`, `cad/sync_params.py`, or a `build_model.py` still
   containing `def open_document(`.
6. FreeCAD stays imported lazily inside functions, so these modules import under
   plain Python and their CSV and path handling is unit-testable — which it now
   is, in `tests/test_cad_build.py`.

## Consequences

**Breaking for existing machine repos.** Gate 5 fails until the two copies are
deleted and `build_model.py` is re-seeded with its `build()` body pasted back.
`agent-cad.md` carries the migration steps. A warning was rejected: a stale copy
still runs, so a warning would be ignored while the schema hazard stayed live.

**A latent bug is fixed.** `export_variant.py` ran the sync script via
`exec(open(sync).read())` inside a generated macro, where `__file__` pointed at
a temp file in `/tmp`. `params.csv` resolved to `/tmp/params.csv`, missed, and
raised. `export_variant.py` had no test coverage, so this had gone unnoticed.
The macro now imports `cad_sync_params` and passes `cad_dir` explicitly.

**The fingerprint format is unchanged**, so `FINGERPRINT_SCHEMA` stays at 1.
Committed fingerprints remain valid; measurement logic and schema constant now
move together.

**Licensing gets simpler.** ~500 lines of tool code leave `templates/`, which is
CC BY-SA documentation, for `scripts/`, which is GPL-3.0. See the licence commit
that follows this one.
