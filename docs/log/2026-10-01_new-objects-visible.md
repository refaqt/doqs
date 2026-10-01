# 2026-10-01 — New parts and assemblies open visible

**Role(s):** software

## What happened

When an agent built a new FreeCAD part or assembly, every object opened hidden.
A person had to switch each one on by hand. Now the build switches them on.

Work done:

- A new Part, Body, Assembly, or link to a part is visible after a build. The
  last feature of a new Body is visible too, so the solid shows on screen.
- The coordinate system of each one (the origin axes, planes and point) stays
  hidden.
- Only new objects change. An object a person hid on purpose stays hidden on
  the next rebuild.
- This works in the open FreeCAD window and in a headless build, because the
  setting is saved in the file.
- `docs/agent-cad.md` and the build script template describe the rule. New
  tests cover it. They need no FreeCAD to run.

## Decisions

No new decision record. The build only sets visibility on objects it creates,
so it never overrides a choice a person made.

## Next Steps

Not yet checked in a real FreeCAD. Rebuild a new part with
`FreeCADCmd cad/build_model.py`, open it, and check that the part shows and the
axes and planes do not.

## Related

- [agent-cad.md, The model tree of a part](../agent-cad.md#the-model-tree-of-a-part)
- [2026-10-01 — New parts get a Part container on top](2026-10-01_part-container-on-top.md)
