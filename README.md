# DOQS

**Documentation System** for modular open-hardware machines — validators, schemas, templates, and the canonical architecture specification.

Machine repositories (e.g. [qarve](https://github.com/refaqt/qarve)) include this repo as a **Git submodule** at `doqs/`.

## Use in a machine repo

Clone with submodules:

```powershell
git clone --recurse-submodules https://github.com/refaqt/qarve.git
```

Run scripts from the **machine repository root** (parent of this folder):

```powershell
python doqs/scripts/validate_all.py
python doqs/scripts/build_graph.py
```

Individual scripts: `validate_okh.py`, `validate_licenses.py`, `check_names.py`, `check_links.py`, `validate_build.py`. To write the split-licence files: `apply_licenses.py`.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/architecture.md](docs/architecture.md) | Full DOQS system specification (module layout, `simulation/`, versioning, interfaces) |
| [docs/readiness-levels.md](docs/readiness-levels.md) | OTRL / ODRL definitions for `okh.toml` |
| [docs/naming.md](docs/naming.md) | Naming conventions (machines, modules, parts) |
| [docs/naming-lexicon.md](docs/naming-lexicon.md) | Approved vocabulary for display names |
| [docs/agent-guide.md](docs/agent-guide.md) | DOQS spec files agents should read; validation commands |
| [CONTRIBUTING.md](CONTRIBUTING.md) | PR gates and submodule workflow |

Agent **setup and skills** (logging, FreeCAD debugging, DOQS naming): [refaqt/refaqt-agents](https://github.com/refaqt/refaqt-agents) at `.agents/` in machine repos.

## Layout

```
doqs/
  docs/           # Canonical specifications
  scripts/        # Validators and generators (run from machine repo root)
  data/           # Machine-readable lexicon for validators
  templates/      # OKH fragments, measurement templates, split-licence kit
  schemas/        # JSON Schema for lockfiles, firmware config
  spec/otrl.ttl   # Source ontology (IOP Alliance Open Know-How)
```

## Licence

Tooling and docs in this repository: follow the repository licence you choose for `refaqt/doqs`.

Machine repos that include this submodule use a **content-type split** (CERN-OHL-S hardware, GPL-3.0 firmware/software, CC BY-SA docs). See [docs/architecture.md](docs/architecture.md#licensing) and `python doqs/scripts/apply_licenses.py`.

`spec/otrl.ttl` is copied from [iop-alliance/OpenKnowHow](https://github.com/iop-alliance/OpenKnowHow) (GPL-3.0-or-later) — see file header.
