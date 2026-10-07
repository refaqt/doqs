# 2026-10-07 — Six commands add a part to a design without hand work

**Role(s):** software

## What happened

The third step of the fabriq work. The steps a person did by hand to add a part, across
three repositories, are now commands. Each one writes what the rules ask for, says what it
did, and changes nothing on a rerun.

- `doqs scaffold` creates a module, an own part, a library brand or a library family with
  every folder and file the gates expect. An own part gets an empty FreeCAD document with a
  Part container and a `Params` sheet, made by FreeCAD.
- `doqs add-part` takes a supplier's part into the private library and then the public one:
  files at their paths, rows with checksums, the terms review, the evidence copy, and the
  `.gitignore` lines for a file that may not be shared.
- `doqs wrap` builds the FreeCAD wrapper from the STEP file in a FreeCAD window, so the
  brand's colours survive, with a Part on top, visible objects and `IF_` frames. It sets the
  `cad` cell of the row and mirrors the wrapper to the other library when allowed.
- `doqs use-part` puts a library part into a machine module: a BOM row with the next free
  id, a `[[bought-part]]` entry, a SysML part def and usages. It can move the library pin,
  but only to a commit that is on the library's main branch.
- `doqs add-interface` adds one interface from one request: the SysML port def, the two
  ports, the connection, the `okh.toml` entry, and a mounting frame in each part file, with
  the names one rule gives them.
- `doqs mirror` compares the public and the private library file by file.

Two checks came with them. `validate_cad.py` now reports a coordinate system without an
`IF_` name and a joint that ends on anything but a frame. The new `validate_interfaces.py`
reports where SysML ports, `okh.toml` entries and frames disagree. Both warn until a
repository turns them on.

## Decisions

- [ADR-016 — Two new script verbs: `add_` and `use_`](../decisions/2026-10-07_add-and-use-verbs.md)
- [ADR-017 — A STEP file is imported in the FreeCAD window, never headless](../decisions/2026-10-07_step-import-in-the-gui.md)
- [ADR-018 — A new check warns first](../decisions/2026-10-07_new-checks-warn-first.md)

## Checked on a real FreeCAD

`doqs wrap` ran once on this Windows machine against a copy of the private library, with
FreeCAD 1.1 starting a window for the job because the open window had no RPC server. It
took 13 seconds. The saved document has one Part container on top labelled with the part
number, the HIWIN block visible with its 22 colour entries kept, two frames visible with
their axes, the container's own coordinate system hidden, and the window closed itself.

## Next Steps

- Run the rest of the chain by hand once: use the block in the compact stage, add the
  block-to-carriage interface, open the pull requests.
- Rename the two frames in the aqtuator base to the names their ports give them.
- Build fabriq on top of these commands.

<details>
<summary>Technical notes</summary>

- `scripts/install_module.py`, `add_part.py`, `export_wrapper.py` with `cad_wrap_step.py`,
  `use_part.py`, `add_interface.py`, `validate_mirror.py`, `validate_interfaces.py`.
- `scripts/freecad_rules.py`: `find_freecad()`, `rpc_available()`, `rpc_run()`,
  `render_macro()`, `run_macro()` with modes `auto`, `rpc`, `gui`, `cmd`.
- `scripts/report_rules.py`: the one report shape, text or JSON.
- `scripts/validate_cad.py`: `frame_findings()`, `report_frames()`.
- `scripts/cli.py`: `ADVISORY`, six `PASSTHROUGH` entries, `--strict-interfaces`.
- `tests/freecad_stub/`: `newDocument`, `addObject` with unique names, `saveAs`,
  `ImportGui.insert`, `FreeCADGui.getMainWindow().close()`.
- Tests: `test_install_module.py`, `test_add_part.py`, `test_use_part.py` (with a real
  submodule and remote for the pin bump), `test_add_interface.py`,
  `test_validate_interfaces.py`, `test_frame_gate.py`.

</details>
