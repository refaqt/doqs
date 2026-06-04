> **Reference machine:** [Qarve](https://github.com/refaqt/qarve) · **Tools:** [DOQS](https://github.com/refaqt/doqs) submodule at `doqs/`. Examples may still say `cnc-mill` or `org` as generic placeholders.
# Documentation System — Open-Source CNC Milling Machine

## Philosophy

All project files are **text-first**. Binary files are used only where unavoidable (e.g., FreeCAD `.FCStd` files). Every text file must be readable, diffable, and editable by both humans and AI agents (Cursor, Claude Code, etc.). The project lives on GitHub, so everything must be Git-friendly.

Every **module** — from an individual manufactured part up to the complete machine — is treated as a potentially independent, publishable unit from the start. The folder structure is **identical at every nesting level**. The project root is itself a module.

---

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

---

## Folder Structure

Every module — at every nesting depth — uses the same set of first-level folders. The project root (`cnc-mill/`) and a leaf module (`modules/x-axis/modules/drive-belt/`) have identical structures; only their contents differ in scope.

### First-Level Folders (Every Module)

| Folder           | Contents                                                                                           |
| ---------------- | -------------------------------------------------------------------------------------------------- |
| `bom/`           | Bill of materials (CSV source data + processing script)                                            |
| `cad/`           | FreeCAD files: `assemblies/`, `parts/`, `exports/`, `params/` (model overrides)                    |
| `architecture/`  | SysML files — requirements, block definitions, **interfaces (ports)**                              |
| `docs/`          | Narrative prose only: dev-log, mistakes, decisions, prompts-log                                    |
| `manufacturing/` | Fabrication drawings, G-code, assembly guides                                                      |
| `modules/`       | Sub-modules (each with this same structure). Adapters live under `modules/adapters/` by convention |

**Special folders at the project root only:**

| Folder      | Contents                                                                    |
| ----------- | --------------------------------------------------------------------------- |
| `firmware/` | Software projects — see Firmware section                                    |
| `builds/`   | Lockfiles for physical machine instances — see Builds & Lockfiles section   |
| `graph/`    | Generated reverse-usage graph (`usage-graph.json`) — see Versioning section |
| `doqs/`     | Tools submodule (`github.com/refaqt/doqs`)                                     |

### Full Tree

```
cnc-mill/
│
├── okh.toml                         # Machine-level OKH manifest
├── README.md
├── LICENSE                          # e.g. CERN-OHL-S-2.0
├── CONTRIBUTING.md
├── CHANGELOG.md
├── .gitmodules
├── .gitattributes                   # Git LFS config
│
├── bom/                             # Top-level BOM (GENERATED from modules)
│   ├── bom.csv                      # Do not edit by hand
│   └── aggregate_bom.py
│
├── cad/                             # Top-level assembly CAD
│   ├── README.md                    # FreeCAD version, workbench, path config
│   ├── assemblies/
│   │   └── machine.FCStd            # Links to module parts via relative paths
│   └── exports/
│       ├── machine.step
│       └── machine.stl
│
├── architecture/                    # Top-level SysML
│   └── machine.sysml                # Imports from module architecture/ folders
│
├── docs/                            # Narrative documentation only
│   ├── dev-log/
│   │   └── YYYY-MM-DD_topic.md
│   ├── mistakes/
│   │   └── YYYY-MM-DD_topic.md
│   ├── decisions/
│   │   └── YYYY-MM-DD_topic.md
│   └── prompts-log/
│       └── YYYY-MM.md               # AI interaction log
│
├── manufacturing/
│   └── notes/
│       └── assembly-guide.md
│
├── modules/
│   └── x-axis/                      # ← identical structure at every depth
│       ├── okh.toml
│       ├── README.md
│       ├── LICENSE
│       │
│       ├── bom/
│       │   ├── bom.csv              # Source BOM for this module
│       │   └── process_bom.py
│       │
│       ├── cad/
│       │   ├── README.md
│       │   ├── params/
│       │   │   ├── default.csv     # Base parameter set (all keys)
│       │   │   ├── 500mm.csv       # Override file: only rows that differ from default
│       │   │   └── ballscrew.csv   # Another override
│       │   ├── params.csv          # ACTIVE model — generated by resolve_params.py
│       │   ├── resolve_params.py   # Merge default + override → params.csv
│       │   ├── sync_params.py      # Sync script: params.csv → FreeCAD Spreadsheet
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
│       │   ├── dev-log/
│       │   ├── mistakes/
│       │   └── decisions/
│       │
│       ├── manufacturing/
│       │   ├── drawings/
│       │   ├── cam/
│       │   └── notes/
│       │       └── assembly-guide.md
│       │
│       └── modules/                 # Nested sub-modules (same layout recursively)
│           └── drive-belt/
│               ├── okh.toml
│               ├── bom/
│               ├── cad/
│               ├── architecture/
│               ├── docs/
│               ├── manufacturing/
│               └── modules/
│
├── firmware/                        # See Firmware section
│   └── ...
│
├── builds/                          # Lockfiles for physical machine instances
│   ├── README.md
│   ├── example-baseline.toml        # Template for new builds
│   └── serial-0042/
│       ├── build.toml               # Pins exact version of every module
│       ├── notes.md                 # Non-standard modifications, history
│       └── photos/
│
├── graph/                           # Generated reverse-usage graph
│   └── usage-graph.json             # Built by doqs/scripts/build_graph.py
│
└── doqs/                            # Separate tools repo, included as submodule
    └── ...
```

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

---

## Versioning Across Dimensions

A hardware module exists along four independent axes simultaneously:

- **Versions** — incremental improvements over time (`v1.0` → `v1.1` → `v2.0`).
- **Models** — orthogonal configurations that coexist (e.g. 300 mm vs 500 mm travel, belt vs ball-screw drive). Different models all remain useful.
- **Stages** — technology / documentation readiness (OTRL/ODRL levels).
- **Parent relationships** — the same module is used by multiple parent assemblies, themselves at different versions/models/stages.

The naive interpretation says this gives `V × M × S × P` combinations. In practice the architecture below reduces this to a tractable set of artefacts: a small number of shared modules, each with a linear version history, composed in a few different ways, with explicit interfaces that decouple compatibility from version numbers.

### The Hardware Constraint: Install Base Never Dies

Software can deprecate v1 the moment v2 ships. Hardware cannot. A v1.0 machine sitting in a workshop is just as real and just as in-need-of-support as the v2.0 released yesterday. This imposes five constraints absent from pure software systems:

1. Old versions must remain documented, buildable, and maintainable indefinitely.
2. Compatibility between versions must be explicit and queryable — not a matter of memory.
3. Mixed-version configurations (`frame v1.0 + spindle v2.3`) are first-class: a real, supported state.
4. Adapter / transition modules are real engineering deliverables with their own version history.
5. Backporting (supplier substitutions, errata, manufacturing clarifications) is a normal operation across release lines.

### Mechanisms Summary

| Dimension                    | Mechanism                                                                                                                   |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Versions                     | Git tags (semver) per module repo, plus long-lived `release/vN.x` branches for LTS maintenance                              |
| Parametric models            | `cad/params/<model>.csv` override files merged onto `cad/params/default.csv`, declared as `[[model]]` entries in `okh.toml` |
| Structural models            | Separate thin composition modules (e.g. `modules/x-axis-belt/`, `modules/x-axis-ballscrew/`) sharing common sub-modules     |
| Stages                       | `technology-readiness-level` / `documentation-readiness-level` fields in `okh.toml` — no Git change                         |
| Parent tracking (forward)    | `[[hasComponent]]` in `okh.toml`                                                                                            |
| Parent tracking (reverse)    | `graph/usage-graph.json`, generated by `doqs/scripts/build_graph.py`                                                        |
| Cross-version compatibility  | Interface ports declared in SysML + mirrored in `okh.toml` as `[[provides-interface]]` / `[[consumes-interface]]`           |
| Mixed-version configurations | Lockfiles in `builds/<id>/build.toml` pinning each module to an exact version                                               |
| Cross-version bridging       | Adapter modules under `modules/adapters/`                                                                                   |

The remaining sections specify each mechanism in detail.

### Naming and versioning conventions

Module slugs, BOM part IDs, display-name lexicon, and version fields are defined in [naming.md](naming.md) and [naming-lexicon.md](naming-lexicon.md). Validators enforce them at build time:

- `doqs/scripts/check_names.py` — folder slugs, BOM `id` format (`PREFIX-NNN`), headers, model slugs, lexicon warnings
- `doqs/scripts/validate_okh.py` — semver in `version` (no `v` prefix); optional `--expected-version` before tagging
- `doqs/scripts/validate_all.py` — single command running all validation gates

**Version surfaces:** `okh.toml` `version` is authoritative; Git tags use a `v` prefix; lockfiles pin `vX.Y.Z`; FreeCAD `Comment` points to `okh.toml` without per-release bumps; drawing title blocks get `Rev: X.Y.Z` at export. See ADR [2026-06-04_naming-and-versioning.md](decisions/2026-06-04_naming-and-versioning.md).

### Versions: Tags + LTS Branches

Every module uses semver Git tags: `v1.0.0`, `v1.1.0`, `v2.0.0`. In addition, **each major version gets a long-lived branch** that never closes:

```
main                  ← active development; the next major version lives here
release/v2.x          ← LTS for the v2 line — backports of supplier subs, errata
release/v1.x          ← LTS for the v1 line — same, slower-moving
```

Patch releases on an LTS branch get tags too: `v1.0.1`, `v1.0.2`. These accumulate as the old version is maintained.

**What lands on release branches:**

- Documentation corrections / errata
- BOM supplier substitutions (sourcing only, no design change — see Equivalence Classes below)
- Manufacturing-process clarifications
- Critical safety fixes

**What does *not* land on release branches:**

- Design changes (those are new module versions on `main`)
- New features

This keeps every LTS branch monotonically *safer* over time and never riskier.

### Parametric Models: Override Files

For models that differ only in dimension values (300 mm vs 500 mm travel, M5 vs M6 fasteners), use sparse override files merged onto a base parameter set. The geometry — the `.FCStd` files — is shared across all models.

```
cad/
  params/
    default.csv     ← base, contains every alias
    300mm.csv       ← only rows that differ from default
    500mm.csv
    500mm-hd.csv    ← 500mm + heavier-duty rail
  params.csv        ← ACTIVE model — generated, do not edit by hand
  resolve_params.py ← merges default + override → params.csv
  sync_params.py    ← params.csv → FreeCAD (existing script)
```

Override files contain only deltas:

```csv
# cad/params/500mm.csv
alias,value,unit,description
rail_length,500,mm,Total length of X-axis linear rail (500 mm variant)
motor_offset,45,mm,Increased clearance for longer travel
```

Resolver script:

```python
# cad/resolve_params.py
"""Merge default + model override → active params.csv."""
import csv, sys
from pathlib import Path

def resolve(here: Path, model: str) -> None:
    default = {r["alias"]: r for r in csv.DictReader(open(here / "params" / "default.csv"))}
    if model != "default":
        override = csv.DictReader(open(here / "params" / f"{model}.csv"))
        for row in override:
            default[row["alias"]] = row
    rows = sorted(default.values(), key=lambda r: r["alias"])
    with open(here / "params.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["alias", "value", "unit", "description"])
        w.writeheader()
        w.writerows(rows)
    print(f"Resolved model '{model}' → {here / 'params.csv'} ({len(rows)} params)")

if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "default"
    resolve(Path(__file__).parent, model)
```

Declare available models in the module's `okh.toml`:

```toml
[[model]]
name        = "default"
description = "300 mm travel — standard variant"
params      = "cad/params/default.csv"

[[model]]
name        = "500mm"
description = "Extended travel variant"
params      = "cad/params/500mm.csv"

[[model]]
name        = "500mm-hd"
description = "Extended travel with heavy-duty rail"
params      = "cad/params/500mm-hd.csv"
```

**Propagation is automatic.** A fix to shared geometry propagates to all parametric models because they all use the same `.FCStd` files. Only the numbers differ.

### Structural Models: Composition, Not Branching

When two models differ architecturally — belt drive vs ball-screw drive, or 3-axis vs 5-axis — they are genuinely different module compositions. The correct response is **not** to branch the repo. It is to factor the shared parts out into shared sub-modules and let two thin composition modules combine them differently:

```
modules/
  x-axis/                    ← shared core: carriage, end plates, sensors, rails
    modules/
      drive-belt/            ← structural variant A (belt drive)
      drive-ballscrew/       ← structural variant B (ball-screw drive)

  x-axis-belt/               ← thin composition: x-axis + drive-belt
  x-axis-ballscrew/          ← thin composition: x-axis + drive-ballscrew
```

Each composition module is mostly just an `okh.toml`, an assembly `.FCStd` linking to the shared parts and one drive sub-module, and a thin assembly guide. Nearly everything substantial lives in the shared `x-axis/`.

**The rule:** if a fix needs to apply to both structural variants, the code being fixed almost certainly belongs in the shared parent module, not in the variant-specific folders. When you find yourself copy-pasting a fix across structural variants, that's the signal to extract the shared concern upward.

**Structural models are expensive** — each is a real module with its own BOM, CAD, and assembly guide. Keep them few. Before creating a new structural variant, ask whether a parameter can absorb the variation instead.

### Stages: Metadata Only

TRL stages are a property of a module at a point in time, not a fork. Use existing OKH fields:

```toml
technology-readiness-level   = "OTRL-4"
documentation-readiness-level = "ODRL-3"
```

A design that moves from OTRL-3 to OTRL-4 is still the same design — it just gets a new version tag and an updated field. No branching is needed for stages.

The one case where stages affect Git structure: if you maintain a stable "production" version and an experimental "next" version simultaneously, that's already covered by `main` / `release/vN.x`.

### Parent Relationships: Reverse Usage Graph

The forward edge (parent → child) is already in `[[hasComponent]]`. The reverse edge (child → parents) is generated at the project root as `graph/usage-graph.json`:

```json
{
  "modules/x-axis": {
    "current_version": "v1.2.0",
    "trl": "OTRL-4",
    "used_by": [
      { "path": ".", "version": "v1.2.0" },
      { "path": "https://github.com/org/other-machine", "version": "v1.1.0" }
    ],
    "used_by_builds": ["builds/serial-0042", "builds/serial-0091"]
  },
  "modules/x-axis/modules/drive-belt": {
    "current_version": "v0.3.1",
    "trl": "OTRL-3",
    "used_by": [{ "path": "modules/x-axis-belt", "version": "v0.3.1" }],
    "used_by_builds": ["builds/serial-0042"]
  }
}
```

Generator (`doqs/scripts/build_graph.py`) walks all `okh.toml` files plus every lockfile under `builds/`, inverting the edges. It also reads `known-consumers.toml` at the project root for external repos that consume this project's modules.

This gives you queryable provenance: "if I change `drive-belt v0.3.1`, who is affected?" The answer is a finite list of parent modules and physical builds — easy to enumerate, easy to notify.

---

## Interfaces

Compatibility between modules is governed by **interfaces, versioned independently of the modules that implement them**. A module declares the interfaces it provides and consumes. Two modules can connect iff the interface names and versions match.

This is the key mechanism that prevents the install-base problem from exploding into a quadratic compatibility matrix. A breaking change to mounting holes bumps the interface major version. Module versions then evolve on their own schedule. Frame `v1.7` still provides `FrameMountInterface v1`, so it still accepts any x-axis that consumes `FrameMountInterface v1` — regardless of how many x-axis versions have shipped since.

### Interface Definitions in SysML

Interfaces live as `port def` blocks in the providing module's SysML file, with their version embedded in the name:

```sysml
// modules/frame/architecture/frame.sysml
package Frame {

    // Mechanical mounting interface — v1
    port def FrameMountInterface_v1 {
        doc /* 4× M6 holes on 80×120 mm pattern, top surface */
        attribute hole_pattern : String = "M6x4, 80x120 grid";
        attribute load_kg      : Real   = 50.0;
    }

    // Mechanical mounting interface — v2 (incompatible with v1)
    port def FrameMountInterface_v2 {
        doc /* 6× M8 holes on 100×150 mm pattern, top surface */
        attribute hole_pattern : String = "M8x6, 100x150 grid";
        attribute load_kg      : Real   = 120.0;
    }

    part def Frame_v1 {
        port mount : FrameMountInterface_v1;   // provides v1
    }

    part def Frame_v2 {
        port mount : FrameMountInterface_v2;   // provides v2
    }
}
```

Consuming modules import and reference the interface:

```sysml
// modules/x-axis/architecture/x-axis.sysml
import '../../frame/architecture/frame.sysml'::Frame::FrameMountInterface_v1;

part def XAxis_v1 {
    port mount : ~FrameMountInterface_v1;  // consumes v1
}
```

### Interface Declarations in OKH

Mirror the SysML interfaces as machine-readable entries in `okh.toml`, so tools that don't parse SysML can still validate compatibility:

```toml
# modules/frame/okh.toml
[[provides-interface]]
name        = "FrameMountInterface"
version     = "1.0"
description = "4× M6 holes on 80×120 grid, top mounting surface"

[[provides-interface]]
name        = "FrameMountInterface"
version     = "2.0"
description = "6× M8 holes on 100×150 grid, top mounting surface"
```

```toml
# modules/x-axis/okh.toml
[[consumes-interface]]
name    = "FrameMountInterface"
version = "1.0"
```

Versions follow semver: `1.0` and `1.1` are compatible (minor change adds optional features), `1.0` and `2.0` are not. The validator treats them accordingly.

### Adapter Modules

When a breaking interface change occurs, the bridge between old and new is itself a module. Adapter modules live under `modules/adapters/` and have the same internal structure as any other module — `bom/`, `cad/`, `architecture/`, etc. — but their function is explicitly to translate between interface versions.

```
modules/adapters/
  spindle-mount-v1-to-v2/
    okh.toml
    bom/
    cad/
    architecture/      ← provides v1 interface, consumes v2 interface
    docs/
    manufacturing/
```

In its `okh.toml`:

```toml
name     = "Spindle Mount v1→v2 Adapter"
function = "Allows v2.x spindles (which consume SpindleMountInterface v2) to mount to v1.x frames (which provide SpindleMountInterface v1)."

[[provides-interface]]
name    = "SpindleMountInterface"
version = "1.0"

[[consumes-interface]]
name    = "SpindleMountInterface"
version = "2.0"
```

Because adapters expose their interface mappings in the same format as any other module, the compatibility validator handles them with no special logic. They just appear in the dependency graph as nodes that happen to translate.

This also gives a discoverable upgrade-path catalogue. Anyone planning an upgrade of a deployed machine browses `modules/adapters/` and sees exactly which transitions are supported.

---

## Builds & Lockfiles

A `builds/` directory at the project root represents real machine instances. Each subdirectory is one physical build: a shipped customer machine, a prototype, a workshop instance. The lockfile inside pins the exact version of every constituent module.

This is analogous to `Cargo.lock` or `package-lock.json` in software, but with longer life expectancy — physical machines may outlive several major versions of the design.

### Directory Layout

```
builds/
  README.md                      # What this folder is, how to make a new build
  example-baseline.toml          # Template for new builds
  serial-0042/
    build.toml                   # Pins exact version of every module
    notes.md                     # History of changes, non-standard modifications
    photos/
      delivery-state.jpg
      2026-01-spindle-upgrade.jpg
  serial-0091/
    build.toml
    notes.md
```

### Lockfile Format

```toml
# builds/serial-0042/build.toml
schema       = "doqs-build-v1"
machine      = "cnc-mill"
built-date   = "2025-03-15"
owner        = "Workshop X"
location     = "Antwerp, BE"

# Pin the top-level machine version this build is based on
[base]
repo    = "https://github.com/refaqt/qarve"
version = "v1.0.0"

# Pin every module individually — these can deviate from the base
[[module]]
path    = "modules/frame"
version = "v1.0.0"

[[module]]
path    = "modules/x-axis"
version = "v1.2.1"           # upgraded from v1.0.0 in 2025-04
model   = "default"          # selects which parametric model

[[module]]
path    = "modules/spindle"
version = "v2.3.0"           # upgraded across major version in 2026-01
adapter = "modules/adapters/spindle-mount-v1-to-v2@v1.0.0"

# Free-form modifications that don't fit the model system
[[modification]]
date        = "2025-08-22"
description = "Replaced X20 limit switch with X25 (X20 EOL)"
bom-impact  = "SW-01: supplier_1_pn changed Omron X20-1 → Omron X25-1"

[[modification]]
date        = "2026-01-15"
description = "Spindle v1 → v2 upgrade; adapter installed"
```

The lockfile serves three purposes:

1. **Reproducibility** — anyone can rebuild this exact machine by checking out the pinned versions.
2. **Support** — when serial-0042 reports a problem, the maintainer knows precisely what's installed.
3. **Validation** — the compatibility validator checks that the pinned combination is interface-consistent (and that any required adapters are present).

### Customer Builds

For users assembling their own machine, `builds/example-baseline.toml` is the starting template. They copy it to their own `builds/<their-id>/build.toml` and either keep it private or contribute it back. A contributed build expands the project's known install base and gives downstream maintainers visibility into what's deployed.

External organisations running their own forks should keep their lockfiles in their own repos, but may list themselves in the parent's `known-consumers.toml` so they appear in the reverse usage graph.

### Validator (`doqs/scripts/validate_build.py`)

```python
"""Validate that a build.toml represents an interface-compatible composition."""
from pathlib import Path
import tomllib

def load_module_manifest(root: Path, mod_entry: dict) -> dict:
    # In a full implementation this would resolve the version (git checkout
    # at the tag) and read okh.toml from that snapshot. For brevity, here we
    # just read from the working tree.
    mod_path = root / mod_entry["path"] / "okh.toml"
    with open(mod_path, "rb") as f:
        return tomllib.load(f)

def collect_interfaces(modules: list[dict]) -> tuple[dict, list]:
    """Return (provided, consumed) maps keyed by (name, major_version)."""
    provided, consumed = {}, []
    for m in modules:
        for iface in m["manifest"].get("provides-interface", []):
            key = (iface["name"], iface["version"].split(".")[0])
            provided.setdefault(key, []).append(m["path"])
        for iface in m["manifest"].get("consumes-interface", []):
            key = (iface["name"], iface["version"].split(".")[0])
            consumed.append({"interface": key, "by": m["path"]})
    return provided, consumed

def validate(build_path: Path, repo_root: Path) -> list[str]:
    errors = []
    with open(build_path, "rb") as f:
        build = tomllib.load(f)

    modules = []
    for entry in build.get("module", []):
        modules.append({
            "path": entry["path"],
            "version": entry["version"],
            "manifest": load_module_manifest(repo_root, entry),
        })
    # Adapters listed inline on module entries are also part of the build
    for entry in build.get("module", []):
        if "adapter" in entry:
            adapter_path = entry["adapter"].split("@")[0]
            modules.append({
                "path": adapter_path,
                "version": entry["adapter"].split("@")[1],
                "manifest": load_module_manifest(
                    repo_root, {"path": adapter_path}),
            })

    provided, consumed = collect_interfaces(modules)
    for need in consumed:
        if need["interface"] not in provided:
            errors.append(
                f"Unsatisfied interface {need['interface']} required by "
                f"{need['by']} — no module in this build provides it")
    return errors

if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    all_ok = True
    for build_file in sorted((repo_root / "builds").rglob("build.toml")):
        errs = validate(build_file, repo_root)
        rel = build_file.relative_to(repo_root)
        if errs:
            all_ok = False
            print(f"FAIL  {rel}")
            for e in errs: print(f"      {e}")
        else:
            print(f"ok    {rel}")
    raise SystemExit(0 if all_ok else 1)
```

Run this in CI on every commit. When a new module version is published, CI immediately identifies which historical builds remain consistent and which need attention (an adapter, a backport, or explicit documentation of incompatibility).

---

## Requirements

**Formal requirements live exclusively in SysML** as `requirement def` blocks in each module's `architecture/` folder. There is no separate requirements document. This avoids duplication and drift between documentation and the system model.

Stakeholder-facing prose (what the machine should do, for whom, under what conditions) goes in `README.md` or `docs/` as context, but is not the authoritative source.

```sysml
// architecture/machine.sysml — system-level requirements
package CNCMachineRequirements {

    requirement def WorkEnvelope {
        doc /* The machine shall provide a work envelope of at least 300 × 200 × 150 mm */
        attribute x_mm : Real; attribute y_mm : Real; attribute z_mm : Real;
        require constraint { x_mm >= 300.0 and y_mm >= 200.0 and z_mm >= 150.0 }
    }

    requirement def PositioningAccuracy {
        doc /* Repeatability shall be ≤ 0.05 mm on all axes */
        attribute repeatability_mm : Real;
        require constraint { repeatability_mm <= 0.05 }
    }
}
```

Module-level requirements live in `modules/x-axis/architecture/x-axis.sysml` and are imported and verified at the machine level.

---

## OKH Manifests (Open Know-How)

This project uses **OKH-LOSHv1.0** (TOML format), the active successor to OKH v1, maintained at `github.com/iop-alliance/OpenKnowHow`. File name is always `okh.toml` at the root of each module folder.

### Key concepts

- `[[hasComponent]]` — links to a sub-module that has its own `okh.toml` (referenced by URL)
- `[[part]]` — defines an individually manufactured part **inline** in the current manifest
- `tsdc` — fabrication process tag: `MEC` (CNC milling), `3DP`, `WJ` (water-jet), `ASM` (assembly)

### Machine-Level Manifest (`okh.toml`)

```toml
okhv = "OKH-LOSHv1.0"

name = "CNC Milling Machine"
repo = "https://github.com/refaqt/qarve"
version = "0.1.0"
release = "https://github.com/refaqt/qarve/releases/tag/v0.1.0"
license = "CERN-OHL-S-2.0"
licensor = ["Your Name"]
organisation = "Your Organisation"

readme = "README.md"
image = ["docs/assets/machine.jpg"]
documentation-language = ["en"]

technology-readiness-level = "OTRL-3"
documentation-readiness-level = "ODRL-3"

function = """
Open-source 3-axis CNC milling machine for small-batch production of
aluminium and wood parts.
"""

cpc-patent-class = "B23C 1/00"
bom = "bom/bom.csv"
manufacturing-instructions = ["manufacturing/notes/assembly-guide.md"]
source = ["cad/assemblies/machine.FCStd"]
export = ["cad/exports/machine.step", "cad/exports/machine.stl"]

[[hasComponent]]
component = "https://github.com/refaqt/qarve/blob/main/modules/x-axis/okh.toml"

[[hasComponent]]
component = "https://github.com/refaqt/qarve/blob/main/modules/y-axis/okh.toml"

[[hasComponent]]
component = "https://github.com/refaqt/qarve/blob/main/modules/spindle/okh.toml"

[[hasComponent]]
component = "https://github.com/refaqt/qarve/blob/main/modules/frame/okh.toml"
```

### Module-Level Manifest (`modules/x-axis/okh.toml`)

```toml
okhv = "OKH-LOSHv1.0"

name = "X-Axis Module"
repo = "https://github.com/refaqt/qarve/tree/main/modules/x-axis"
version = "0.1.0"
release = "https://github.com/refaqt/qarve/releases/tag/v0.1.0"
license = "CERN-OHL-S-2.0"
licensor = ["Your Name"]

readme = "README.md"
image = ["docs/assets/x-axis.jpg"]
documentation-language = ["en"]

technology-readiness-level = "OTRL-3"
documentation-readiness-level = "ODRL-3"

function = """
Linear motion axis providing X-direction travel via GT2 belt drive on
15mm linear rails.
"""

tsdc = "ASM"
bom = "bom/bom.csv"
manufacturing-instructions = ["manufacturing/notes/assembly-guide.md"]
source = ["cad/assemblies/x-axis.FCStd"]
export = ["cad/exports/x-axis.step", "cad/exports/x-axis.stl"]

# Parametric models — see Versioning section
[[model]]
name        = "default"
description = "300 mm travel — standard variant"
params      = "cad/params/default.csv"

[[model]]
name        = "500mm"
description = "Extended travel variant"
params      = "cad/params/500mm.csv"

# Interfaces this module exposes and requires — see Interfaces section
[[provides-interface]]
name        = "XAxisOutputInterface"
version     = "1.0"
description = "Carriage mounting face for tools / spindle stack"

[[consumes-interface]]
name        = "FrameMountInterface"
version     = "1.0"
description = "Mounts onto frame top surface"

# Nested sub-module with its own manifest
[[hasComponent]]
component = "https://github.com/refaqt/qarve/blob/main/modules/x-axis/modules/drive-belt/okh.toml"

# Individually manufactured parts — defined inline
[[part]]
name = "Carriage Plate"
image = ["cad/parts/carriage/image.jpg"]
source = ["cad/parts/carriage/carriage.FCStd"]
export = [
  "cad/parts/carriage/exports/carriage.step",
  "cad/parts/carriage/exports/carriage.dxf",
  "cad/parts/carriage/exports/carriage.stl",
]
material = "6061-T6 aluminium"
mass = 320.0
tsdc = "WJ"

[part.outer-dimensions]
openSCAD = "cube(size = [200, 80, 8])"
unit = "mm"

[[part]]
name = "Motor Mount Bracket"
source = ["cad/parts/motor-mount/motor-mount.FCStd"]
export = [
  "cad/parts/motor-mount/exports/motor-mount.step",
  "cad/parts/motor-mount/exports/motor-mount.dxf",
  "cad/parts/motor-mount/exports/motor-mount.stl",
]
material = "6061-T6 aluminium"
mass = 85.0
tsdc = "MEC"
```

When a module is extracted to its own repo, update its `repo` field and the `[[hasComponent]]` URL in the parent manifest.

### Validation Script (`doqs/scripts/validate_okh.py`)

```python
from pathlib import Path
import tomllib  # Python 3.11+

REQUIRED = ["okhv", "name", "repo", "version", "license", "licensor", "function"]

def validate(p: Path) -> list[str]:
    errors = []
    with open(p, "rb") as f:
        data = tomllib.load(f)
    for field in REQUIRED:
        if field not in data:
            errors.append(f"Missing: {field}")
    for key in ("bom", "readme"):
        if key in data:
            ref = p.parent / data[key]
            if not ref.exists():
                errors.append(f"{key} not found: {data[key]}")
    for item in data.get("source", []) + data.get("export", []):
        if not (p.parent / item).exists():
            errors.append(f"File not found: {item}")
    for instr in data.get("manufacturing-instructions", []):
        if not (p.parent / instr).exists():
            errors.append(f"manufacturing-instructions not found: {instr}")
    # Model param files must exist
    for model in data.get("model", []):
        if "params" in model:
            if not (p.parent / model["params"]).exists():
                errors.append(f"model '{model.get('name','?')}' "
                              f"params not found: {model['params']}")
    # Interfaces must declare name and version
    for iface in data.get("provides-interface", []) + data.get("consumes-interface", []):
        if "name" not in iface or "version" not in iface:
            errors.append(f"Interface missing name or version: {iface}")
    return errors

if __name__ == "__main__":
    root = Path(__file__).parent.parent
    all_ok = True
    for manifest in sorted(root.rglob("okh.toml")):
        if "doqs" in manifest.relative_to(root).parts:
            continue
        errors = validate(manifest)
        rel = manifest.relative_to(root)
        if errors:
            all_ok = False
            print(f"FAIL  {rel}")
            for e in errors: print(f"      {e}")
        else:
            print(f"ok    {rel}")
    raise SystemExit(0 if all_ok else 1)
```

Related validators (documented in their own sections):

- `doqs/scripts/check_names.py` — module slugs, BOM ids, model slugs, naming lexicon ([naming.md](naming.md)).
- `doqs/scripts/validate_all.py` — runs `validate_okh`, `check_names`, `check_links`, and `validate_build` in sequence.
- `doqs/scripts/validate_build.py` — checks that lockfiles in `builds/` represent interface-consistent compositions.
- `doqs/scripts/build_graph.py` — regenerates `graph/usage-graph.json` from all manifests and lockfiles (generator, not a gate).

---

## Linking CSV Parameters to FreeCAD

The FreeCAD Spreadsheet workbench can drive model dimensions through **cell aliases** referenced in sketch constraints via expressions (e.g., a sketch constraint reads `Params.rail_length`). This means parameter values can be managed as plain text in a `params.csv` file and synced into FreeCAD programmatically.

### Data Flow

```
cad/params/default.csv      ← base parameter set (every alias appears here)
cad/params/<model>.csv      ← sparse override file: only rows that differ
     │
     │  cad/resolve_params.py <model>   (selects active model)
     ▼
cad/params.csv              ← ACTIVE model — generated, do not edit by hand
     │
     │  cad/sync_params.py  (run via FreeCAD Python)
     ▼
FreeCAD Spreadsheet (Params)
     │
     │  FreeCAD expressions in sketch constraints
     ▼
Model geometry (rail_length, carriage_thickness, motor_offset, …)
```

If a module has only one model, `cad/params/default.csv` is the only file in `cad/params/` and `cad/params.csv` is just a copy of it. The resolver step is still run for consistency.

SysML `attribute` values document the design intent. The `default.csv` parameter file contains the authoritative numeric values for the canonical model. Both should be kept consistent; a validation script can check that every attribute mentioned in `architecture/*.sysml` has a corresponding row in `default.csv`.

### Parameter File Format

The format is the same for `default.csv` and any model override file:

```
alias,value,unit,description
rail_length,400,mm,Total length of X-axis linear rail
carriage_thickness,8,mm,Carriage plate thickness
motor_offset,35,mm,Distance from rail end to motor shaft centre
belt_pitch,2,mm,GT2 belt tooth pitch
pulley_teeth,20,,Number of teeth on motor pulley
```

- `default.csv` must include **every** alias used by the FreeCAD Spreadsheet.
- A model override file (e.g. `500mm.csv`) includes **only the rows that differ** from `default.csv`. Aliases not present in the override inherit from `default.csv`.
- `alias` must match the alias assigned to the corresponding FreeCAD Spreadsheet cell.
- `unit` may be empty for dimensionless values.
- All param files are committed to Git — diffs show parameter changes clearly.
- The active `cad/params.csv` is **generated** by `resolve_params.py` and is `.gitignore`d.

### `cad/sync_params.py` — Sync Script

This script is run **from within FreeCAD** (via the built-in Python console or as a macro), or headlessly via the FreeCAD command line.

```python
"""
Sync params.csv into the FreeCAD Spreadsheet named 'Params'.

Usage (FreeCAD Python console):
    exec(open("cad/sync_params.py").read())

Usage (headless, from the module's root folder):
    FreeCAD cad/assemblies/x-axis.FCStd cad/sync_params.py
"""

import csv
from pathlib import Path

def sync_params(doc=None, csv_path=None):
    import FreeCAD  # only available inside FreeCAD runtime

    if doc is None:
        doc = FreeCAD.ActiveDocument
    if doc is None:
        raise RuntimeError("No active FreeCAD document.")

    sheet = doc.getObjectsByLabel("Params")
    if not sheet:
        raise RuntimeError("No Spreadsheet named 'Params' in document.")
    sheet = sheet[0]

    here = Path(__file__).parent
    csv_path = csv_path or (here / "params.csv")

    updated = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            alias = row["alias"].strip()
            value = row["value"].strip()
            unit  = row.get("unit", "").strip()
            cell_value = f"{value} {unit}".strip() if unit else value
            sheet.set(alias, cell_value)
            updated.append(alias)

    doc.recompute()
    doc.save()
    print(f"Synced {len(updated)} parameters: {', '.join(updated)}")

sync_params()
```

### Setting Up Aliases in FreeCAD

Before the sync script can work, each cell in the Spreadsheet must have its alias set once manually:

1. Open the `.FCStd` file in FreeCAD.
2. Open the Spreadsheet workbench, add a row for each parameter.
3. Right-click each value cell → *Properties* → *Alias* → enter the alias (matching the `alias` column in `params.csv`).
4. In each sketch constraint, click the expression icon and enter `Params.alias_name`.

This setup is one-time. After that, all parameter updates go through `params.csv` + `sync_params.py`.

### Export Params to CSV (Reverse Direction)

To pull the current spreadsheet values back into `params.csv` (for documentation or when parameters were changed interactively in FreeCAD):

```python
"""Add to sync_params.py or run separately."""

def export_params(doc=None, csv_path=None):
    import FreeCAD, csv as csv_mod
    if doc is None:
        doc = FreeCAD.ActiveDocument
    sheet = doc.getObjectsByLabel("Params")[0]

    here = Path(__file__).parent
    csv_path = csv_path or (here / "params.csv")

    # Read existing rows to preserve descriptions
    existing = {}
    with open(csv_path, newline="") as f:
        for row in csv_mod.DictReader(f):
            existing[row["alias"]] = row

    # Get current values from spreadsheet
    props = [p for p in dir(sheet) if not p.startswith("_")]
    rows = []
    for alias in props:
        try:
            val = getattr(sheet, alias)
            if isinstance(val, (int, float)):
                desc = existing.get(alias, {}).get("description", "")
                unit = existing.get(alias, {}).get("unit", "")
                rows.append({"alias": alias, "value": val, "unit": unit,
                             "description": desc})
        except Exception:
            pass

    rows.sort(key=lambda r: r["alias"])
    with open(csv_path, "w", newline="") as f:
        w = csv_mod.DictWriter(f, fieldnames=["alias","value","unit","description"])
        w.writeheader()
        w.writerows(rows)
    print(f"Exported {len(rows)} parameters to {csv_path}")
```

---

## Firmware

Firmware is a software project and follows a software project structure. Each target (motion controller board, pendant display, etc.) is its own sub-project. Firmware will eventually be extracted into its own repo, following the same submodule pattern as hardware modules.

```
firmware/
│
├── README.md                    # Overview: what boards, how to build, how to flash
│
└── motion-controller/           # One folder per firmware target
    ├── README.md                # Target-specific: board, toolchain, flashing
    ├── platformio.ini           # Build system config (PlatformIO)
    │   # -- or CMakeLists.txt for CMake-based projects
    ├── src/
    │   └── main.cpp             # Entry point
    ├── include/
    │   └── config.h             # Compile-time constants
    ├── lib/                     # Local libraries / vendor code
    ├── tests/                   # Unit tests (e.g. Unity, GoogleTest)
    │   └── test_kinematics.cpp
    ├── config/
    │   └── machine.json         # Runtime machine config: speeds, limits, steps/mm
    └── docs/
        ├── dev-log/
        └── decisions/
```

**Config vs. compile-time constants:**

- `config/machine.json` — machine-specific runtime parameters (steps per mm, max speed, homing offsets). Committed to Git; differs between machines. AI-editable.
- `include/config.h` — compile-time constants that don't change between machines.

**When to extract firmware to its own repo:**
Apply the same test as hardware modules: when the firmware is stable enough to reuse in another machine project. Use `git subtree split --prefix=firmware/motion-controller` and the same submodule pattern.

---

## File Format Guidelines

### Markdown (`.md`) — Narrative Documentation

Used for: dev log, mistakes log, decisions, README files, assembly guides.

**Dev log entry** (`doqs/templates/dev-log-entry.md`):

```markdown
# YYYY-MM-DD — Topic Title

## Goal
## Work Done
## Decisions Made
## Open Questions
- [ ]
## Next Steps
- [ ]
```

**ADR template** (`doqs/templates/adr.md`):

```markdown
# ADR-NNN — Title
- **Date:** YYYY-MM-DD
- **Status:** Proposed | Accepted | Deprecated | Superseded by ADR-NNN
## Context
## Decision
## Consequences
```

**Mistakes log entry** (`doqs/templates/mistake-entry.md`):

```markdown
# YYYY-MM-DD — Short Description
## What Happened
## Why It Happened
## Consequence
## How to Avoid It
## Related Files / Commits
```

### TOML (`.toml`) — OKH Manifests

- File name always `okh.toml`, at the root of the module folder.
- Validate with `doqs/scripts/validate_okh.py` before committing.

### JSON (`.json`) — Structured Config and Data

Used for: firmware runtime config, structured data for programmatic use.

**Rules:** 2-space indentation, `snake_case` keys, never minified, validated against JSON Schema in `doqs/schemas/`.

### CSV (`.csv`) — Tabular Data

Used for: BOM, parameter tables, measurement data.

**BOM column convention:**

```
id,name,spec,category,qty,unit,unit_cost_eur,unit_mass_g,equiv_class,
supplier_1,supplier_1_pn,
supplier_2,supplier_2_pn,
supplier_3,supplier_3_pn,
notes
```

Supplier columns 2 and 3 may be empty but must always be present.

**Equivalence classes for LTS sourcing.** The `spec` column describes what the design requires (e.g. `"SPDT 5A lever microswitch"`). The `equiv_class` column tags interchangeable parts with a short identifier (e.g. `SPDT-5A-LEVER`). When a supplier part goes EOL, an updated `bom.csv` on a `release/vN.x` branch substitutes another part in the same `equiv_class` — no design change, only sourcing. This separates *part specification* (lives forever, defined by the design) from *part instance* (evolves with the market, refreshed on LTS branches).

Example row:

```
SW-001,Limit Switch,"SPDT 5A lever",electrical,4,pc,3.20,18,SPDT-5A-LEVER,Omron,X20-1,Honeywell,V7-2,Generic,LM-9,
```

**Parameter table convention** (`cad/params/default.csv` plus optional `cad/params/<model>.csv` overrides):

```
alias,value,unit,description
```

The `alias` must match the FreeCAD Spreadsheet cell alias exactly. See the *Linking CSV Parameters to FreeCAD* section for the model-override workflow.

**Processing script** (`bom/process_bom.py`):

```python
import csv
from pathlib import Path

def load_bom(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

def render_markdown(bom: list[dict], out_path: Path) -> None:
    header = "| ID | Name | Qty | Unit Cost (€) | Total (€) | Primary Supplier |"
    sep    = "|----|------|-----|--------------|-----------|-----------------|"
    lines  = ["# Bill of Materials\n", header, sep]
    for r in bom:
        total = float(r["unit_cost_eur"]) * int(r["qty"])
        lines.append(f"| {r['id']} | {r['name']} | {r['qty']} | "
                     f"{r['unit_cost_eur']} | {total:.2f} | {r['supplier_1']} |")
    total = sum(float(r["unit_cost_eur"]) * int(r["qty"]) for r in bom)
    lines.append(f"\n**Grand Total: €{total:.2f}**")
    out_path.write_text("\n".join(lines))

if __name__ == "__main__":
    here = Path(__file__).parent
    bom = load_bom(here / "bom.csv")
    render_markdown(bom, here / "bom_output.md")
```

**Aggregation script** (`bom/aggregate_bom.py` at project root):

```python
from pathlib import Path
import csv

def aggregate(root: Path, out_path: Path):
    rows = []
    for bom_file in sorted(root.rglob("bom/bom.csv")):
        if bom_file == out_path:
            continue
        module = bom_file.relative_to(root).parts[0]  # e.g. "modules"
        with open(bom_file, newline="") as f:
            for row in csv.DictReader(f):
                row["module"] = str(bom_file.parent.parent.relative_to(root))
                rows.append(row)
    if not rows:
        return
    fieldnames = ["module"] + [k for k in rows[0] if k != "module"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

if __name__ == "__main__":
    root = Path(__file__).parent.parent
    aggregate(root, root / "bom" / "bom.csv")
```

### SysML (`.sysml`) — System Architecture and Requirements

Used for: block definitions, requirements, interfaces, state machines, part properties. This is the authoritative source for requirements — there are no separate requirements documents.

**Free tooling:**

| Tool                                                                                               | Notes                                 |
| -------------------------------------------------------------------------------------------------- | ------------------------------------- |
| [SysIDE](https://github.com/sensmetry/sysml-2ls)                                                   | VS Code extension — best free option  |
| [SysML v2 Pilot Implementation](https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation) | Eclipse IDE, official reference       |
| Cursor / Claude Code                                                                               | Plain text, no special tooling needed |

**Module-level SysML** (`modules/x-axis/architecture/x-axis.sysml`):

```sysml
package XAxis {

    // Requirements
    requirement def TravelRequirement {
        doc /* X-axis travel shall be ≥ 300 mm */
        attribute travel_mm : Real;
        require constraint { travel_mm >= 300.0 }
    }

    // Interface ports — versioned independently of the module itself.
    // The version is embedded in the port name.
    port def FrameMountInterface_v1 {
        doc /* 4× M6 holes on 80×120 mm pattern, top surface */
    }

    port def XAxisOutputInterface_v1 {
        doc /* Tool/spindle mounting face on the carriage */
    }

    // Block definitions — authoritative part properties
    part def CarriagePlate {
        attribute material          : String = "6061-T6 aluminium";
        attribute thickness_mm      : Real   = 8.0;
        attribute surface_treatment : String = "anodised";
    }

    part def LinearAxis {
        attribute travel_mm         : Real;
        attribute max_speed_mm_s    : Real;
        attribute repeatability_mm  : Real;
        part carriage : CarriagePlate;

        // This module consumes the frame interface and provides the carriage interface
        port mount_to_frame : ~FrameMountInterface_v1;
        port carriage_face  : XAxisOutputInterface_v1;
    }
}
```

**Top-level SysML** (`architecture/machine.sysml`):

```sysml
import '../../modules/x-axis/architecture/x-axis.sysml'::XAxis::*;
import '../../modules/spindle/architecture/spindle.sysml'::Spindle::*;

package CNCMachine {
    part def Machine {
        part xAxis   : LinearAxis;
        part yAxis   : LinearAxis;
        part zAxis   : LinearAxis;
        part spindle : SpindleAssembly;
    }

    requirement def WorkEnvelope {
        doc /* Work envelope ≥ 300 × 200 × 150 mm */
    }
}
```

### CAD Files (FreeCAD v1.1, built-in Assembly workbench)

**Relative path setup:**
Before creating any cross-file links, enable:
`Edit → Preferences → General → Document → Use relative paths when saving external links (linked objects)`

With this setting, `App::Link` objects store relative paths. The path from `cad/assemblies/machine.FCStd` to a module part is `../../modules/x-axis/cad/parts/carriage/carriage.FCStd`. In Mode B, the submodule sits at the same path — no links break.

**Git LFS — set up once per repo before first binary commit:**

```bash
git lfs install
git lfs track "*.FCStd"
git lfs track "*.stl"
git add .gitattributes
git commit -m "chore: configure Git LFS"
```

`.gitattributes`:

```
*.FCStd filter=lfs diff=lfs merge=lfs -text
*.stl   filter=lfs diff=lfs merge=lfs -text
```

LFS must be configured in each extracted module repo individually.

**Exports after significant changes:** `.step` (geometry interchange), `.dxf` (2D drawings), `.stl` (GitHub 3D browser preview). Commit alongside the `.FCStd`.

---

## AI Agent Workflow (Cursor / Claude Code)

### Prompts Log

Add to `.cursorrules` (Cursor) or `AGENTS.md` (Claude Code) at the project root:

```markdown
## Logging Rule

After completing any task, append an entry to
`docs/prompts-log/YYYY-MM.md` (use the current year-month).

Format:
---
### HH:MM — Short task title

**Prompt:** "..."

**Actions:**
- ...

**Files changed:**
- `path/to/file` — created / modified / deleted

**Outcome:** One sentence.
---
```

### General Patterns

1. **Point the agent at specific files.** e.g.: *"Look at `modules/x-axis/bom/bom.csv` and generate `[[part]]` entries using `doqs/templates/okh-module-with-parts.toml`."*
2. **Use JSON or CSV for agent output.** Validate against the schema, then commit.
3. **Never ask the agent to edit `.FCStd` files.** Geometry changes happen in FreeCAD manually.
4. **After OKH generation**, run `doqs/scripts/validate_okh.py`.
5. **After param changes**, run `cad/sync_params.py` inside FreeCAD.

---

## Git & GitHub Conventions

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>
```

Types: `feat`, `fix`, `docs`, `cad`, `arch`, `okh`, `firmware`, `chore`, `refactor`, `interface`, `model`, `build`

```
docs(dev-log): 2025-06-10 Z-axis bearing selection
cad(x-axis): update carriage plate to 8mm thickness
arch(x-axis): add TravelRequirement in SysML
okh(x-axis): add [[part]] entries for carriage and motor mount
firmware(controller): add homing sequence
params(x-axis): increase rail_length to 420mm
interface(frame): bump FrameMountInterface to v2.0 (breaking)
model(x-axis): add 500mm-hd model override
build(serial-0042): record spindle v2.3.0 upgrade with adapter
```

### Branch Strategy

```
main                   → active development for the next major version
dev                    → integration branch (optional, for short-lived integration)
feature/xxx            → subsystem or feature work, branched from main

release/v1.x           → long-term-support branch for the v1.x line
release/v2.x           → long-term-support branch for the v2.x line
```

**Release branches are permanent.** Every major version (v1.x, v2.x, …) gets its own `release/vN.x` branch that lives indefinitely. These exist to support the install base — physical machines built against that major version remain serviceable through their LTS branch.

**Patch tags live on release branches.** A v1.0 user reports a bug in step 17 of the assembly guide → the fix lands on `release/v1.x` and gets tagged `v1.0.1`. The same fix may be cherry-picked to `release/v2.x` if applicable, and may already be present on `main`.

### Backporting to Release Branches

Standard backport flow:

```bash
# Fix lands on main as part of normal development:
git checkout main
# … make and commit the fix …
git log -1 --format=%H            # capture commit hash, say abc123

# Backport to the v2 LTS line:
git checkout release/v2.x
git cherry-pick abc123
git tag v2.4.1                    # patch release on the LTS line
git push origin release/v2.x v2.4.1

# Backport further to v1 LTS if applicable:
git checkout release/v1.x
git cherry-pick abc123
git tag v1.7.4
git push origin release/v1.x v1.7.4
```

**What is appropriate to backport:**

- Documentation corrections and errata
- BOM supplier substitutions (within the same `equiv_class`)
- Manufacturing-process clarifications
- Critical safety fixes

**What is *not* appropriate to backport:**

- Design changes (these become new module versions, not patches)
- New features
- Anything that would change the geometry exported in `cad/exports/`

### Working with Git Submodules

```bash
# Clone with all submodules
git clone --recurse-submodules https://github.com/refaqt/qarve.git

# Update all submodules to their recorded commit
git submodule update --init --recursive

# Fetch and merge latest from all submodule remotes
git submodule update --remote --merge

# After changing a submodule (edit, commit, push from inside it)
cd modules/x-axis
git add . && git commit -m "…" && git push
cd ../..
git add modules/x-axis
git commit -m "chore(submodules): bump x-axis"
```

### `.gitignore`

```gitignore
# Python
__pycache__/
*.pyc
.venv/

# FreeCAD
*.FCBak
*.FCStd1

# OS
.DS_Store
Thumbs.db

# Generated outputs
**/bom/bom_output.md
bom/bom.csv            # root-level aggregated BOM is generated
**/cad/params.csv      # active model, generated by resolve_params.py
analysis/results/*.md
```

Module-level `bom/bom.csv` files are source data and are committed. The root-level `bom/bom.csv` is generated by `aggregate_bom.py` and is gitignored. Similarly, every module's `cad/params.csv` is generated by `resolve_params.py` from `cad/params/default.csv` (+ optional model override) and is gitignored; only the inputs in `cad/params/` are committed.

The `graph/usage-graph.json` file is generated but **is** committed — it serves as a snapshot of the known consumer graph at each commit, useful for tracking changes to the install-base footprint over time.

### GitHub Settings

- **Labels:** `cad`, `firmware`, `docs`, `okh`, `arch`, `interface`, `model`, `build`, `lts-backport`, `module:x-axis`, `module:spindle`
- **Milestones** for design phases (e.g., `v0.1 — Proof of Concept`) and per major version (e.g., `v2.0 — Production Release`)
- **Releases** with CHANGELOG entries for each tagged version, including patch releases on LTS branches
- GitHub topics `open-hardware` and `okh` on all repos for discoverability
- **Branch protection** on `main` and every `release/vN.x` branch — these are long-lived and must stay clean

---

## Checklist for a New Design Session

**Documentation & decisions:**

- [ ] Create dev log entry (`docs/dev-log/YYYY-MM-DD_topic.md`)
- [ ] If a mistake was made, add entry to `docs/mistakes/`
- [ ] If a decision was made, write ADR (`docs/decisions/`)

**Design:**

- [ ] If requirements changed, update `architecture/*.sysml`
- [ ] If an interface changed, update its `port def` in SysML **and** decide whether the change is breaking → bump the interface version accordingly
- [ ] If parameters changed for the default model, update `cad/params/default.csv`; for a model variant, update `cad/params/<model>.csv`
- [ ] Run `cad/resolve_params.py <model>` for each affected model
- [ ] Run `cad/sync_params.py` inside FreeCAD to update geometry
- [ ] If BOM changed, update module `bom/bom.csv`; run `process_bom.py`
- [ ] Run `bom/aggregate_bom.py` (project root)
- [ ] If CAD changed, export `.step`, `.dxf`, `.stl` to `cad/exports/`; set drawing title block `Rev` to current `okh.toml` `version`
- [ ] FreeCAD document `Comment`: stable `Module: <slug> — see okh.toml` (do not bump per patch release)

**Manifests:**

- [ ] If a new part was added, add a `[[part]]` entry to the module's `okh.toml`
- [ ] If a new sub-module was added, add a `[[hasComponent]]` entry to the parent `okh.toml`
- [ ] If a new model was added, add a `[[model]]` entry
- [ ] If an interface changed, update `[[provides-interface]]` / `[[consumes-interface]]`
- [ ] If a breaking interface change occurred, plan an adapter module under `modules/adapters/`

**Install base & builds:**

- [ ] If this change affects deployed machines, review `graph/usage-graph.json` to identify which builds are affected
- [ ] For each affected build, decide: upgrade in place, add an adapter, document incompatibility, or backport a fix to the relevant `release/vN.x` branch
- [ ] If a build's modules were changed, update `builds/<id>/build.toml` and add an entry to `[[modification]]`
- [ ] If this is a supplier substitution (no design change), commit only to `release/vN.x` and tag a patch version

**Validation & commit:**

- [ ] Run `doqs/scripts/validate_all.py` (or individually: `validate_okh.py`, `check_names.py`, `check_links.py`, `validate_build.py`)
- [ ] Before tagging: `doqs/scripts/validate_okh.py --expected-version X.Y.Z`
- [ ] Run `doqs/scripts/build_graph.py` — regenerate `graph/usage-graph.json`
- [ ] Commit with a conventional commit message
- [ ] Tag versions where appropriate (semver in `okh.toml`, Git tag `vX.Y.Z`, patch tags on LTS branches)
- [ ] Push submodule repos before the main repo
