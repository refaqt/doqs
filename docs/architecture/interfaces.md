# Interfaces

Part of the doqs specification. Start at the [overview](../architecture.md).

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

### One name for a port, a frame and an OKH entry

An interface between two parts exists three times: as a `port def` with a port on each part in SysML, as a mounting frame (`IF_...`) in each part's FreeCAD file, and, when it faces outside the module, as an entry in `okh.toml`. One rule gives all three their names, so a tool can create them together and a validator can check that they agree ([ADR-015](../decisions/2026-10-07_port-and-frame-share-a-name.md)):

| In SysML | In FreeCAD | In `okh.toml` |
| --- | --- | --- |
| `port def RailMountInterface_v1` | | `name = "RailMountInterface"`, `version = "1.0"` |
| `port referenceRailMount : RailMountInterface_v1;` on `part def Base` | frame `IF_reference_rail_mount` in `base.FCStd` | |
| `port baseMount : ~RailMountInterface_v1;` on `part def GuideRail` | frame `IF_base_mount` in the rail's file | |

The frame label is the port name in lowercase with underscores, after `IF_`. The OKH name is the port def without its version suffix; the OKH version is that suffix followed by `.0`. Only the major version must match. The helpers in `doqs/scripts/interface_rules.py` apply the rule, `doqs/scripts/sysml_rules.py` adds the SysML statements without touching the rest of the file, and `doqs/scripts/okh_rules.py` adds the manifest entry the same way.

### Adapter Modules

When a breaking interface change occurs, the bridge between old and new is itself a module. Adapter modules live under `modules/adapters/` and have the same internal structure as any other module — `bom/`, `cad/`, `architecture/`, `simulation/`, etc. — but their function is explicitly to translate between interface versions.

```
modules/adapters/
  spindle-mount-v1-to-v2/
    okh.toml
    bom/
    cad/
    architecture/      ← provides v1 interface, consumes v2 interface
    docs/
    manufacturing/
    simulation/
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
