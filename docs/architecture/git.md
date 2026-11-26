# Git and GitHub

Part of the doqs specification. Start at the [overview](../architecture.md).

## Git & GitHub Conventions

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>
```

Types: `feat`, `fix`, `docs`, `cad`, `arch`, `okh`, `firmware`, `sim`, `chore`, `refactor`, `interface`, `model`, `build`

```
docs(log): 2025-06-10 Z-axis bearing selection
cad(x-axis): update carriage plate to 8mm thickness
arch(x-axis): add TravelRequirement in SysML
okh(x-axis): add [[part]] entries for carriage and motor mount
firmware(controller): add homing sequence
sim(x-axis): add carriage deflection case
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

### Tooling submodules (`doqs/`, `.agents/`)

Machine repos mount this tools repo at `doqs/` and [refaqt-agents](https://github.com/refaqt/refaqt-agents) at `.agents/`. Those are **tooling** submodules, not extracted machine modules.

Every gate that walks the machine root skips both folder names, at any depth. The check is `is_under_tooling_submodule()` in [`scripts/naming_rules.py`](../../scripts/naming_rules.py); the licence and CAD gates use the same name list. Neither submodule holds machine content, so a sample `okh.toml`, `catalog.toml`, or `.sysml` file inside them must never fail a machine gate. Add a new tooling submodule to `TOOLING_SUBMODULE_NAMES` in that file, not to a single script.

How to add the submodules to a repository, and what each helper writes, is in
[using-doqs.md](../using-doqs.md#2-add-doqs-to-a-repository). Two rules matter at the architecture
level: only the tooling submodules (`doqs`, `.agents`) carry `branch = main`, and extracted
modules under `modules/` stay pinned to a commit.

The committed gitlink remains a pin. Do not commit dirty gitlinks after `--remote` unless freezing a pin. CI may still check out the recorded pin (`submodules: recursive`, not `--remote`). Extracted machine modules under `modules/` stay SHA-pinned without `branch`, so the `--remote` call names `doqs` and `.agents` explicitly: `--remote` on a submodule without `branch` tracks the remote default branch instead of the recorded SHA.

doqs mounts the kit at its own `.agents/` too, so its `.gitmodules` sets `update = none` on that submodule. Git skips `doqs/.agents` in a consumer repo, so the kit is not mounted twice and the `doqs` gitlink does not go dirty. Working on doqs on its own needs `git submodule update --init --remote --checkout .agents`, where `--checkout` overrides that flag.

`CLAUDE.md` and `AGENTS.md` are written by the shared kit's `sync_root.py` from [refaqt-agents `templates/root/`](https://github.com/refaqt/refaqt-agents/tree/main/templates/root), not by this repository.

### Working with Git Submodules

Extracted **machine-module** submodules (for example `modules/x-axis`) stay SHA-pinned. Bump the pointer when you adopt a new module version:

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
**/simulation/results/**/exports/
**/measurement/results/**/exports/

# Variant geometry is regenerated on demand, never committed per model.
# Omit this line in a single-model repo that commits its exports.
**/cad/exports/
```

Committed despite being generated: `cad/params-table.csv` (the configuration table a parent needs to select a model) and, in an instance module, `bom/bom.csv`, `bom/resolved.csv` and `cad/resolved/*`. Those exist to be reviewed — their diff is what a family update changed for that machine — and `validate_variants.py` fails when they are stale.

Module-level `bom/bom.csv` files are source data and are committed. The root-level `bom/bom.csv` is generated by `aggregate_bom.py` and is gitignored. Similarly, every module's `cad/params.csv` is generated by `resolve_params.py` from `cad/params/default.csv` (+ optional model override) and is gitignored; only the inputs in `cad/params/` are committed.

The `graph/usage-graph.json` file is generated but **is** committed — it serves as a snapshot of the known consumer graph at each commit, useful for tracking changes to the install-base footprint over time.

### GitHub Settings

- **Labels:** `cad`, `firmware`, `docs`, `okh`, `arch`, `interface`, `model`, `simulation`, `build`, `lts-backport`, `module:x-axis`, `module:spindle`
- **Milestones** for design phases (e.g., `v0.1 — Proof of Concept`) and per major version (e.g., `v2.0 — Production Release`)
- **Releases** with CHANGELOG entries for each tagged version, including patch releases on LTS branches
- GitHub topics `open-hardware` and `okh` on all repos for discoverability
- **Branch protection** on `main` and every `release/vN.x` branch — these are long-lived and must stay clean
