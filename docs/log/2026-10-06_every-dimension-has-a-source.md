# 2026-10-06 — Every dimension now has a reason

**Role(s):** software

## What happened

Models built by agents had sketches that could still move, and sizes typed in
as numbers that linked to nothing. doqs now asks for a reason behind every size
and checks that the model uses it. The incident is in
[the mistake log](../mistakes/2026-10-06_unlinked-dimensions.md).

Work done:

- Parameter files have two new columns, `basis` and `source`. Every independent
  value says where it comes from: a SysML requirement, a supplier part, a
  standard, a simulation or a design choice. A derived value is a formula and
  needs no reason of its own. The check makes sure a named requirement exists
  in the SysML model and a named simulation file exists.
- Every build now looks inside the model. It lists each sketch that can still
  move and each size that is a typed number. The list goes into the fingerprint
  and is printed at the end of the build.
- The CAD check and the product family check report these findings. They are
  warnings for now, so machine repositories keep passing when they update doqs.
  A new switch, `--strict-parametric`, turns them into failures. doqs's own
  examples already pass with it.
- Two short helpers make linked dimensions easy to write: `dim()` for sketch
  dimensions and `bind()` for feature sizes.
- 25 new tests. The model check is tested on stand-in objects, not on a real
  FreeCAD.

## Decisions

See [ADR-012](../decisions/2026-10-06_every-dimension-has-a-source.md).

## Next Steps

Rebuild one real part in qarve with FreeCAD 1.1 and read its `parametric`
section, to confirm the property names the check reads. Then fill `basis` and
`source` in qarve's parameter files, fix the warnings, and add
`--strict-parametric` to its CI.

## Related

- [agent-cad.md, Every dimension has a reason](../agent-cad.md#every-dimension-has-a-reason)
- [architecture.md, Parameter File Format](../architecture.md#parameter-file-format)
