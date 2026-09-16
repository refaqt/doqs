# ADR — what `export_variant.py` promises

- **Date:** 2026-09-16
- **Status:** Accepted

## Context

`export_variant.py` produces geometry for one composition × model on demand. It
drives FreeCAD through a **generated macro** — written to a temporary file and
handed to a separate `FreeCADCmd` process. That makes it the one piece of this
repository unreachable by importing a module, and it had **no test coverage**:
CI byte-compiled it and nothing more.

[ADR: CAD tools live in doqs](2026-09-16_cad-tools-in-doqs.md) fixed a path bug
in that macro — `exec(open(sync).read())` left `__file__` pointing at the temp
file, so `params.csv` resolved to `/tmp/params.csv`. That change was correct but
was never executed, and it turned out to be one of four defects on this path:

1. **Parameters were resolved against the `--module` directory.** A composition
   is thin by design: no `cad/` at all, and an `okh.toml` naming the core that
   holds the numbers. So the command printed in `variants.md` — the documented,
   primary invocation — exited 1 with a `ParamError` before FreeCAD was reached.
   The feature had never worked for the case it exists for.
2. **The macro saved the document it opened.** `sync_active()` ends in
   `doc.save()`, so every export wrote the committed `.FCStd`: a dirty working
   tree, a `validate_cad.py --check-clean` failure, and the FreeCAD #8924
   overwrite hazard that `cad_build.run()` is careful to avoid.
3. **A stale output file reported success.** `not out.exists()` is satisfied by
   a leftover STEP from an earlier run, and FreeCADCmd does not reliably exit
   non-zero when a macro raises.
4. **The export rewrote the active model.** It shelled out to
   `resolve_params.py --model <model>`, which writes `<module>/cad/params.csv` —
   so exporting `500mm` switched the model someone was working at, and (once
   defect 1 was fixed) wrote into the family checkout that `variants.md`
   promises is never written to.

## Decision

1. **A composition's parameters resolve through its core**, via a new
   `param_rules.params_owner()`. A module owning `cad/params/default.csv` comes
   back unchanged, so the traversal is a no-op for every existing caller.
   *Rejected:* giving each composition its own `cad/params/`, which duplicates
   the numbers the family exists to share; and reusing
   `resolve_instance.targets()`, which starts from an `[instance]` manifest and
   cannot be called with what `--module` gives you. It lives in `param_rules`
   rather than `naming_rules` because it raises `ParamError`, which callers
   already render with the `FAIL` convention.
2. **The macro never saves.** `sync_active()` gains `save=True`; the macro
   passes `save=False`. The default keeps the FreeCAD-console flow byte-for-byte
   unchanged. `sync_table()` is deliberately *not* given the same keyword: its
   only documented caller is the console, where the saving process is the one
   holding the document — that is Ctrl+S, not the #8924 hazard.
3. **A staged file decides success, not an exit code.** FreeCAD writes into a
   temporary directory beside `--out`; the result is moved into place with
   `os.replace` only when it exists and is non-empty. The macro also refuses to
   export an empty object list, which would otherwise produce a valid, empty
   STEP that passes every check.
4. **The active parameter set is resolved into staging, never into the module.**
   `resolve_params.render_active()` already returns exactly the bytes the
   resolver would write, so there is one renderer and no second writer. This
   also removes the `subprocess(..., check=True)` that used to surface as a raw
   `CalledProcessError`.
5. **A FreeCAD stub enters the test suite**, at `tests/freecad_stub/`. This is a
   new convention: until now FreeCAD was imported lazily so the pure-Python
   halves stayed testable, and there was no fake anywhere. A macro has no
   pure-Python half — it only exists as text handed to another process — so the
   stub is what makes it reachable at all. It is loaded only through a child
   process's `PYTHONPATH` (or an explicit `sys.modules` patch), so it cannot
   shadow the real module, and `tests/freecad_stub/` carries no `__init__.py`,
   so discovery skips it. Its scope is deliberately narrow: it asserts *DOQS*
   behaviour — which file was read, which aliases were written, where the STEP
   went, whether `save()` was called — and never FreeCAD behaviour.

## Consequences

**The documented command works.** `tests/test_export_variant.py` runs the
literal invocation from `variants.md`, and a second test loops over every
`[composition]` module in the fixture, so a new composition cannot be added
without the export path resolving for it.

**Exporting is now side-effect free.** The source `.FCStd` is unchanged, no
`params.csv` is written into the family, and a failed run leaves a pinned
`builds/<id>/` export byte-identical. Each of those is a named test, and each
was confirmed to fail against a faithful revert of its fix — not merely to pass.

**The stub is the pattern for any future FreeCAD-facing macro.** Its drift risk
is real: it can only stay honest if it is kept minimal, which is why no `Mesh`
stub was added for an import that no longer exists.

**Open question, recorded rather than guessed.** `sync_active()` requires a
`Params` spreadsheet in the document it is given. The **core** carries that
sheet; whether a *composition* assembly does — or whether a composition export
should instead set `Configuration` on its Variant Links — needs a real document
to decide. Until then the export fails legibly with *"No Spreadsheet named
'Params'"*, and a test pins that behaviour so it cannot become a silent one.

**Correcting the record:** [2026-09-16_cad-tools-in-doqs.md](2026-09-16_cad-tools-in-doqs.md)
says "A latent bug is fixed" of this path. That change fixed one of the four
defects above and was never executed; the other three survived it.
