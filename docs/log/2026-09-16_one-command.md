# 2026-09-16 — One command instead of nineteen

**Role(s):** software

## What happened

`scripts/` holds nineteen files a person can run. Nothing said which one, or in
what order. That is the second half of "I don't know which files should be run".

There is now one name:

```bash
bash doqs.sh check       # every gate, plus "are the generated files current?"
bash doqs.sh generate    # write every generated file, in the right order
bash doqs.sh list        # every command, and the scripts each one runs
```

`doqs.bat` is the same on Windows. Both call `python doqs/doqs.py`, which
dispatches from `scripts/cli.py`.

`install_root_tools.py` copies the two launchers to a consumer root with **no
code change**: `iter_root_launchers()` already walks `templates/<tool>/*.sh|bat`,
so a new `templates/doqs-cli/` folder was enough.

## The compatibility promise

`validate_all.py` still runs the same seven gates, and nothing else. A machine
repository can bump its doqs pin without new gates appearing in its CI. We proved
it rather than assumed it: `validate_all.py` was run against all three fixtures
before and after the change, and the output is byte-identical with the same exit
codes.

`doqs check` runs those seven **plus** three checks on generated files
(`resolve_params --table --check`, `resolve_instance --check`,
`apply_licenses --check`). Those arrive only when a repository chooses to call
the new command. The gate list lives in `cli.GATES`, and `validate_all.py`
imports it, so the two cannot drift apart.

## Subprocess, not in-process

The plan said to call each gate in-process for speed. We kept subprocess
dispatch, which is what `validate_all.py` has always done. One gate that crashes
then cannot take the whole run down, and the `SystemExit` that `aggregate_bom`
raises from library code stays harmless. A test covers it: a repository with a
broken manifest still gets a full report, not just the first failure.

## Also in this step

- `check_links.py` and `validate_build.py` had argparse inside `if __name__`, so
  neither could be imported or tested. Both now have `main(argv)`.
- `aggregate_bom.py` gained `main(argv)` for the same reason.
- `check_names.py --warnings-only` did nothing at all — both branches returned 0.
  Removed.
- `build_graph.py` gained `--check`, and its graph building is now separate from
  writing the file. qarve checks its committed graph with
  `git diff --exit-code`; `build_graph.py --check` replaces that. It is
  deliberately **not** in `doqs check`: no repository commits that file today,
  so gating it would turn everyone red.
- First tests for `validate_build.py`, `aggregate_bom.py` and `build_graph.py`.
  All three had no test of any kind.

One of those new tests found drift: qarve's hand-copied `aggregate_bom.py` prints
"No module BOM files found", while the doqs script writes a header-only CSV. Two
scripts with one name doing different things is exactly what step 1 removed from
the documentation.

## Numbers

240 tests pass, up from 215.

## Next Steps

Step 3: `docs/using-doqs.md`, the one page for someone using doqs in their own
repository.
