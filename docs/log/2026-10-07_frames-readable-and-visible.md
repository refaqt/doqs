# 2026-10-07 — Frames can be read from a saved file, and open visible

**Role(s):** software

## What happened

This is the first step of a larger piece of work: a design tool, called fabriq, that adds a
part to a machine in minutes instead of days. The plan is in the pull request that carries
this entry. Before the tool can create or check mounting frames, doqs must be able to read
them from a saved FreeCAD file without FreeCAD, and a build must show them.

Work done:

- doqs reads the label of every object, the list of mounting frames, the file each link
  points to, and the object each assembly joint ends on, straight from a saved `.FCStd`.
  A joint stores the internal name of a frame (`Frame001`); the new readers turn that into
  its label (`IF_rail_reference`) and the file it lives in. No FreeCAD is needed, so a
  validator can use them in CI.
- A build now shows an imported supplier solid, and shows a new mounting frame with its
  axes and planes. Before, both opened hidden. The origin of a container stays hidden.
  See [ADR-014](../decisions/2026-10-07_imported-solids-and-frames-visible.md).
- A part can keep its build script beside its model in `cad/parts/<part>/`. The script
  still reads the module's `cad/params.csv`. Before, it looked for a parameter file in its
  own folder and found nothing. The check for the FreeCADCmd guard now finds those scripts
  too.

## Decisions

- [ADR-014 — An imported solid and a mounting frame open visible](../decisions/2026-10-07_imported-solids-and-frames-visible.md)

## Next Steps

- A SysML reader and editor for the subset of SysML v2 in use, so a tool can add ports,
  parts and connections without hand edits.
- Commands that take a supplier part into the parts library, wrap its STEP file with
  colours and frames, and use it in a machine module.
- Validators for frames: every frame label starts with `IF_`, every joint ends on a frame,
  and every SysML port has its frame.

<details>
<summary>Technical notes</summary>

- New readers in `scripts/cad_rules.py`: `object_labels()`, `frames()`, `link_targets()`,
  `joint_targets()`, `resolve_joint_target()`. `FRAME_TYPE` moved up so `SHOWN_TYPES` can
  name it; `IMPORTED_SOLID_TYPE` is new.
- `scripts/cad_build.py`: `_show_frame()`, `module_cad_dir()`; `show_new_objects()` treats
  the axes of a new frame as part of the frame; `params_path()` walks up to the module's
  `cad/`; `frame()` shows a frame it creates.
- `scripts/validate_cad.py`: `legacy_tool_copies()` also scans `cad/parts/*/build_model.py`.
- Tests: `tests/test_cad_rules.py` (`TestFrameReaders`, visibility), `tests/test_cad_build.py`
  (`TestParamsPath`, frame visibility, per-part guard check). One pre-existing test,
  `test_seed_bootstrap_finds_doqs_scripts`, fails on this Windows account because it creates
  a symbolic link; it fails the same way on `main`.

</details>
