# 2026-09-18 — A check read the path to the repository, not the path inside it

## What happened

The naming check warns when a folder under `modules/` has no `okh.toml`, because
that folder may be a module someone forgot to finish. To avoid false alarms it
skipped any folder whose name was `cad`, `bom` or `architecture`.

It tested those names against the **full path on disk**, including every folder
above the repository itself. A repository stored in a folder named `cad` — for
example `C:\work\cad\my-machine` — matched the skip rule at the top, so the
whole check was skipped. Nothing was printed. The same repository was checked on
one computer and silently not checked on another.

The list of excused names was also too short. It named three folders, but the
specification gives every module eight content folders. The five that were
missing, and everything inside them, were reported as lost modules. One machine
repository produced twenty warnings for a single module.

## Why it went wrong

The check walked every folder at every depth and then tried to excuse the ones
it should not have opened. A list of excuses can never be complete, because a
module may hold any content folder. And the excuse itself was matched against
the path to the repository, which the project does not control.

This is the second time a name match at any depth caused a problem. The first
time, a folder name was matched too little; this time, too much.

## Prevention rule

Two rules, both for any check that walks a repository.

1. **Decide where a thing can be, then look only there.** Do not walk
   everything and filter by name. A module sits directly under a `modules/`
   folder, or under `modules/adapters/`, and nowhere else. See
   [naming.md, Where a module may sit](../naming.md).
2. **Never compare a name against an absolute path.** The folders above the
   repository belong to the person who cloned it. Always compare against the
   path relative to the repository root, as
   [`is_under_tooling_submodule()`](../../scripts/naming_rules.py) does.

Tests in [`tests/test_naming_rules.py`](../../tests/test_naming_rules.py) cover
both: a module with a `docs/` folder stays silent, and a repository inside a
folder named `cad` still reports a real orphan.

## Related

- [2026-09-18_orphan-warning-only-in-module-folders.md](../log/2026-09-18_orphan-warning-only-in-module-folders.md)
- [2026-09-16_validators-walked-agent-kit.md](2026-09-16_validators-walked-agent-kit.md)
