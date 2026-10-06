# ADR-012 — Every dimension has a reason, and the model links to it

- **Date:** 2026-10-06
- **Status:** Accepted
- **Works with:** [ADR-002 master sketches live in a separate Body](2026-06-24_freecad-master-sketches-body.md),
  [ADR-011 an own model is our design](2026-10-02_own-models-are-our-designs.md)

## Context

Agents that built FreeCAD models left sketches that were not fully constrained.
They also typed numbers into dimensions, and those numbers linked to nothing.
A row of 8 holes got 7 typed spacings. To change the pitch, someone had to find
and change 7 numbers, and nothing said that the 7 belonged together.

Every dimension of a machine has a reason. It comes from a requirement, from a
part we buy, from a standard, from a calculation or simulation, or from a choice
a designer made. doqs already had the pipe for this: `cad/params/default.csv`,
derived values written as `=` formulas, and the `Params` sheet in FreeCAD. But
nothing asked for the reason, and nothing checked that the model used the sheet.

## Decision

1. **Independent and derived values.** A parameter file holds two kinds of rows.
   An *independent* row is a number someone chose. A *derived* row starts with
   `=` and is a formula over other rows. Use as few independent rows as you can.
2. **Every independent row says where it comes from.** Two new columns,
   `basis` and `source`:

   | basis | source holds |
   | --- | --- |
   | `requirement` | the SysML requirement, like `Stage::TravelRequirement.travel_mm`; it must exist in an `architecture/*.sysml` file |
   | `catalogue`, `estimated`, `measured` | the supplier document and page, or who measured the part and when (same meaning as for own models) |
   | `standard` | the standard and size, like `ISO 4762 M6` |
   | `simulation` | the file under `simulation/` that gives the value; it must exist |
   | `design` | a file in `docs/decisions/`, or a short reason |

   A derived row leaves both empty: its formula is the reason. An override file
   such as `500mm.csv` may leave them empty too; it keeps the ones in
   `default.csv`. An agent asks the user before it invents a `design` value.
3. **Every sketch is fully constrained.** Nothing in it can move.
4. **Every dimension in the model is an expression.** A sketch dimension or a
   feature size reads `Params.<alias>`, a formula of those, or another
   dimension. Zero, a full turn (360°) and a single copy are the only numbers
   that need no parameter.
5. **Repeated features are patterns.** Draw one hole and pattern it, driven by a
   count and a pitch. In a sketch, tie the copies with `Equal` and give one of
   them the dimension. Never type the same spacing several times.
6. **The build measures it.** `cad_fingerprint.py` records, under
   `"parametric"`, each sketch that can still move and each size that is a
   typed number. The build prints the same list.
7. **Warn now, fail later.** `validate_variants.py` (sources) and
   `validate_cad.py` (sketches and sizes) report the findings as warnings.
   `--strict-parametric` on those two, on `validate_all.py` and on
   `doqs check` makes them failures. doqs's own worked examples run strict.

## Consequences

- A machine repository that updates doqs keeps passing. It sees warnings for
  every parameter without a source and for every fingerprint built with an older
  doqs. When the warnings are gone, its CI should add `--strict-parametric`.
- The generated `params.csv` files carry the two new columns, so the reason
  travels with the value into a resolved instance.
- The audit reads FreeCAD properties by name. Property names and modes change
  between FreeCAD releases, so the table in `scripts/parametric_rules.py` must
  be checked against a real document when FreeCAD changes. The unit tests use
  stand-in objects, not FreeCAD.
- Two new helpers in `cad_build.py` make the right way short to write:
  `dim(sketch, constraint, "Params.x")` and `bind(feature, "Length", "Params.x")`.
