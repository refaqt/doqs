# 2026-10-01 — New parts get a Part container on top

**Role(s):** software

## What happened

When an agent creates a FreeCAD part, the top object of the model tree is now a
Part container, with the Body inside it. Before, agents often put the Body at the
top, and a person had to wrap it by hand before the part fitted into an assembly.

Work done:

- The build tools give agents one call that returns a Body inside a Part
  container. It creates both on the first run and reuses them after that.
- A build that leaves a Body at the top stops, and the change is undone.
- The CAD check in CI fails a saved part file with a Body at the top.
- Assembly files are not checked. They keep their master sketches in a Body
  inside a plain group, as an earlier decision says.
- The build script template, `docs/agent-cad.md` and `docs/architecture.md`
  describe the rule. 21 new tests cover it. They need no FreeCAD to run.

## Decisions

See [ADR-010](../decisions/2026-10-01_part-container-on-top.md). The rule fails
the build instead of printing a warning, because a warning is easy to miss.

## Next Steps

Machine repositories pick this up with their usual tools update. An older part
with a Body at the top then fails the CAD check. One rebuild repairs it.

## Related

- [ADR-010](../decisions/2026-10-01_part-container-on-top.md)
- [ADR-002](../decisions/2026-06-24_freecad-master-sketches-body.md)
- [agent-cad.md, The model tree of a part](../agent-cad.md#the-model-tree-of-a-part)
