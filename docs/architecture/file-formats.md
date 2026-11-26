# File formats

Part of the doqs specification. Start at the [overview](../architecture.md).

## File Format Guidelines

### Markdown (`.md`) — Narrative Documentation

Used for: activity log, mistakes log, decisions, README files, assembly guides.

**Narrative doc folders** (machine repo `docs/`):

| Folder | Purpose |
|--------|---------|
| `docs/log/` | Chronological activity record across all roles |
| `docs/mistakes/` | Incidents and prevention rules |
| `docs/decisions/` | Architecture Decision Records (ADRs) |

Agents follow `.agents/rules/living-docs.md` and the `log` / `mistake-log` skills in [refaqt-agents](https://github.com/refaqt/refaqt-agents) for entry format and update triggers.

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
id,name,spec,category,qty,unit,unit_mass_g,equiv_class,
brand,brand_pn,part,
notes
```

**The BOM says what is inside, not what it costs.** Prices, distributors and
distributor part numbers left these columns on 2026-09-18; a price changes every
week and a design rarely does, so they do not share a file or a history. A
separate application answers cost, joining on `part` — or on `brand` plus
`brand_pn` where the item is not in a parts library. See
[ADR-006](../decisions/2026-09-18_money-out-of-the-bom.md).

`brand` is the name on the part (HIWIN, Beckhoff, DIN) and is stable for
decades. It is not the supplier you buy from, which is commercial and belongs
with the prices. `part` is a reference into a parts library,
`stoq:hiwin/hgr-rail#HGR20R500` — see [parts-library.md](../parts-library.md).

**Equivalence classes for LTS sourcing.** The `spec` column describes what the design requires (e.g. `"SPDT 5A lever microswitch"`). The `equiv_class` column tags interchangeable parts with a short identifier (e.g. `SPDT-5A-LEVER`). When a supplier part goes EOL, an updated `bom.csv` on a `release/vN.x` branch substitutes another part in the same `equiv_class` — no design change, only sourcing. This separates *part specification* (lives forever, defined by the design) from *part instance* (evolves with the market, refreshed on LTS branches).

Example row:

```
SW-001,Limit Switch,"SPDT 5A lever",electrical,4,pc,18,SPDT-5A-LEVER,Omron,X20-1,,
```

**Model-aware BOMs.** The 12 columns above are fixed — validators check the header exactly — so anything that varies per model lives beside `bom.csv`, not in it:

| File | Purpose |
| --- | --- |
| `bom/tables/<part>.csv` | One row per stocked length of an off-the-shelf part: part number, price, mass, and the vendor STEP |
| `bom/sources.toml` | `[[bind]]` entries connecting a BOM row to a length table; `[[vendor]]` entries pointing a purchased part at its geometry |
| `bom/models/<model>.csv` | Column-sparse overlay: only the columns in its header are overridden |

A cell may also carry `{alias}` placeholders resolved from the module's parameters, for cut-to-length stock with no per-length part number. Resolve with `doqs/scripts/resolve_bom.py`. Full rules in [variants.md](../variants.md#off-the-shelf-parts-that-come-in-lengths).

**Parameter table convention** (`cad/params/default.csv` plus optional `cad/params/<model>.csv` overrides):

```
alias,value,unit,basis,source,description
```

The `alias` must match the FreeCAD Spreadsheet cell alias exactly. `basis` and `source` say where an independent value comes from; see [Parameter File Format](parameters.md#parameter-file-format). See the *Linking CSV Parameters to FreeCAD* section for the model-override workflow.

**Working with a BOM.** Two doqs scripts do this; a module never carries its own copy.

- [`scripts/resolve_bom.py`](../../scripts/resolve_bom.py) resolves one module's BOM for one model:
  it applies the column-sparse overlay, looks up length tables through `bom/sources.toml`, and
  fills `{alias}` placeholders from the module's parameters. Writes to stdout, or to `--out`.
- [`scripts/aggregate_bom.py`](../../scripts/aggregate_bom.py) walks every module and writes one
  purchasing list at `bom/bom.csv` in the machine root.

An earlier version of this document printed a `bom/process_bom.py` here. No such script has ever
shipped in doqs. If a repository holds a hand-copied BOM script, delete it and use the two above.

### SysML (`.sysml`) — System Architecture and Requirements

Used for: block definitions, requirements, interfaces, state machines, part properties. This is the authoritative source for requirements — there are no separate requirements documents.

**Free tooling:**

| Tool | Notes |
| --- | --- |
| [SysON](https://mbse-syson.org/) via `syson.bat` / `python doqs/scripts/syson.py ui` | Graphical editor. Docker Desktop once, then Open/Save against `architecture/*.sysml`. See [syson.md](../syson.md). |
| [Syside Editor](https://marketplace.visualstudio.com/items?itemName=sensmetry.syside-editor) | VS Code / Cursor language support for the same text files |
| Cursor / Claude Code | Plain text, no special tooling needed |

Do not treat SysON’s homepage project zip (JSON documents + diagram layouts) as the git source of truth. Canonical models stay in `architecture/*.sysml`.

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
*.step  filter=lfs diff=lfs merge=lfs -text
*.stp   filter=lfs diff=lfs merge=lfs -text
```

Track `*.step` in family repos: supplier geometry under `cad/vendor/` is committed for every stocked length of a rail or screw.

LFS must be configured in each extracted module repo individually.

A clone without LFS content holds small text placeholders in place of these files. Cloud
sessions work like this on purpose, to save LFS bandwidth. `validate_cad.py` and
`validate_variants.py` do not compare a placeholder's checksum. They print one warning line
that names the placeholders, and the check still passes. CI runs `git lfs pull` before the
checks, so it compares the real files. See
[docs/mistakes/2026-10-20_lfs-placeholders-failed-the-checks.md](../mistakes/2026-10-20_lfs-placeholders-failed-the-checks.md).

**Exports after significant changes:** `.step` (geometry interchange), `.dxf` (2D drawings), `.stl` (GitHub 3D browser preview). Commit alongside the `.FCStd`.

### Top-down design and master sketches

Top-down CAD — a master sketch in an assembly file driving geometry in child part files via `SubShapeBinder` — is supported, but FreeCAD tracks dependencies at the **document** level. If a part Binder-links into the same document the assembly will insert it from, FreeCAD sees a cycle (assembly → part → assembly) and refuses insertion.

**Required pattern in the assembly file:** put master sketches in a dedicated `PartDesign::Body` (e.g. `Body_master`) under a `Master sketches` group. Sketches must use **that Body's origin planes**, not the `Assembly` object's origin planes. Child parts bind to sketches inside the Body. The Assembly object holds joints and inserted part links only.

```
assembly.FCStd
├── Assembly
├── Master sketches (Group)
│   └── Body_master
│       └── Sketch …
└── parts/…  (inserted as App::Link; each may Binder → Body_master sketches)
```

See ADR [2026-06-24_freecad-master-sketches-body.md](../decisions/2026-06-24_freecad-master-sketches-body.md).

**Alternatives when a cycle cannot be avoided:**

| Approach | When to use |
| -------- | ----------- |
| **Skeleton document** | Master sketches shared across multiple assemblies or modules; both assembly and parts link *into* a separate `skeleton.FCStd` (or the module's params file) |
| **Parameter spreadsheet** | Dimensions and offsets only — no projected geometry; use `params.csv` aliases instead of Binders ([Linking CSV Parameters to FreeCAD](parameters.md#linking-csv-parameters-to-freecad)) |
