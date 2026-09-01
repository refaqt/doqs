# ADR — Root launchers installed by setup-tooling

- **Date:** 2026-09-01
- **Status:** Accepted

## Context

`setup-tooling.sh` / `.bat` are copy-once files at the machine repo root. They
only ran `git submodule update --remote`. New consumer-root helpers such as
`syson.bat` were also copy-once templates, with docs telling humans to copy
them by hand. Architecture text said doqs scripts do not write consumer-root
files.

That does not scale: each new tool is missing until someone copies it, and
hardcoding one `copy` in the helper repeats the gap for the next tool.

## Decision

1. Keep `setup-tooling.sh` / `.bat` as copy-once **bootstrap** (submodule
   update). Existing machine repos refresh those two files once from
   `templates/setup-tooling/`.
2. After submodule update, the helpers run
   `python doqs/scripts/install_root_tools.py`.
3. That script copies every `*.bat` and `*.sh` under `doqs/templates/<tool>/`
   to the machine root, except `templates/setup-tooling/`. Identical bytes are
   left untouched; a changed template overwrites the root file.
4. Adding a tool means adding `templates/<tool>/<tool>.bat` and `.sh`. The
   next helper run installs them. Do not copy READMEs. Do not write `AGENTS.md`
   or `README.md`.

## Consequences

- Double-click `setup-tooling.bat` creates `syson.bat` (and later launchers)
  without a separate copy step.
- Until a machine repo refreshes `setup-tooling.*` once, it still will not
  install launchers.
- Generated launchers may show up in `git status` after a template change;
  commit them if they should exist after clone.

## Related

- [docs/syson.md](../syson.md)
- [2026-09-01_syson-session-adapter.md](2026-09-01_syson-session-adapter.md)
