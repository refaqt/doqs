# Checklist for a design session

Part of the doqs specification. Start at the [overview](../architecture.md).

## Checklist for a New Design Session

**Documentation & decisions:**

- [ ] Record session work in `docs/log/` if warranted (see `.agents/skills/log/SKILL.md`)
- [ ] If a mistake was made, add entry to `docs/mistakes/` (see `.agents/skills/mistake-log/SKILL.md`)
- [ ] If a decision was made, write ADR in `docs/decisions/` (see `.agents/templates/adr.md`)

**Design:**

- [ ] If requirements changed, update `architecture/*.sysml`
- [ ] If an interface changed, update its `port def` in SysML **and** decide whether the change is breaking → bump the interface version accordingly
- [ ] If parameters changed for the default model, update `cad/params/default.csv`; for a model variant, update `cad/params/<model>.csv` (only the rows that differ — derived values follow)
- [ ] Run `doqs/scripts/resolve_params.py --table` and commit `cad/params-table.csv`
- [ ] Run `doqs/scripts/cad_sync_params.py` inside FreeCAD to update geometry (`sync_table()` after adding or removing a model)
- [ ] If BOM changed, update module `bom/bom.csv`
- [ ] If a new length was added, add its row to each bound `bom/tables/<part>.csv` — a length no supplier stocks fails validation
- [ ] Run `doqs/scripts/aggregate_bom.py` (project root)
- [ ] If CAD changed, export `.step`, `.dxf`, `.stl` to `cad/exports/`; set drawing title block `Rev` to current `okh.toml` `version`
- [ ] FreeCAD document `Comment`: stable `Module: <slug> — see okh.toml` (do not bump per patch release)
- [ ] If geometry or loads changed, update affected `simulation/cases/<case-slug>/` inputs
- [ ] Re-run studies and update `simulation/results/<case-slug>/summary.md`; cite SysML requirement names verified

**Manifests:**

- [ ] If a new part was added, add a `[[part]]` entry to the module's `okh.toml`
- [ ] If a new sub-module was added, add a `[[hasComponent]]` entry to the parent `okh.toml`
- [ ] If a new model was added, add a `[[model]]` entry
- [ ] If a family SKU was added or retired, update `catalog.toml`
- [ ] If a purchased part's geometry was added, put it in `cad/vendor/` and record it in `cad/vendor/vendor-index.csv`
- [ ] If a family submodule was bumped, re-run `doqs/scripts/resolve_instance.py` and **review the resolved BOM diff** before ordering
- [ ] If an interface changed, update `[[provides-interface]]` / `[[consumes-interface]]`
- [ ] If a breaking interface change occurred, plan an adapter module under `modules/adapters/`

**Install base & builds:**

- [ ] If this change affects deployed machines, review `graph/usage-graph.json` to identify which builds are affected
- [ ] For each affected build, decide: upgrade in place, add an adapter, document incompatibility, or backport a fix to the relevant `release/vN.x` branch
- [ ] If a build's modules were changed, update `builds/<id>/build.toml` and add an entry to `[[modification]]`
- [ ] If this is a supplier substitution (no design change), commit only to `release/vN.x` and tag a patch version

**Validation & commit:**

- [ ] If this is a new repo or a new first-level content directory, run `doqs/scripts/apply_licenses.py` and add a README Licence section
- [ ] Run `bash doqs.sh pre-pr` (it saves FreeCAD work, then runs `doqs generate` and `doqs check`)
- [ ] Before tagging: `doqs/scripts/validate_okh.py --expected-version X.Y.Z`
- [ ] Run `doqs/scripts/resolve_graph.py` — regenerate `graph/usage-graph.json`
- [ ] Commit with a conventional commit message
- [ ] Tag versions where appropriate (semver in `okh.toml`, Git tag `vX.Y.Z`, patch tags on LTS branches)
- [ ] Push submodule repos before the main repo
