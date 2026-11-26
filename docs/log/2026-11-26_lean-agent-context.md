# 2026-11-26 — Agents read less at the start of a session

**Role(s):** software

## What changed

Agents now read much less before they start work, and they run one command where they used to
follow a page of instructions. The big specification page shrank from 89 KB to a 5 KB overview,
with one short page per topic. New commands check the tooling folders (`doqs doctor`), prepare a
pull request (`doqs pre-pr`), save FreeCAD work (`doqs freecad save`) and start a log entry
(`doqs log new`). This change is on branch `claude/blissful-ride-ojx7wf`, not yet merged.

## Why it matters

Every agent session paid for the same long texts again: the full specification, three copies of
one story about the start-up hook, and lines that asked the agent to read rules it had already
loaded. That cost time and money in every session. Steps written as prose were also easy to do in
the wrong order, for example checking before saving the FreeCAD files.

## What you need to do

Nothing right away. After a machine repository moves its `doqs/` submodule to this change, use
`bash doqs.sh pre-pr` before each pull request and `bash doqs.sh doctor` when a command says a
file is missing. CI does not change: the new checks from the shared agent kit only warn. The
reasons are in [ADR-022](../decisions/2026-11-26_lean-agent-context.md).

## How it was checked

758 automated tests ran. 757 pass. The one failure was already there before this change: that
test expects a computer without FreeCAD, and this one has it. `doqs check` passes on all four test
machines, and every link and section link in the documentation resolves. The shared kit's new
scripts do not exist yet, so the commands that call them were tested with stand-in scripts.

<details>
<summary>Technical notes</summary>

- New commands in `scripts/cli.py`: `doctor`, `pre-pr`, `log new`, `mistakes`, `context`. New
  `save` action in `scripts/freecad_session.py`, checked once in a real FreeCADCmd 1.1.
- `doqs check` runs `.agents/scripts/mistakes_index.py --check` and `sync_root.py --check` last, as
  warnings. It skips them silently when the script, `docs/mistakes/README.md` or
  `.agents-local/profile.toml` is missing.
- `install_root_tools.py` runs `sync_root.py --root` when the script and the profile both exist.
- `pre-pr` saves and rebuilds first, then generates and checks, so the check sees the saved files.
- `setup-tooling.sh --check` and `setup-tooling.bat --check` only read the two marker files.
- The topic pages are in `docs/architecture/`. Links into the old sections were moved to them.
- Found on the way, not changed: `doqs generate` writes the licence files before the BOM, so a new
  root `bom/` folder has no licence file until the second run.

</details>
