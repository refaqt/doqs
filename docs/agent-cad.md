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
| Windows | `%APPDATA%\FreeCAD\Mod\` |
| macOS (1.1) | `~/Library/Application Support/FreeCAD/v1-1/Mod/` |
| Linux, Debian | `~/.local/share/FreeCAD/Mod/` |
| Linux, Arch (1.1) | `~/.local/share/FreeCAD/v1-1/Mod/` |
| Linux, Flatpak | `~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod/` |

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force "$env:APPDATA\FreeCAD\Mod"
Copy-Item -Recurse addon\FreeCADMCP "$env:APPDATA\FreeCAD\Mod\"
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

Centre of mass earns its place by catching mirrored and rotated parts whose
volume, area and bounding box are all unchanged.

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
| `cad/build_model.py` — `build()`, the geometry | `cad_build.py` — transactions, save discipline, `run()` |
| `cad/params/*.csv`, `cad/*.FCStd` | `cad_fingerprint.py` — measurement |
| | `cad_sync_params.py` — CSV → Spreadsheet |

Tools stay in the submodule so a fix reaches every module on the next
`git submodule update --remote`. `validate_cad.py` fails on a per-module copy.

### Migrating a module created before this split

1. Delete `cad/fingerprint.py` and `cad/sync_params.py`.
2. Re-seed `cad/build_model.py` from the template, pasting your `build()` body
   back in. A pre-split file is the one containing `def open_document(`.
3. Run `python doqs/scripts/validate_cad.py` — it names anything left over.

Nothing about the `.FCStd`, the fingerprint format or the commands changes;
`FreeCADCmd cad/build_model.py` is still the headless rebuild.

Prefer driving dimensions through Spreadsheet aliases
([Linking CSV Parameters to FreeCAD](architecture.md#linking-csv-parameters-to-freecad))
over hard-coding them. For assembly-driven parts, master sketches belong in a
dedicated `Body_master` constrained to that Body's own origin planes — see
[ADR-002](decisions/2026-06-24_freecad-master-sketches-body.md).

## A note on topological naming

Earlier guidance treated the topological naming problem as a reason to avoid
letting agents edit features in place. That is overstated for FreeCAD 1.1: TNP
was substantially fixed by the new naming algorithm in 1.0, which identifies
broken references and often proposes a repair. Edge cases remain and some newer
features do not use the algorithm yet, but it is not a reason to avoid live
editing. Clobbering was the real problem, and the guard above is what solves it.
