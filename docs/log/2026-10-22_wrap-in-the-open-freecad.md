# 2026-10-22 — Wrapping a part works in the open FreeCAD window, and checks find the real library

**Role(s):** cad, software

## What happened

`doqs wrap` can now build a part wrapper in the FreeCAD window you have open, without closing it.
We ran it for the ACE TA17-7 damper in a window with fourteen open documents. The wrapper was
saved, and all fourteen documents were still open afterwards.

`bash doqs.sh check` in a machine repository no longer looks for parts in the test fixtures that
doqs carries. In aqtuator, the false "no family 'ace/ta-damper'" error is gone.

Four problems were fixed. The mistake note
[Adding a part crashed the open FreeCAD window](../mistakes/2026-10-22_wrap-crashed-the-open-freecad.md)
explains each one.

## Next Steps

- Move aqtuator's `doqs/` submodule to this fix after it is merged.
- In aqtuator, `bash doqs.sh check` still fails for two other reasons, not touched here:
  `validate_names.py` crashes on Windows when it prints a `→`, and four compact-stage parts were
  saved after their build and need a rebuild.
- On this Windows checkout, 49 doqs tests fail on `main` already (checksums, path slashes, shell
  hooks). They are not caused by this work.

<details>
<summary>Technical notes</summary>

- `scripts/freecad_rules.py`: `rpc_run()` uses only `execute_code` (GUI thread). The add-on stops
  waiting after about 90 s; a longer job needs `--mode gui`. `render_macro()` drops every cached
  module named like a file in `scripts/` before the body runs.
- `scripts/cad_wrap_step.py`: `wrap()` leaves `cad_rules.ORIGIN_TYPES` out of the top objects.
- `scripts/naming_rules.py`: `_library_roots_cached()` skips markers under `doqs/` or `.agents/`
  (`is_under_tooling_submodule`). `validate_variants.py`, `validate_names.py` and `use_part.py`
  all use it.
- Test stand-in: `tests/freecad_stub/ImportGui.py` takes a `container` key and makes a Part with
  an Origin outside `Group`; `_Object.addObject` refuses the object itself, as FreeCAD does.
- New tests: `tests/test_freecad_rules.py` (fake RPC server; macro header),
  `TestWrap.test_the_importers_own_part_becomes_the_wrapper`,
  `TestLibrariesInToolingAreSkipped`. Each one fails without its fix.
- Real run: `export_wrapper.py --library <scratch copy of stoq/modules/ace> --part
  ace/ta-damper#TA17-7 --frames IF_mount --mode rpc` against FreeCAD 1.1.4. The first try failed
  with the old `cad_wrap_step` still loaded in the window; that found problem 4.

</details>
