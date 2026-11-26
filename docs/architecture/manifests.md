# Requirements and OKH manifests

Part of the doqs specification. Start at the [overview](../architecture.md).

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
# Hardware licence (this manifest describes the hardware project).
# Firmware/software is GPL-3.0; docs/media is CC BY-SA 4.0. See README.md / LICENSE.
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

Two keys tie the manifest to the architecture, so a check can follow a part from its SysML definition to its file ([ADR-015](../decisions/2026-10-07_port-and-frame-share-a-name.md)):

```toml
# A part we make: `sysml` names its part def in architecture/<module>.sysml.
[[part]]
name   = "Base"
source = ["cad/parts/base/base.FCStd"]
sysml  = "Base"

# A part we buy: the BOM row that buys it, the library reference, and its part def.
[[bought-part]]
bom   = "MEC-001"
part  = "stoq:hiwin/hgl-block#HGL15CAZBC+E2"
sysml = "GuideBlock"
```

`doqs scaffold part` and `doqs use-part` write them. `validate_interfaces.py` checks that each `sysml` name exists and that every port of that part def has its frame in the file.

When a module is extracted to its own repo, update its `repo` field and the `[[hasComponent]]` URL in the parent manifest.

### Validation Script (`doqs/scripts/validate_okh.py`)

[`scripts/validate_okh.py`](../../scripts/validate_okh.py) reads every `okh.toml` outside the
tooling submodules and checks that each one carries the required fields:

`okhv`, `name`, `repo`, `version`, `license`, `licensor`, `function`.

It also checks the SPDX licence expression, the paths in `bom` and `readme`, and — with
`--expected-version` — that the root manifest matches a released version.

Related validators (documented in their own sections):

- `doqs/scripts/validate_names.py` — module slugs, BOM ids, model slugs, naming lexicon ([naming.md](../naming.md)).
- `doqs/scripts/validate_all.py` — runs `validate_okh`, `validate_licenses`, `validate_names`, `validate_links`, `validate_build`, `validate_variants` and `validate_cad` in sequence.
- `doqs/scripts/validate_licenses.py` — split-licence files (`LICENSE`, `LICENSES/`, `TRADEMARKS.md`, directory stubs). Use `apply_licenses.py` to write them.
- `doqs/scripts/validate_build.py` — checks that lockfiles in `builds/` represent interface-consistent compositions.
- `doqs/scripts/validate_variants.py` — product families: see [variants.md](../variants.md).
- `doqs/scripts/resolve_graph.py` — regenerates `graph/usage-graph.json` from all manifests and lockfiles (generator, not a gate).
- `doqs/scripts/aggregate_bom.py` — machine-root purchasing list; understands families and instance modules.
- `doqs/scripts/resolve_params.py`, `resolve_bom.py`, `resolve_instance.py`, `export_variant.py` — variant resolvers (generators, not gates).
