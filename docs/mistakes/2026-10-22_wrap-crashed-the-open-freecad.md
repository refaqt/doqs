# 2026-10-22 — Adding a part crashed the open FreeCAD window, and the checks looked in the wrong library

## What happened

In aqtuator, an agent added the ACE TA17-7 end stop damper to the parts library. Three doqs
problems stopped it on the way:

1. `doqs wrap` closed the user's open FreeCAD window, twice, with no message. Work that was not
   saved was at risk both times.
2. After that, the wrap still failed on the TA17-7 STEP file with "Cannot add a group object to
   itself". The agent built the wrapper by hand.
3. `bash doqs.sh check` in aqtuator said the damper family did not exist. It looked for it in a
   test fixture inside `doqs/`, not in the real library at `modules/stoq`.

While fixing the first two, a fourth problem showed up: an open FreeCAD window kept the doqs code
it had loaded earlier in the day. A fixed doqs ran the old, broken code in that window.

## Why it went wrong

1. doqs sent its work to the open window with the add-on's background call. That call runs on a
   second thread. FreeCAD only allows document work on its main thread, so it crashed. The
   2026-10-07 tests used a FreeCAD window started for the job, never the open window.
2. When the importer makes its own Part, the Part's axes and planes are not in its list of
   children. doqs counted them as more top objects and tried to put the Part inside itself. The
   test stand-in for FreeCAD had no axes, and it allowed a Part inside itself.
3. The library search walked the whole machine folder, `doqs/` too. doqs carries test fixtures
   that look like libraries, and `doqs/...` sorts before `modules/...`.
4. Python keeps a module once it is loaded. FreeCAD stays open for days.

## What we changed

doqs now runs its work on FreeCAD's main thread, ignores the axes and planes of an imported Part,
skips libraries inside `doqs/` and `.agents/`, and loads its code fresh each time it runs in the
open window. Each fix has a test. The test stand-in for FreeCAD now behaves like FreeCAD in both
points that hid problem 2.

## Rule

Test every command that talks to the open FreeCAD window against a real open window, with a
document already open, before you call it done. A test against a window started for the job does
not cover it.

<details>
<summary>Technical notes</summary>

- `scripts/freecad_rules.py` `rpc_run()` called `execute_code_async`. The add-on runs that on a
  worker thread (`rpc_server.py`, `execute_code_async`); document writes from there must go
  through `commit()`. The wrap macro called `newDocument`, `ImportGui.insert`, `saveAs` and
  `closeDocument` directly. FreeCAD 1.1.4 crashed.
- The async path could never succeed anyway: `get_async_status` answers
  `{"success": True, "job": {"state": ...}}`, but `rpc_run()` read a top-level `status` key, and
  the worker does not capture `print`, so `DOQS_MACRO_DONE` never came back.
- Real import of `TA17-7.step` gives `TA17_7` (`App::Part`) holding one `Part::Feature`, plus
  `Origin`, three `App::Line`, three `App::Plane` and one `App::Point`, none of them in `Group`.
- The aqtuator note of the same day:
  `aqtuator/docs/mistakes/2026-10-22_wrap-crashed-the-open-freecad.md`.

</details>
