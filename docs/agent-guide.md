# Agent reference — DOQS domain spec

Agent **setup and skills** live in [refaqt/refaqt-agents](https://github.com/refaqt/refaqt-agents), mounted at `.agents/` in machine repos. Read root `AGENTS.md` first.

This document lists **what to read from the `doqs/` submodule** when doing structural or domain work.

## Submodule

Machine repos include DOQS as a Git submodule at `doqs/`. Without it, validators and templates are unavailable:

```powershell
git submodule update --init --recursive
```

Develop tools in `github.com/refaqt/doqs`, then bump the submodule pointer in each machine repo.

## Spec files to read

| File | When |
|------|------|
| `doqs/docs/architecture.md` | Non-trivial design, new modules, versioning, interfaces, builds, licensing |
| `doqs/docs/architecture.md` (Licensing section) | Adding `LICENSE` / `LICENSES/` / `TRADEMARKS.md` to a machine or extracted-module repo |
| `doqs/docs/architecture.md` (Simulation section) | Adding or interpreting design-time analysis under `simulation/` |
| `doqs/docs/architecture.md` (Measurement section) | Physical test campaigns under `measurement/` |
| `doqs/docs/architecture.md` (Software section) | Host-side applications under `software/` |
| `doqs/docs/decisions/2026-06-24_freecad-master-sketches-body.md` | FreeCAD top-down design, master sketches, Assembly Insert failures |
| `doqs/docs/readiness-levels.md` | OTRL/ODRL in `okh.toml` |
| `doqs/docs/naming.md` | Naming modules, parts, repos |
| `doqs/docs/naming-lexicon.md` | BOM and part display names |
| `doqs/templates/` | OKH fragments, measurement templates, domain artefacts |

The machine's `docs/architecture.md` is a **short overview + pointer** to `doqs/docs/architecture.md`.

## Narrative docs (structure vs procedure)

DOQS machine repos use these folders under `docs/` (see architecture.md folder trees):

| Folder | Purpose |
|--------|---------|
| `docs/log/` | Chronological activity record across all roles |
| `docs/mistakes/` | Incidents and prevention rules |
| `docs/decisions/` | Architecture Decision Records |

**How** agents write and maintain these entries: `.agents/rules/living-docs.md` and `.agents/skills/log/` / `.agents/skills/mistake-log/`.

## Validation

From the **machine repository root** after OKH, BOM, or path changes:

```powershell
python doqs/scripts/validate_all.py
```

For a new repo, or after adding a first-level content directory (`cad/`, `firmware/`, …):

```powershell
python doqs/scripts/apply_licenses.py
```

`validate_all.py` runs, in order: `validate_okh.py`, `validate_licenses.py`, `check_names.py`, `check_links.py`, `validate_build.py`.

Before tagging:

```powershell
python doqs/scripts/validate_okh.py --expected-version X.Y.Z
```

## CI

```yaml
- uses: actions/checkout@v4
  with:
    submodules: recursive
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
- run: python doqs/scripts/validate_all.py
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full gate list.

## Where to change what

| Change | Repository |
|--------|------------|
| Cross-machine process rules, agent skills | **refaqt-agents** (`.agents/` submodule) |
| DOQS layout, validators, naming spec | **doqs** (this repo) |
| Machine-specific behaviour | Machine repo `docs/` and `.agents-local/` |
