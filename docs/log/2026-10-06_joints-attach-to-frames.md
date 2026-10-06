# 2026-10-06 — Assembly joints now attach to named mounting frames

**Role(s):** software

## What happened

Assemblies broke too often after small design changes, because joints held
single faces of a part. doqs now asks every part to offer named mounting
frames, and every joint to attach to those. The incident is in
[the mistake log](../mistakes/2026-10-06_joints-on-faces.md).

Work done:

- A new rule, with the reasons and the ways we compared: joints attach to named
  mounting frames, placed by the parameter sheet. A frame name is part of the
  module's interface.
- The CAD check now reads every joint in a saved assembly and names each one
  that uses a face, an edge or a point. It is a warning for now, so machine
  repositories keep passing when they update doqs. The existing strict switch,
  `--strict-parametric`, turns it into a failure. It needs no FreeCAD, so it
  runs in CI.
- A short helper, `frame()`, creates a mounting frame inside the part and
  places it by expressions. The build templates show how to use it.
- The model check now also looks at the placement of a mounting frame, so a
  typed number there is reported like any other.
- 10 new tests. The joint check is tested on small saved files built like the
  ones FreeCAD 1.1 writes, not on a real assembly.

## Decisions

See [ADR-013](../decisions/2026-10-06_joints-attach-to-frames.md).

## Next Steps

- Run the check on a real qarve assembly saved by FreeCAD 1.1, to confirm it
  reads the joints. Then add frames to the parts and move the joints to them.
- Later, record the final position of each part in an assembly fingerprint, so
  a part that moved without a parameter change shows up in review.

## Related

- [agent-cad.md, Joints attach to mounting frames](../agent-cad.md#joints-attach-to-mounting-frames)
- [naming.md, Mounting frame names](../naming.md#mounting-frame-names)
