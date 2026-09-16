# DOQS

**Documentation System** for modular open-hardware machines — validators, schemas, templates, and the canonical architecture specification.

Machine repositories (e.g. [qarve](https://github.com/refaqt/qarve)) include this repo as a **Git submodule** at `doqs/`.

## Use in a machine repo

Clone with submodules, then from the **machine repository root** run `bash setup-tooling.sh` (agents, any OS) so `doqs/` and `.agents/` track latest `main` and root launchers such as `syson.bat` are installed. Humans on Windows may double-click `setup-tooling.bat`. Copy those helpers from [`templates/setup-tooling/`](templates/setup-tooling/) to the consumer root (copy-once bootstrap; do not run them from this templates folder). CI may still check out the recorded pin.

```powershell
git clone --recurse-submodules https://github.com/refaqt/qarve.git
cd qarve
bash setup-tooling.sh
```

Then run everything through one command, from the **machine repository root**:

```powershell
bash doqs.sh check       # every gate, plus "are the generated files current?"
bash doqs.sh generate    # write every generated file, in the right order
bash doqs.sh list        # every command, and the scripts each one runs
```

`doqs.bat` does the same on Windows, and `python doqs/doqs.py <command>` works without either
launcher. `setup-tooling.sh` installs both launchers for you.

`doqs list` is the full command list, so this README does not repeat it. The scripts under
`doqs/scripts/` still work when called directly: `python doqs/scripts/validate_all.py` runs the
same seven gates it always has. `doqs check` runs those seven plus three checks on generated
files.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/architecture.md](docs/architecture.md) | Full DOQS system specification (module layout, `simulation/`, versioning, interfaces) |
| [docs/variants.md](docs/variants.md) | Product families: many lengths and options of one design, and how a machine consumes one configuration |
| [docs/syson.md](docs/syson.md) | Local SysON (graphical SysML) via Docker |
| [docs/readiness-levels.md](docs/readiness-levels.md) | OTRL / ODRL definitions for `okh.toml` |
| [docs/naming.md](docs/naming.md) | Naming conventions (machines, modules, parts) |
| [docs/naming-lexicon.md](docs/naming-lexicon.md) | Approved vocabulary for display names |
| [docs/agent-cad.md](docs/agent-cad.md) | Agents editing FreeCAD models in the open GUI document: setup, the save guard, fingerprints instead of screenshots |
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
                  # variants/ (product-family kit), cad/ (the build_model.py
                  # seed), agent-cad/ (MCP config and the save guard),
                  # setup-tooling/ (copy-once bootstrap) and syson/ (root
                  # launchers)
  schemas/        # JSON Schema for lockfiles, catalogues, instances,
                  # BOM sources, firmware config (GPL-3.0)
  spec/otrl.ttl   # Source ontology (IOP Alliance, GPL-3.0-or-later)
```

## Licence

This tools repository uses different licences for different kinds of content:

- **Software** (`scripts/`, `schemas/`, `tests/`, `tools/`, and the CI, editor and agent
  configuration) — [GPL-3.0](LICENSES/GPL-3.0.txt)
- **Documentation** (`docs/`, `templates/`, `data/`) —
  [CC BY-SA 4.0](LICENSES/CC-BY-SA-4.0.txt)

[LICENSE](LICENSE) holds the full mapping. This list is a summary of it.

The executable launchers under `templates/` are GPL-3.0-or-later and carry SPDX
headers; `templates/cad/build_model.py` is a seed whose resulting per-module file
belongs to the machine repository. See [`templates/LICENSE`](templates/LICENSE).

`spec/otrl.ttl` is GPL-3.0-or-later from [iop-alliance/OpenKnowHow](https://github.com/iop-alliance/OpenKnowHow).

Machine repos that include this submodule use a **content-type split** (CERN-OHL-S hardware, GPL-3.0 firmware/software, CC BY-SA docs). See [docs/architecture.md](docs/architecture.md#licensing) and `python doqs/scripts/apply_licenses.py`.

The REFAQT name and logo, and the DOQS name and logo, are trademarks and are not covered by the above — see [TRADEMARKS.md](TRADEMARKS.md).

See [LICENSE](LICENSE) for the full overview and directory mapping.
