# Agent CAD

How agents create and edit FreeCAD models in a DOQS machine repository — while
you keep the files open, without any path that can silently overwrite your work,
and without spending thousands of tokens on screenshots.

## The problem this solves

FreeCAD does not lock a `.FCStd` while it is open. It reads the zip into memory
when you open it and writes at save time, so an external process can write the
file underneath an open session — and FreeCAD will not notice.
[FreeCAD#8924](https://github.com/FreeCAD/FreeCAD/issues/8924), open since March
2023 and labelled high priority, puts it plainly: the second save *"happily
overwrites the changes. No warning."*

That makes the naive approach — an agent running `FreeCADCmd` against a file you
have open — a silent data-loss machine:

1. You open `rail.FCStd`. FreeCAD holds an in-memory copy.
2. The agent rebuilds it headless and saves. Disk now has the agent's version.
3. You press Ctrl+S. Your copy overwrites the agent's work. No warning.

Or the reverse order, and your work is the casualty. Nothing errors and nothing
corrupts — you just lose one side. `.FCBak` rotation makes it worse: a few stray
saves push your real last-good state out of the backup window.

The fix is not "close your files first". It is to have the agent work **inside
the running FreeCAD process**, on the same in-memory document you are looking at,
so there is never a second copy to reconcile.

## Architecture

The agent edits `cad/build_model.py` — a plain Python file, the reviewable
artefact in the pull request. It supplies `build(doc, params)`; the scaffolding
around it lives in [`scripts/cad_build.py`](../scripts/cad_build.py) and updates
with the submodule. That one entry point runs in either context:

| Context | What happens | Saves? |
| --- | --- | --- |
| **Interactive** — FreeCAD open | Edits the document you are looking at, in one undo transaction | Never. Yours to save. |
| **Headless** — `FreeCADCmd cad/build_model.py` | Opens from disk, rebuilds, saves, fingerprints | Yes. This is the CI path. |
| **Export** — `export_variant.py`'s macro | Opens from disk, syncs parameters in memory, writes only the STEP | **Never.** The document is not this process's to write. |

The `.FCStd` stays a generated output. The reviewable diff is Python.

The bridge into the running GUI is the [`freecad-mcp`](https://github.com/neka-nat/freecad-mcp)
addon: an RPC server inside FreeCAD's own process that marshals work onto the Qt
GUI thread. That marshalling is the part worth reusing — FreeCAD documents and
the Coin3D scenegraph are not thread-safe, and touching them from another thread
wedges the event loop.

## Setup

### 1. Prerequisites

FreeCAD 1.1.x, [uv / uvx](https://docs.astral.sh/uv/guides/tools/), Python 3.12+.

### 2. Install the FreeCAD addon

```bash
git clone https://github.com/neka-nat/freecad-mcp.git
cd freecad-mcp
```

Copy `addon/FreeCADMCP` into your FreeCAD addon directory so the result is
`Mod/FreeCADMCP`:

| Platform | Directory |
| --- | --- |
| Windows (1.1) | `%APPDATA%\FreeCAD\v1-1\Mod\` |
| Windows (1.0) | `%APPDATA%\FreeCAD\Mod\` |
| macOS (1.1) | `~/Library/Application Support/FreeCAD/v1-1/Mod/` |
| Linux, Debian | `~/.local/share/FreeCAD/Mod/` |
| Linux, Arch (1.1) | `~/.local/share/FreeCAD/v1-1/Mod/` |
| Linux, Flatpak | `~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod/` |

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force "$env:APPDATA\FreeCAD\v1-1\Mod"
Copy-Item -Recurse addon\FreeCADMCP "$env:APPDATA\FreeCAD\v1-1\Mod\"
```

FreeCAD 1.1 keeps a folder per version on Windows too. `%APPDATA%\FreeCAD\Mod` is
not read at all by 1.1, and an add-on copied there never loads. Ask FreeCAD itself if you are
unsure which folder is yours:

```powershell
FreeCADCmd -c "import FreeCAD; print(FreeCAD.getUserAppDataDir())"
```

Restart FreeCAD, select the **MCP Addon** workbench, and click **Start RPC
Server** in the **FreeCAD MCP** toolbar. **Auto-Start Server** in the same menu
makes that automatic.

Leave **Remote Connections** off. The RPC server executes arbitrary Python and
must stay bound to `localhost`.

### 3. Install the repository configuration

From the machine repository root:

```powershell
bash setup-tooling.sh
```

That installs two files from [`templates/agent-cad/`](../templates/agent-cad/),
**once** — they are yours to edit afterwards and a later update will not
overwrite them:

* `.mcp.json` — registers the FreeCAD MCP server
* `.claude/settings.json` — the guard, below

## The guard

```json
{
  "permissions": {
    "deny": [
      "mcp__freecad__execute_code_headless",
      "mcp__freecad__reload_document"
    ]
  }
}
```

These two tools are the entire on-disk hazard surface, and denying them by bare
name removes them from the agent's context completely — not prompted for, not
visible, not callable.

* **`execute_code_headless`** runs agent code in a separate `freecadcmd` process,
  and its own documentation instructs the model to open documents from disk and
  save them.
* **`reload_document`** is the upstream remedy for the resulting divergence, and
  it works by closing your in-memory document and reopening from disk — which
  discards your unsaved work.

With both gone, no code path in the addon writes to disk. The `.FCStd` changes
only when you press Ctrl+S. `validate_cad.py` fails the build if the rules go
missing, so this cannot quietly rot.

Two things worth knowing:

* **The upstream addon itself is clean.** It contains no `doc.save()` calls. The
  hazard is these two tools, not a bug — which is why the fix is a deny list
  rather than a patch or a fork.
* **Do not use the OS read-only attribute instead.** FreeCAD ignores it and saves
  anyway ([FreeCAD#25474](https://github.com/FreeCAD/FreeCAD/issues/25474)). It
  would give false confidence.

## How an agent sees a model

Screenshots are the expensive *and* low-information option. An image costs
`⌈width/28⌉ × ⌈height/28⌉` visual tokens, so a 1920×1080 viewport is about 2,700
tokens — and still cannot tell you whether a rail is 500 mm long.

Two approaches that sound promising and are not:

* **STEP export.** It is text, but it is an interchange format: a modest part is
  tens of thousands of lines of `#1234=CARTESIAN_POINT(...)`. Reading it costs
  far more than a screenshot and conveys less. STEP stays what it is — archival
  and downstream CAM.
* **Reading the `.FCStd`.** It is a zip, and `Document.xml` genuinely helps for
  *structure* — the object tree, properties and expressions. But geometry lives
  in opaque binary `.brp` files, so it cannot answer what shape you got.

What works is to **measure instead of look**:

| Tier | Answers | Where from | Cost |
| --- | --- | --- | --- |
| 0 | Did it work? | recompute status, `obj.State` | ~50 tokens |
| 1 | Right size, right place, sane solid? | the fingerprint, below | ~60–80 per object |
| 2 | Did I break a reference? | sketch `solve()`, `FullyConstrained`, `OutList`/`InList` | cheap text |
| 3 | What is the actual profile? | `shape.slice()` → point list | ~100s |
| 4 | Does it *look* right? | `get_view(width=640, height=480)` | 266–638 tokens |

`--only-text-feedback` in `.mcp.json` suppresses the screenshot otherwise
attached to eight tools. The explicit `get_view` ignores that flag, so tier 4
stays available when a question is genuinely visual — it just stops being the
default.

### Fingerprints

`cad/<document>.fingerprint.json` is written on every build by
[`scripts/cad_fingerprint.py`](../scripts/cad_fingerprint.py) and committed:

```json
{
  "schema": 1,
  "saved": true,
  "sources": {"rail.FCStd": "…sha256…", "rail.stl": "…sha256…"},
  "params": {"rail_length": 500.0},
  "objects": {
    "Pad": {
      "type": "PartDesign::Pad", "valid": true, "closed": true,
      "volume": 124500.0, "area": 18600.0,
      "bbox": [0.0, 0.0, 0.0, 500.0, 40.0, 30.0],
      "com": [250.0, 20.0, 15.0],
      "counts": {"solids": 1, "shells": 1, "faces": 14, "edges": 36, "verts": 24}
    }
  }
}
```

It does three jobs at once:

* The agent reads the **diff**, not the whole state — tens of tokens per
  iteration, and *"bbox[3]: 500.0 -> 480.0"* is a better answer than a render.
* It is a **geometric regression gate**. A change that moves a volume 40% shows
  up as a text diff in the pull request, whether or not anyone thought to look.
* DOQS computes it, not the MCP, so headless CI and the live GUI session produce
  the same numbers.

Only objects that carry real geometry are measured. Datum lines, planes and
points are skipped, and so is an object whose `Shape` is a link to another object
rather than geometry of its own. An analysis mesh is the common case: it points
`Shape` at the part it was meshed from. The mesh is a result, not geometry the
design owns, so it is left out and the part beside it is measured as usual.

Centre of mass earns its place by catching mirrored and rotated parts whose
volume, area and bounding box are all unchanged.

FreeCAD spreads that one number over two properties, and a fingerprint reads
whichever the shape carries. `CenterOfMass` covers a solid, a shell, a face, a
wire and an edge. `CenterOfGravity` covers a compound — which is what an
`App::Part`, an `App::Link`, an assembly, a PartDesign `Body` and every
PartDesign feature actually return. For a compound of solids the two give the
same number, so entries written by either route compare directly. A shape with
no mass at all records `com: null` and keeps the rest of its entry.

Values are rounded to six significant figures. OCCT recomputes are not bit-stable
across platforms, and without that tolerance every rebuild would emit a diff.

## Working with a file open

1. Open the part in FreeCAD. Keep working in it.
2. Ask the agent for a change. It edits `cad/build_model.py` and asks the running
   instance to execute it.
3. The geometry updates in front of you, inside one undo transaction. **Ctrl+Z
   reverts the whole rebuild.** Your unsaved edits are untouched.
4. When you are happy, **you** save.
5. Before committing, rebuild headless so the fingerprint matches the saved file:

```powershell
FreeCADCmd cad/build_model.py
```

A good run ends with `Rebuilt and saved <document>`. If you do not see that line,
nothing was built: read the error above it.

A fingerprint measured from an unsaved document records `"saved": false`, and
`validate_cad.py` rejects committing one — the numbers would describe geometry
that cannot be reproduced from the committed `.FCStd`.

## Validation

```powershell
python doqs/scripts/validate_cad.py
python doqs/scripts/validate_cad.py --check-clean
```

| Check | Catches |
| --- | --- |
| Guard rules present | The deny list was removed or never installed |
| Fingerprint present and current | Geometry changed without a rebuild |
| `saved: true` | A fingerprint taken from an unsaved GUI document |
| Recorded digests match | A hand-edited `.FCStd` or a stale `.step`/`.stl` |
| Part on top | A part whose Body is not inside a Part container |
| Build script runs headless | A build script that ends with `if __name__ == "__main__":`, so FreeCADCmd 1.1 builds nothing |
| Own models in a parts library | A model under `cad/own/` with no build script, no parameters, no current fingerprint, or a Body on top; a tracked `.FCBak` or `__pycache__/` |
| Every dimension is linked | A sketch that can still move, or a size typed in as a number. A warning; a failure with `--strict-parametric` |
| Joints attach to mounting frames | An Assembly joint that uses a face, an edge or a point of a solid. A warning; a failure with `--strict-parametric` |
| `--check-clean` | An agent session left a `.FCStd` modified on disk |

The guard check applies only once a repository actually contains a `.FCStd` —
a machine repo with no CAD has nothing to guard. `validate_cad.py` runs as part
of `validate_all.py`.

## Writing a build script

Copy [`templates/cad/build_model.py`](../templates/cad/build_model.py) to the
module's `cad/` directory and replace `build()`. That is the only file a module
owns. The transaction handling, save discipline and fingerprinting — the parts
that make the open-file workflow safe — live in `doqs/scripts/` and reach the
seed through a short upward walk to the submodule:

| Lives in the module | Lives in `doqs/scripts/` |
| --- | --- |
| `cad/build_model.py` — `build()`, the geometry | `cad_build.py` — transactions, save discipline, `main()` and `run()` |
| `cad/params/*.csv`, `cad/*.FCStd` | `cad_fingerprint.py` — measurement |
| | `cad_sync_params.py` — CSV → Spreadsheet |

Tools stay in the submodule so a fix reaches every module on the next
`git submodule update --remote`. `validate_cad.py` fails on a per-module copy.

### The last line of a build script

A build script ends with this line, and with nothing around it:

```python
main(build, globals(), cad_dir=_HERE)
```

Do not put it under `if __name__ == "__main__":`. FreeCAD 1.1 runs a script with
`FreeCADCmd cad/build_model.py` and sets `__name__` to the file name without its
suffix, here `build_model`. The test is then false, and the run builds nothing,
prints nothing and exits 0. You would commit an old model and believe it is new.

`main()` builds unless the file is being imported. It works the same from
`FreeCADCmd`, from `python`, and from the FreeCAD console. Two checks catch the
old ending:

* When a headless FreeCAD run imports `cad_build` and ends without a finished
  build, it prints `ERROR: this FreeCADCmd run built nothing` and exits 1. That
  also covers a build that raised an error, because FreeCADCmd does not always
  exit with a failure code.
* `validate_cad.py` fails a build script that still holds the old guard.

### Own models in a parts library

A parts library keeps the models we draw ourselves under `cad/own/`, several in
one folder. Each one has its own build script, `cad/own/<pn>.build.py`, copied
from [`templates/parts-library/cad/own/build.py`](../templates/parts-library/cad/own/build.py).
The script's name tells `main()` which `<pn>.FCStd` to open and which
`<pn>.params.csv` to read. Run it from the library root:

```powershell
FreeCADCmd modules/hiwin/modules/hgr-rail/cad/own/HGR20R1000.build.py
```

The rest of the rules are in [parts-library.md, Our own models](parts-library.md#our-own-models).

### Migrating a module created before this split

1. Delete `cad/fingerprint.py` and `cad/sync_params.py`.
2. Re-seed `cad/build_model.py` from the template, pasting your `build()` body
   back in. A pre-split file is the one containing `def open_document(`.
3. Run `python doqs/scripts/validate_cad.py` — it names anything left over.

Nothing about the `.FCStd`, the fingerprint format or the commands changes;
`FreeCADCmd cad/build_model.py` is still the headless rebuild.

### The model tree of a part

The top object of a part is a Part container (`App::Part`). The Body sits inside
it. An Assembly inserts and places a part as one object, and the Part container
is that object.

Do not create the Body yourself. Use the two helpers that the seed imports:

```python
def build(doc, params):
    shape = body(doc)          # a Body inside part(doc), created on the first run
    ...
```

`part(doc)` returns the Part container and creates it if it is missing.
`body(doc)` returns a Body inside that Part. A rerun reuses both. An older
document with a Body at the top is repaired: `body(doc)` moves that Body into the
Part.

New objects open visible. When a build creates a Part, a Body, an Assembly, a
link to a part, a solid imported from a STEP file, or a mounting frame, it
switches that object on, together with the last feature of each new Body. The
coordinate system of a Part, a Body or an Assembly (the origin axes, planes
and point) stays hidden. A mounting frame shows its axes and planes, because
they are the frame. Objects that existed before the build keep the visibility
you gave them. Visibility is stored in the document itself, so a headless
build gets it right too. See
[ADR-014](decisions/2026-10-07_imported-solids-and-frames-visible.md).

The rule is checked twice. `run()` stops and undoes the build when a Body is left
outside a Part, so the mistake never reaches your screen or the file.
`validate_cad.py` fails a committed part file with a Body at the top. Assembly
files are not checked: a file under `cad/assemblies/`, or a file that holds an
Assembly, keeps its master sketches in a Body inside a plain group (see
[ADR-002](decisions/2026-06-24_freecad-master-sketches-body.md)). The reasons
are in [the decision](decisions/2026-10-01_part-container-on-top.md).

For assembly-driven parts, master sketches belong in a
dedicated `Body_master` constrained to that Body's own origin planes — see
[ADR-002](decisions/2026-06-24_freecad-master-sketches-body.md).

### Every dimension has a reason

A number typed into a sketch links to nothing. When the reason behind it
changes, nobody knows that this number must change too. So every size in a model
is linked, and every link ends at a reason
([ADR-012](decisions/2026-10-06_every-dimension-has-a-source.md)).

**1. Write the parameter table first.** Before you draw, list the sizes the part
needs in `cad/params/default.csv`. Sort them into two kinds:

* **Independent** — a number someone chose. Fill `basis` and `source`: a SysML
  requirement, a supplier document, a standard, a simulation file, or a design
  choice with a reason. If no reason exists yet, ask the user. Do not invent one.
* **Derived** — everything else, written as a formula: `=plate_w - 2 * edge_margin`.

Keep the independent rows few. Eight holes at one pitch are two rows
(`hole_count`, `hole_pitch`), not eight positions.

**2. Fully constrain every sketch.** Nothing may move. Use relations first
(coincident, horizontal, vertical, equal, symmetric, tangent), then dimensions.
A relation needs no number; that is one less number to link.

**3. Never type a number into a dimension.** Every driving dimension and every
feature size is an expression: `Params.<alias>`, a formula of aliases, or a
named dimension in another sketch. Use the two helpers from `cad_build`:

```python
def build(doc, params):
    shape = body(doc)
    sk = shape.newObject("Sketcher::SketchObject", "HoleSketch")
    ...                                           # one circle
    dim(sk, Sketcher.Constraint("Diameter", 0, 1.0), "Params.hole_d")
    dim(sk, Sketcher.Constraint("DistanceX", -1, 1, 0, 3, 1.0), "Params.hole_edge")
    ...
    pattern = shape.newObject("PartDesign::LinearPattern", "Holes")
    bind(pattern, "Occurrences", "Params.hole_count")
    bind(pattern, "Length", "(Params.hole_count - 1) * Params.hole_pitch")
```

Only zero, a full turn (360°) and a single copy need no parameter.

**4. Know which dimension drives.** A driven value is a formula or a reference
dimension (a dimension that shows a value and drives nothing). It is never a
second typed number that happens to agree.

**5. Repeated features are patterns.** Draw one hole and pattern it. Or, in one
sketch, tie the copies with `Equal` and dimension one of them. Never give each
spacing its own number.

**6. Check it.** Every build prints the sketches that can still move and the
sizes that are typed numbers. The fingerprint records them under `parametric`:

```json
"parametric": {
  "audited": 6,
  "objects": {
    "Sketch001": {
      "type": "Sketcher::SketchObject", "label": "HoleSketch", "dof": 0,
      "unlinked": ["Constraint4 (DistanceX) is a typed number: 20 mm"]
    }
  }
}
```

A clean model has an empty `objects`. `validate_cad.py` reports what is left, and
`validate_variants.py` reports a parameter without a reason. Both warn by default.
A repository that has cleaned up adds `--strict-parametric` to its CI, so the
warnings become failures:

```powershell
python doqs/scripts/validate_all.py --strict-parametric
```

The check reads FreeCAD properties by name. It knows sketches, datums and the
usual PartDesign features (pad, pocket, hole, fillet, chamfer, revolution,
patterns, primitives); the list is in
[`scripts/parametric_rules.py`](../scripts/parametric_rules.py).

### Joints attach to mounting frames

A joint that holds a face, an edge or a point of a solid breaks when that solid
changes: FreeCAD numbers the faces again, and the part jumps or the joint fails.
So a part offers named mounting frames, and every joint attaches to those
([ADR-013](decisions/2026-10-06_joints-attach-to-frames.md)).

**In the part.** Add one frame for each place where another part attaches.
Place it with the same parameters as the holes or the face it stands for, so it
moves when they move:

```python
def build(doc, params):
    shape = body(doc)
    ...
    frame(doc, "IF_mount_bottom", x="Params.rail_l / 2")
    frame(doc, "IF_carriage", x="Params.carriage_x", z="Params.rail_h")
    frame(doc, "IF_motor", y="Params.motor_y", angle="Params.motor_a", axis=(1, 0, 0))
```

`frame()` creates a coordinate system (`Part::LocalCoordinateSystem`) inside the
Part container, shows it with its axes, and reuses it on a rerun. The label
must start with `IF_`. A supplier part gets its frames in our part file around
the supplier geometry, placed from catalogue values.

A part may keep its build script beside its model, in
`cad/parts/<part>/build_model.py`. The script still reads the module's
`cad/params.csv`, and `validate_cad.py` checks it like the one in `cad/`.

`doqs add-interface` adds the frames for you: a port `referenceRailMount` on
a part means the frame `IF_reference_rail_mount` in that part's file
([ADR-015](decisions/2026-10-07_port-and-frame-share-a-name.md)). It puts a
`frame()` call into the build script and the frame into the saved document,
at the origin. You then place it. `doqs wrap` gives a supplier part its
frames the same way, in the FreeCAD window so the brand's colours survive
([ADR-017](decisions/2026-10-07_step-import-in-the-gui.md)).

`validate_cad.py` also reports a coordinate system whose label does not
start with `IF_`, and a joint that ends on anything but a frame, following
the joint into the linked file. `validate_interfaces.py` reports a port
without its frame and a frame without its port. Both warn until the
repository turns them on with `--strict-parametric` and `--strict-interfaces`.

**In the assembly.** Select the frame, or one of its axes or planes, for each
side of a joint. Never a face, an edge or a point. If a joint needs an offset,
drive it by an expression over `Params`. For a part that never moves, a
placement driven by an expression is allowed, but it reads the placement of a
frame and the part has no joints.

**Frame names are an interface.** Adding a frame is safe. Renaming or removing
one breaks every assembly that uses it, so it needs a new major version of the
module.

`validate_cad.py` reads the joints from the saved file and names each one that
uses a face, an edge or a point. It warns by default and fails with
`--strict-parametric`.

## A note on topological naming

Earlier guidance treated the topological naming problem as a reason to avoid
letting agents edit features in place. That is overstated for FreeCAD 1.1: TNP
was substantially fixed by the new naming algorithm in 1.0, which identifies
broken references and often proposes a repair. Edge cases remain and some newer
features do not use the algorithm yet, but it is not a reason to avoid live
editing. Clobbering was the real problem, and the guard above is what solves it.
