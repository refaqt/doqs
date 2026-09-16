# 2026-09-16 — Validators skip the agent kit

**Role(s):** software

## What happened

A review of pull request #14 found that the gate scripts still walked the
machine repository's own `.agents/` folder. That folder holds the shared agent
kit, which is a separate repository. A sample `okh.toml` there made
`validate_okh.py` fail on a machine repo.

Work done:

- `scripts/naming_rules.py` now exports `TOOLING_SUBMODULE_NAMES`
  (`doqs`, `.agents`) and `is_under_tooling_submodule()`, which replaces
  `is_under_doqs_submodule()`.
- The ten scripts that walk the machine root use the new check.
- `scripts/license_rules.py` and `scripts/validate_cad.py` dropped their own
  copies of the name list and import the shared one.
- `tests/test_naming_rules.py` gained unit tests for the check and a test that
  runs four gates against a fixture with sample files under `.agents/`.
- `docs/architecture.md` records the rule in the tooling submodules section.

## Decisions

Match the folder name at any depth. An extracted module under `modules/`
mounts the same two submodules for itself, so `modules/x-axis/.agents/` must
be skipped as well.

## Next Steps

Machine repos pick this up with the usual `bash setup-tooling.sh` run.

## Related

- [2026-09-16_validators-walked-agent-kit.md](../mistakes/2026-09-16_validators-walked-agent-kit.md)
