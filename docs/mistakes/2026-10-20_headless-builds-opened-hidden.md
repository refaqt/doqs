# 2026-10-20 — Models built without the FreeCAD window opened hidden

## What happened

The aqtuator compact stage links the LAMOTION ALZ scale and the RUS-ET end
clamps from the stoq parts library. In the assembly both parts were invisible,
and the shape of each link was empty. The two HIWIN own models in stoq (rail
`HGR15R418H` and block `HGL15CAZBC+E2`) open hidden in the same way.

All four were built headless, with `FreeCADCmd` and `cad_build.run()`. The
build switches every new Part, Body and frame on, and Document.xml stores that.
But the FreeCAD window does not read visibility from Document.xml. It reads it
from the view data in the file (`GuiDocument.xml`). A save without the window
writes no view data. When the window opens such a file, it hides every object
and sets `Visibility = False` on each of them too.

Without the window, the files looked right: every object was visible, and a
link to each part had its full volume. Only the window showed the problem.

stoq fixed the two LAMOTION models by building them again inside the window,
in [refaqt/stoq#18](https://github.com/refaqt/stoq/pull/18).

## Why it went wrong

1. ADR-014 and `docs/agent-cad.md` said that visibility is stored in the
   document, so a headless build gets it right. Nobody tested that in the
   window.
2. Every check reads the file without the window. They saw "visible" and
   passed.
3. Nobody opened a rebuilt own model in the window before it was merged.

## What we changed

`cad_build.save()` saves a document. After a save without the window, it adds
small view data to the file: one entry per object, with the visibility that
Document.xml stores. `run()`, `doqs add-interface`, the STEP wrapper, the part
scaffold and the parameter sync now all save through it.

`validate_cad.py` warns about a committed file without view data. With
`--strict-parametric` it fails.

## Rule

A rule about what a person sees must be tested in the FreeCAD window, not only
headless. When a tool saves a document, it saves through `cad_build.save()`.
