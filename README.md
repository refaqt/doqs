# DOQS

**Documentation System** for modular open-hardware machines — validators, schemas, templates, and the canonical architecture specification.

Machine repositories (e.g. [qarve](https://github.com/refaqt/qarve)) include this repo as a **Git submodule** at `doqs/`.

## Use in a machine repo

Clone with submodules, then from the **machine repository root** run `bash setup-tooling.sh` (agents, any OS) so `doqs/` and `.agents/` track latest `main`. Humans on Windows may double-click `setup-tooling.bat`. Copy those helpers from [`templates/setup-tooling/`](templates/setup-tooling/) to the consumer root (copy-once; do not run them from this templates folder). CI may still check out the recorded pin.

```powershell
git clone --recurse-submodules https://github.com/refaqt/qarve.git
cd qarve
bash setup-tooling.sh
```

Run scripts from the **machine repository root** (parent of this folder):

```powershell
python doqs/scripts/validate_all.py
python doqs/scripts/build_graph.py
```

Individual scripts: `validate_okh.py`, `validate_licenses.py`, `check_names.py`, `check_links.py`, `validate_build.py`. To write the split-licence files: `apply_licenses.py`. Graphical SysML: double-click `syson.bat` at the machine repo root, or `python doqs/scripts/syson.py ui` (see [docs/syson.md](docs/syson.md)).

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/architecture.md](docs/architecture.md) | Full DOQS system specification (module layout, `simulation/`, versioning, interfaces) |
| [docs/syson.md](docs/syson.md) | Local SysON (graphical SysML) via Docker |
| [docs/readiness-levels.md](docs/readiness-levels.md) | OTRL / ODRL definitions for `okh.toml` |
| [docs/naming.md](docs/naming.md) | Naming conventions (machines, modules, parts) |
| [docs/naming-lexicon.md](docs/naming-lexicon.md) | Approved vocabulary for display names |
| [docs/agent-guide.md](docs/agent-guide.md) | DOQS spec files agents should read; validation commands |
| [CONTRIBUTING.md](CONTRIBUTING.md) | PR gates and submodule workflow |

Agent **setup and skills** (logging, FreeCAD debugging, DOQS naming): [refaqt/refaqt-agents](https://github.com/refaqt/refaqt-agents) at `.agents/` in machine repos.

## Layout

```
doqs/
  LICENSE         # overview: GPL-3.0 software, CC BY-SA docs
  TRADEMARKS.md
  LICENSES/       # GPL-3.0.txt, CC-BY-SA-4.0.txt
  docs/           # Canonical specifications (CC BY-SA 4.0)
  scripts/        # Validators, generators, SysON launcher (GPL-3.0)
  tools/          # Docker Compose for local SysON (GPL-3.0)
  data/           # Machine-readable lexicon (CC BY-SA 4.0)
  templates/      # OKH fragments, measurement templates, split-licence kit,
                  # setup-tooling/ and syson/ (copy-once helpers for consumer roots)
  schemas/        # JSON Schema for lockfiles, firmware config (GPL-3.0)
  spec/otrl.ttl   # Source ontology (IOP Alliance, GPL-3.0-or-later)
```

## Licence

This tools repository uses different licences for different kinds of content:

- **Software** (`scripts/`, `schemas/`, `tests/`, `tools/`) —
  [GPL-3.0](LICENSES/GPL-3.0.txt)
- **Documentation** (`docs/`, `templates/`, `data/`) —
  [CC BY-SA 4.0](LICENSES/CC-BY-SA-4.0.txt)

`spec/otrl.ttl` is GPL-3.0-or-later from [iop-alliance/OpenKnowHow](https://github.com/iop-alliance/OpenKnowHow).

Machine repos that include this submodule use a **content-type split** (CERN-OHL-S hardware, GPL-3.0 firmware/software, CC BY-SA docs). See [docs/architecture.md](docs/architecture.md#licensing) and `python doqs/scripts/apply_licenses.py`.

The REFAQT name and logo, and the DOQS name and logo, are trademarks and are not covered by the above — see [TRADEMARKS.md](TRADEMARKS.md).

See [LICENSE](LICENSE) for the full overview and directory mapping.
