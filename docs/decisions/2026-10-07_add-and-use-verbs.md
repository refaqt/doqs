# ADR-016 — Two new script verbs: `add_` and `use_`

- **Date:** 2026-10-07
- **Status:** Accepted

Write this file in B2 English. Follow `.agents/rules/communication.md`. Keep official names, file paths, and numbers exact.

## Context

Every script in `scripts/` starts with a verb that says what it does: `validate_` reads,
`resolve_` derives a generated file, `apply_` writes a fixed set of files, `install_` copies
templates, `export_` produces one artefact, `restore_` rebuilds from a record
([CONTRIBUTING.md](../../CONTRIBUTING.md)).

The commands that add a part to a design fit none of them. `add_part.py` takes one named
thing (a supplier's part) into two repositories, append-only. `use_part.py` links a thing
that exists (a library part) into a module. `add_interface.py` adds one named interface to
three places. They are not fixed sets of files, not generated files, not templates.

## Decision

Two verbs join the table:

| Verb | Means |
| --- | --- |
| `add_` | Adds one named thing to a repository, append-only and idempotent: a part, an interface. Takes `--json` and `--dry-run`. |
| `use_` | Links a thing that already exists into a module: a library part into a BOM, a manifest and a SysML file. Takes `--json` and `--dry-run`. |

The scaffold command keeps `install_` (`install_module.py`: it copies templates). The
wrapper command keeps `export_` (`export_wrapper.py`: it produces one artefact). The mirror
check keeps `validate_` (`validate_mirror.py` reads; `--apply` is its one writing option,
like `restore_`). `cad_wrap_step.py` keeps the `cad_` prefix: it runs inside FreeCAD.

Every one of these commands prints the same report shape (`report_rules.Report`): what it
wrote, what it changed, what it left alone, warnings, errors, and what to do next. With
`--json` the report is machine-readable, so a tool such as fabriq and an agent read the
same result.

## Consequences

- A reader of `scripts/` still learns what a file does from its first word.
- The command list in `doqs list` and in `docs/using-doqs.md` grows by six entries, and
  the page test keeps the two in step.
