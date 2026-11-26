# Simulation and measurement

Part of the doqs specification. Start at the [overview](../architecture.md).

## Simulation

Every module has a `simulation/` folder for **design-time analysis** — physics and behavioral studies (FEA, thermal, kinematics, dynamics, etc.) that validate requirements declared in `architecture/`. This is distinct from:

- **`architecture/`** — SysML requirements and logical model (what must be true)
- **`cad/`** — geometry (what it looks like)
- **`firmware/`** / **`software/`** — control and host-side code at the project root (unit tests such as `test_kinematics.cpp` stay there)
- **`measurement/`** — the same quantity measured on real hardware rather than predicted

Simulation is **tool-agnostic** (CalculiX, OpenFOAM, custom Python, etc.). The folder convention is the same at every module depth, including extracted Git submodules — paths are unchanged, same as CAD and SysML.

### Directory layout

```
simulation/
├── README.md          # Tools, versions, how to reproduce
├── cases/             # Text-first case definitions (TOML/YAML/JSON, scripts, input decks)
│   └── <case-slug>/   # One folder per study (kebab-case; see naming.md)
└── results/           # Committed summaries; heavy binaries gitignored or LFS
    └── <case-slug>/
        ├── summary.md # Human/agent-readable pass/fail + key numbers
        └── exports/   # Optional plots/meshes (gitignored by default)
```

**Text-first.** Case definitions and `results/<case-slug>/summary.md` are source artefacts — readable, diffable, and agent-editable. Large binaries (meshes, plots, VTK) belong in `results/<case-slug>/exports/` and are gitignored by default (or tracked via Git LFS if a small set of reference outputs is needed).

**Requirement traceability.** Each `summary.md` should cite the SysML requirement(s) it verifies (by name, e.g. `TravelRequirement`, `PositioningAccuracy`). Do not duplicate authoritative constraints into simulation results — requirements stay in `architecture/*.sysml`.

**Parametric models.** When a study depends on dimensions, note which `[[model]]` / `cad/params/` set was used (e.g. `default`, `500mm`).

**CAD inputs.** Studies may reference geometry from `cad/exports/` (e.g. `.step` files). Keep relative paths from the module root so submodule extraction does not break links.

**Empty modules.** A module may have no studies yet — `simulation/` can be omitted until the first case is added, or exist with only a `README.md`. There is no validator enforcement for this folder.

**Case slugs.** Use the same kebab-case charset as module folder names (`carriage-deflection`, not `carriage_deflection` or `500mm-travel`). Do not encode dimensions or materials in case folder names — put values in case config files.

## Measurement

Every module may have a `measurement/` folder for **physical test campaigns** - data recorded from real
hardware. It is the empirical counterpart to `simulation/`: where a simulation case predicts behaviour,
a measurement campaign records what the built machine actually did.

Keep the distinction sharp:

- **`simulation/`** - design-time prediction (FEA, dynamics, thermal). No hardware involved.
- **`measurement/`** - a campaign run on physical hardware, with instruments, at a date, in a configuration.
- **`architecture/`** - the requirement each of the above is trying to verify.

Measurement is **tool-agnostic** (DAQ vendor software, oscilloscopes, custom Python rigs). Like CAD and
SysML, the folder convention is identical at every module depth, including extracted submodules.

### Directory layout

```
measurement/
|-- README.md          # Instruments, sensors, calibration, how to reproduce a run
|-- cases/             # Text-first campaign definitions (protocol, channel maps, sensor config)
|   `-- <case-slug>/   # One folder per campaign type (kebab-case; see naming.md)
|-- results/           # Committed summaries; raw data lives in external storage
|   `-- <case-slug>/
|       |-- summary.md # Findings, key numbers, which requirement this verifies
|       `-- exports/   # Optional small reference plots (gitignored by default)
`-- data-index.csv     # Manifest of the raw data held outside Git - see below
```

**Text-first, same as simulation.** The campaign definition and `summary.md` are source artefacts:
readable, diffable, agent-editable. What differs from simulation is the scale of the raw output -
measurement campaigns routinely produce gigabytes, which is what `data-index.csv` exists to handle.

**Requirement traceability.** Each `summary.md` cites the SysML requirement(s) it verifies, by name.
Where a matching simulation case exists, cite it too - a measured-vs-predicted comparison is the whole
point of keeping both folders.

**Configuration provenance.** Record which `[[model]]` / `cad/params/` set the hardware was built to,
and which firmware version was flashed. A measurement is meaningless without knowing what was measured.

### External data references

Raw measurement data does not belong in Git. Instrument captures are large, binary, vendor-specific,
and never merge. Git LFS is not the answer either: LFS bills storage *and* bandwidth, so a growing
archive of multi-gigabyte captures becomes expensive precisely as the project matures.

**The rule: raw data lives in external storage; Git holds a manifest that describes it.**

Each module with measurement data commits a `measurement/data-index.csv` - one row per file:

```csv
campaign,relpath,tier,bytes,sha256,recorded_utc,notes
tap-tests,2026-05-07_001/Alu_x_S24000_F1800_1.WDH,raw,8183296,3f2a...,2026-05-07T09:14:02Z,
tap-tests,2026-05-07_001/Alu_x_S24000_F1800_1.CSV,export,1310720,9c41...,2026-05-07T09:14:02Z,8-channel export
```

| Column | Meaning |
| ------ | ------- |
| `campaign` | Case slug this file belongs to - matches a folder under `cases/` |
| `relpath` | Path relative to the storage root, stable across mounts |
| `tier` | `raw` (instrument original), `export` (derived selection), `derived` (analysis output) |
| `bytes`, `sha256` | Integrity - lets any consumer verify a fetched file, and detects silent loss |
| `recorded_utc` | When the measurement was taken, not when the file was written |
| `notes` | Free text |

Extra columns may be appended for campaign-specific metadata (axis, position, material, spindle speed,
feed). Keep the seven above as the stable prefix so generic tooling can read any manifest.

**Where the data actually lives** is declared once in `measurement/README.md`: the storage backend, the
root path or bucket, and how to obtain access. Consumers resolve the root from an environment variable
rather than hardcoding it, so the same manifest works on every machine:

```
Storage : Google Drive (shared drive "Projects")
Root    : $MACHINE_DATA_ROOT, default "H:/Shared drives/.../Data"
Access  : request from the project owner
```

**Why a manifest is worth the effort.** It makes the archive queryable without downloading any of it -
*"which tap tests ran on aluminium above 20 000 rpm?"* is answered from a committed CSV. It survives the
storage backend changing (only the README and the root variable move). It gives AI agents a complete
picture of the experimental record within their context budget. And the checksums turn "the data is on
a shared drive somewhere" into something you can actually verify.

**Empty modules.** A module may have no campaigns yet - `measurement/` can be omitted until the first
one, or exist with only a `README.md`. There is no validator enforcement for this folder.

**Case slugs.** Same kebab-case charset as module folders (`tap-tests`, `stability-tests`,
`thermal-drift`). Name the *study*, not the conditions - spindle speeds and materials are data, and
belong in the manifest and case config, never in the folder name.
