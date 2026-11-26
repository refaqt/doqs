> **Reference machine:** [Qarve](https://github.com/refaqt/qarve) · **Tools:** [DOQS](https://github.com/refaqt/doqs) submodule at `doqs/`. Examples may still say `cnc-mill` or `org` as generic placeholders.
# Documentation System — Open-Source CNC Milling Machine

This page is the short overview of the doqs specification. It says what doqs is and
names the main ideas. The full rules for each topic are on their own page, listed in
the table at the end. Read only the page for the topic you work on.

doqs is a set of rules, templates and checks for open hardware projects that live in
git. A machine repository mounts doqs at `doqs/` and runs `doqs check` to prove that
it follows the rules.

## Philosophy

All project files are **text-first**. Binary files are used only where unavoidable (e.g., FreeCAD `.FCStd` files). Every text file must be readable, diffable, and editable by both humans and AI agents (Cursor, Claude Code, etc.). The project lives on GitHub, so everything must be Git-friendly.

Every **module** — from an individual manufactured part up to the complete machine — is treated as a potentially independent, publishable unit from the start. The folder structure is **identical at every nesting level** (`bom/`, `cad/`, `architecture/`, `simulation/`, etc.). The project root is itself a module.

## Main ideas

**Module.** Every folder under `modules/` is a module, and the repository root is the
top module. Each module has the same first-level folders: `bom/`, `cad/`,
`architecture/`, `docs/`, `manufacturing/`, `simulation/`, `measurement/` and
`modules/`. A module lives as a plain folder, or in its own repository as a git
submodule at the same path.

**Manifest.** Each module has an `okh.toml` file in the Open Know-How format. It
names the module, its version, its licence, its parts, its sub-modules and its
interfaces.

**Licence split.** A machine repository does not use one licence for everything.
Hardware is CERN-OHL-S v2.0, firmware and software are GPL-3.0, and documentation
and media are CC BY-SA 4.0. Supplier geometry keeps the supplier's own terms.

**Versions and models.** Each module has its own version number, set with git tags,
and long-lived `release/vN.x` branches for machines that are already built. A model
is a variant that exists next to the others, for example a 300 mm and a 500 mm
travel. A model is a small CSV file that overrides the default parameters.

**Interfaces.** Two modules connect through an interface. It is a SysML `port def`
with its own version, and it is listed in both `okh.toml` files. A port, a mounting
frame in the FreeCAD file and the `okh.toml` entry share one name. An adapter module
connects two interface versions that do not fit.

**Builds.** A machine that was really built gets a lockfile,
`builds/<id>/build.toml`. It pins every module to an exact version, so the machine
can be supported for as long as it is in use.

**Parameters.** The sizes of a part come from `cad/params/default.csv`. FreeCAD
reads them into a `Params` sheet, and every dimension in the model is an expression
over that sheet.

**Tooling submodules.** `doqs/` holds these tools and `.agents/` holds the shared
agent rules. Both are mounted as git submodules, and the checks skip both.

## Topic pages

| Topic | Page |
| --- | --- |
| Modules, the two ways to deploy them, the full folder tree, licensing, SysML imports between modules | [architecture/modules.md](architecture/modules.md) |
| Versions, tags and release branches, parametric and structural models, stages, the reverse usage graph | [architecture/versioning.md](architecture/versioning.md) |
| Interface definitions in SysML and OKH, shared names for ports and frames, adapter modules | [architecture/interfaces.md](architecture/interfaces.md) |
| Build records and lockfiles, customer builds, `validate_build.py` | [architecture/builds.md](architecture/builds.md) |
| Requirements, and the `okh.toml` manifest for the machine and for each module | [architecture/manifests.md](architecture/manifests.md) |
| CSV parameter files and how FreeCAD reads them | [architecture/parameters.md](architecture/parameters.md) |
| Simulation cases and measurement campaigns, with external data | [architecture/simulation-and-measurement.md](architecture/simulation-and-measurement.md) |
| Firmware and host software folders | [architecture/firmware-and-software.md](architecture/firmware-and-software.md) |
| Markdown, TOML, JSON, CSV, BOM columns, SysML and FreeCAD file rules, master sketches | [architecture/file-formats.md](architecture/file-formats.md) |
| Commit messages, branches, backports, tooling submodules, `.gitignore`, GitHub settings | [architecture/git.md](architecture/git.md) |
| What to check at the end of a design session | [architecture/checklist.md](architecture/checklist.md) |

Other doqs pages cover product families ([variants.md](variants.md)), parts libraries
([parts-library.md](parts-library.md)), roles ([roles.md](roles.md)), FreeCAD work
by agents ([agent-cad.md](agent-cad.md)) and naming ([naming.md](naming.md)).
