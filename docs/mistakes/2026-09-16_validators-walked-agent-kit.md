# 2026-09-16 — Validators walked the shared agent kit

## What happened

The gate scripts walk the machine repository root and read every `okh.toml`,
`catalog.toml`, `*.sysml`, `bom/bom.csv`, and `cad/` folder they find. They
skipped the `doqs/` submodule with `is_under_doqs_submodule()`, which matched
the folder name `doqs` only.

A machine repo also mounts the shared agent kit
([refaqt-agents](https://github.com/refaqt/refaqt-agents)) at its own
`.agents/`. That folder was still walked by nine scripts. A sample manifest in
the kit made `validate_okh.py` fail, and the machine repo could not fix the
file, because the kit is a different repository.

Two other scripts, `license_rules.py` and `validate_cad.py`, had already
learned to skip `.agents/`. Each kept its own copy of the name list, so the
third copy in `naming_rules.py` was never updated with them.

## Why it went wrong

The name of the helper described one submodule, so the second tooling
submodule was easy to forget. The same rule lived in three places, and no test
covered the kit folder.

## Prevention rule

Keep one list of tooling submodule names, `TOOLING_SUBMODULE_NAMES` in
[`scripts/naming_rules.py`](../../scripts/naming_rules.py), and one check,
`is_under_tooling_submodule()`. Every walker imports it. When a new tooling
submodule appears, add the name there and nowhere else. A test in
[`tests/test_naming_rules.py`](../../tests/test_naming_rules.py) runs the
gates against a machine fixture that holds sample files under `.agents/`.

## Related

- [2026-09-16_tooling-submodule-skip.md](../log/2026-09-16_tooling-submodule-skip.md)
- [architecture.md, Tooling submodules](../architecture.md)
