# Modules and folders

Part of the doqs specification. Start at the [overview](../architecture.md).

## Modularity Model

### The Core Rule

> Every folder in this project is a module. Every module has the same internal structure. The project root is the top-level module.

This means: `cnc-mill/` has the same first-level folders as `cnc-mill/modules/x-axis/`. There is no structural distinction between the machine, a sub-assembly, or a part. The only differences are scope and which sub-folders are non-empty.

### Two Deployment Modes

**Mode A — Embedded (monorepo)**

All modules live as plain folders under `modules/` in the main repo.

```
cnc-mill/                  ← one Git repo
├── modules/
│   ├── x-axis/
│   └── spindle/
└── ...
```

**Mode B — Extracted (multi-repo, Git submodules)**

A module gets its own GitHub repo. It comes back into the parent at `modules/x-axis/` as a Git submodule. The path is unchanged, so all FreeCAD links, SysML imports, and Python paths continue working without modification.

```
cnc-mill/
└── modules/
    └── x-axis/            ← Git submodule → github.com/org/x-axis
```

### Working Inside an Extracted Submodule

When `modules/x-axis/` is a Git submodule, that folder **is** the cloned repository. You do not need a separate clone. Work directly in that folder:

```bash
cd modules/x-axis

# Make your edits, then:
git add .
git commit -m "cad(carriage): update hole pattern"
git push                   # pushes to github.com/org/x-axis

# Back in the parent repo, the submodule pointer is now out of date:
cd ../..
git add modules/x-axis     # stages the new commit hash
git commit -m "chore(submodules): bump x-axis to latest"
git push
```

The parent repo stores only a commit hash pointing into the submodule repo — not the files themselves. `git add modules/x-axis` updates that pointer. If you pull the parent repo on another machine, run `git submodule update --remote` to pull the latest submodule commits.

The full cycle when someone else has pushed to the submodule:

```bash
# Inside the parent repo:
git submodule update --remote --merge   # fetches and merges submodule changes
git add modules/x-axis
git commit -m "chore(submodules): sync x-axis"
```

### Migrating a Module from Embedded to Extracted

```bash
# 1. Split the module's history into its own branch
git subtree split --prefix=modules/x-axis -b split-x-axis

# 2. Push to a new GitHub repo
cd ..
git clone https://github.com/org/x-axis.git
cd x-axis
git pull ../cnc-mill split-x-axis && git push origin main

# 3. Replace folder with submodule at the same path
cd ../cnc-mill
git rm -r modules/x-axis
git submodule add https://github.com/org/x-axis.git modules/x-axis
git commit -m "chore(modules): extract x-axis to standalone repo"

# 4. Update the repo URL in modules/x-axis/okh.toml
#    repo = "https://github.com/org/x-axis"
```

## Folder Structure

Every module — at every nesting depth — uses the same set of first-level folders. The project root (`cnc-mill/`) and a leaf module (`modules/x-axis/modules/drive-belt/`) have identical structures; only their contents differ in scope.

### First-Level Folders (Every Module)

| Folder           | Contents                                                                                           |
| ---------------- | -------------------------------------------------------------------------------------------------- |
| `bom/`           | Bill of materials (CSV source data + processing script)                                            |
| `cad/`           | FreeCAD files: `assemblies/`, `parts/`, `exports/`, `params/` (model overrides), `vendor/` (third-party geometry of purchased parts) |
| `architecture/`  | SysML files — requirements, block definitions, **interfaces (ports)**                              |
| `docs/`          | Narrative prose: activity log, mistakes, decisions (see [refaqt-agents](https://github.com/refaqt/refaqt-agents) for entry format) |
| `manufacturing/` | Fabrication drawings, G-code, assembly guides                                                      |
| `simulation/`    | Design-time analysis: case definitions, run scripts, result summaries                             |
| `measurement/`   | Physical test campaigns: protocols, result summaries, external-data manifests                     |
| `modules/`       | Sub-modules (each with this same structure). Adapters live under `modules/adapters/` by convention |

In a part file under `cad/`, the top object of the model tree is a Part container (`App::Part`), with the Body inside it. Assembly files are exempt. See [the decision](../decisions/2026-10-01_part-container-on-top.md) and [agent-cad.md](../agent-cad.md#the-model-tree-of-a-part).

A part offers named mounting frames (`IF_...`) inside that Part container, placed by expressions over `Params`. Assembly joints attach to these frames, never to a face, an edge or a point of a solid. A frame name is part of the module's interface. See [the decision](../decisions/2026-10-06_joints-attach-to-frames.md) and [agent-cad.md](../agent-cad.md#joints-attach-to-mounting-frames).

Each first-level content folder that exists carries a short `LICENSE` pointer; see [Licensing](#licensing).

**Special folders at the project root only:**

| Folder      | Contents                                                                    |
| ----------- | --------------------------------------------------------------------------- |
| `firmware/` | Embedded software targets — see [Firmware](firmware-and-software.md#firmware) |
| `software/` | Host-side software (desktop apps, analysis libraries) — see [Software](firmware-and-software.md#software) |
| `builds/`   | Lockfiles for physical machine instances — see [Builds](builds.md) |
| `graph/`    | Generated reverse-usage graph (`usage-graph.json`) — see [Versioning](versioning.md#parent-relationships-reverse-usage-graph) |
| `doqs/`     | Tools submodule (`github.com/refaqt/doqs`)                                     |

### Full Tree

```
cnc-mill/
│
├── okh.toml                         # Machine-level OKH manifest
├── README.md
├── LICENSE                          # overview: CERN-OHL-S / GPL-3.0 / CC BY-SA
├── TRADEMARKS.md                    # reserved marks (not licensed)
├── LICENSES/                        # full legal texts
│   ├── CERN-OHL-S-2.0.txt
│   ├── GPL-3.0.txt
│   └── CC-BY-SA-4.0.txt
├── CONTRIBUTING.md
├── CHANGELOG.md
├── .gitmodules
├── .gitattributes                   # Git LFS config
│
├── bom/                             # Top-level BOM (GENERATED from modules)
│   ├── LICENSE                      # CERN-OHL-S v2.0
│   ├── bom.csv                      # Do not edit by hand
│   └── aggregate_bom.py
│
├── cad/                             # Top-level assembly CAD
│   ├── LICENSE                      # CERN-OHL-S v2.0
│   ├── README.md                    # FreeCAD version, workbench, path config
│   ├── assemblies/
│   │   └── machine.FCStd            # Links to module parts via relative paths
│   └── exports/
│       ├── machine.step
│       └── machine.stl
│
├── architecture/                    # Top-level SysML
│   ├── LICENSE                      # CERN-OHL-S v2.0
│   └── machine.sysml                # Imports from module architecture/ folders
│
├── docs/                            # Narrative documentation only
│   ├── LICENSE                      # CC BY-SA 4.0
│   ├── log/                         # Chronological activity record (all roles)
│   │   └── YYYY-MM-DD_topic.md
│   ├── mistakes/                    # Incidents and prevention rules
│   │   └── YYYY-MM-DD_topic.md
│   └── decisions/                   # Architecture Decision Records
│       └── YYYY-MM-DD_topic.md
│
├── manufacturing/
│   ├── LICENSE                      # CERN-OHL-S v2.0
│   └── notes/
│       └── assembly-guide.md
│
├── simulation/
│   ├── LICENSE                      # GPL-3.0
│   ├── README.md
│   ├── cases/
│   └── results/
│
├── measurement/                     # Physical test campaigns — see Measurement section
│   ├── LICENSE                      # CC BY-SA 4.0
│   ├── README.md
│   ├── cases/
│   ├── results/
│   └── data-index.csv               # Manifest of data held in external storage
│
├── modules/
│   ├── LICENSE                      # CERN-OHL-S v2.0 (embedded modules inherit this)
│   └── x-axis/                      # ← identical structure at every depth
│       ├── okh.toml
│       ├── README.md
│       │
│       ├── bom/
│       │   └── bom.csv              # Source BOM for this module
│       │
│       ├── cad/
│       │   ├── README.md
│       │   ├── params/
│       │   │   ├── default.csv     # Base parameter set (all keys)
│       │   │   ├── 500mm.csv       # Override file: only rows that differ from default
│       │   │   └── ballscrew.csv   # Another override
│       │   ├── params.csv          # ACTIVE model — generated by resolve_params.py
│       │   ├── build_model.py      # This part's geometry — build(); scaffolding is in doqs
│       │   ├── assemblies/
│       │   │   └── x-axis.FCStd     # FreeCAD assembly; spreadsheet drives dimensions
│       │   ├── parts/
│       │   │   ├── carriage/
│       │   │   │   ├── carriage.FCStd
│       │   │   │   └── exports/
│       │   │   │       ├── carriage.step
│       │   │   │       ├── carriage.dxf
│       │   │   │       └── carriage.stl
│       │   │   └── motor-mount/
│       │   │       ├── motor-mount.FCStd
│       │   │       └── exports/
│       │   └── exports/
│       │       ├── x-axis.step
│       │       └── x-axis.stl
│       │
│       ├── architecture/            # SysML: requirements + block definitions
│       │   └── x-axis.sysml
│       │
│       ├── docs/
│       │   ├── log/
│       │   ├── mistakes/
│       │   └── decisions/
│       │
│       ├── manufacturing/
│       │   ├── drawings/
│       │   ├── cam/
│       │   └── notes/
│       │       └── assembly-guide.md
│       │
│       ├── simulation/
│       │   ├── README.md
│       │   ├── cases/
│       │   │   └── carriage-deflection/
│       │   └── results/
│       │       └── carriage-deflection/
│       │           └── summary.md
│       │
│       ├── measurement/
│       │   ├── README.md
│       │   ├── cases/
│       │   │   └── carriage-stiffness/
│       │   ├── results/
│       │   │   └── carriage-stiffness/
│       │   │       └── summary.md
│       │   └── data-index.csv
│       │
│       └── modules/                 # Nested sub-modules (same layout recursively)
│           └── drive-belt/
│               ├── okh.toml
│               ├── bom/
│               ├── cad/
│               ├── architecture/
│               ├── docs/
│               ├── manufacturing/
│               ├── simulation/
│               └── modules/
│
├── firmware/                        # See Firmware section
│   ├── LICENSE                      # GPL-3.0
│   └── ...
│
├── software/                        # See Software section
│   ├── LICENSE                      # GPL-3.0
│   └── ...
│
├── builds/                          # Lockfiles for physical machine instances
│   ├── LICENSE                      # CERN-OHL-S v2.0
│   ├── README.md
│   ├── example-baseline.toml        # Template for new builds
│   └── serial-0042/
│       ├── build.toml               # Pins exact version of every module
│       ├── notes.md                 # Non-standard modifications, history
│       └── photos/
│
├── graph/                           # Generated reverse-usage graph
│   └── usage-graph.json             # Built by doqs/scripts/resolve_graph.py
│
└── doqs/                            # Separate tools repo, included as submodule
    └── ...
```

`doqs/` and `graph/` have no directory `LICENSE` stubs — the tools submodule and generated graph are outside this content-type mapping.

### Licensing

The **DOQS tools repository** (`refaqt/doqs`) is not a machine repo. It uses a two-way split, GPL-3.0 and CC BY-SA 4.0, with carve-outs inside `templates/`. The `LICENSE` file in that repository holds the full mapping and is the only place it is written down. `apply_licenses.py --root <doqs>` detects the tools repo and writes that kit instead of the machine three-way split.

**Machine and extracted-module repositories** use a **content-type split**, not a single blanket licence:

| Content | Directories | Licence |
| --- | --- | --- |
| Hardware | `cad/`, `architecture/`, `manufacturing/`, `bom/`, `builds/`, `modules/` | CERN-OHL-S v2.0 |
| Third-party supplier geometry | `**/cad/vendor/` (carved out of `cad/`) | Supplier's own terms — **not** CERN-OHL-S |
| Firmware & software | `firmware/`, `software/`, `simulation/` | GPL-3.0 |
| Media & documentation | `docs/`, `measurement/` | CC BY-SA 4.0 |

Layout at each Git repository root:

- `LICENSE` — overview mapping directories to licences
- `LICENSES/` — full legal texts (`CERN-OHL-S-2.0.txt`, `GPL-3.0.txt`, `CC-BY-SA-4.0.txt`)
- `TRADEMARKS.md` — organisation and project names/logos are reserved marks, not covered by the licences above
- A short `LICENSE` pointer in each mapped first-level directory that exists
- Root `okh.toml` `license = "CERN-OHL-S-2.0"` (OKH describes the hardware project; a comment points at the split)
- `README.md` Licence section naming the three licences

Embedded modules inherit via `modules/LICENSE`. When a module is extracted to its own GitHub repo, run the apply script at that repo root so it gets the full kit. Tooling submodules (`doqs/`, `.agents/`) are not scanned as machine roots.

**`cad/vendor/` is the one exception to the content-type map.** It holds CAD of purchased, off-the-shelf components, which belong to their suppliers. Writing the CERN-OHL-S stub over those files would claim a licence on files the project does not own, so `apply_licenses.py` writes a separate `cad/vendor/LICENSE` carving the directory out — at any module depth, not just the first level. See [variants.md](../variants.md#geometry-of-purchased-components).

Templates live in `doqs/templates/licensing/`. From the machine repository root:

```powershell
python doqs/scripts/apply_licenses.py           # write missing/outdated files
python doqs/scripts/apply_licenses.py --check   # generated files only
python doqs/scripts/validate_licenses.py        # generated files + README + okh.toml
```

`apply_licenses.py` does not rewrite `README.md` or `okh.toml`. Extra exclusion paragraphs in a directory `LICENSE` (for third-party vendor files) are allowed; validators check required phrases, not byte-for-byte identity.

Organisation in `TRADEMARKS.md` comes from `okh.toml` `organisation` when set, otherwise `REFAQT`. Project name comes from `okh.toml` `name`.

---

### Cross-Module SysML Imports

With `architecture/` at the first level, import paths are:

```sysml
// architecture/machine.sysml
import '../../modules/x-axis/architecture/x-axis.sysml'::XAxis::*;
import '../../modules/spindle/architecture/spindle.sysml'::Spindle::*;
```

From a nested sub-module importing a sibling:

```sysml
// modules/x-axis/modules/drive-belt/architecture/drive-belt.sysml
import '../../../architecture/x-axis.sysml'::XAxis::*;
```
