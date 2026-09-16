# ADR — a session hook downloads the shared agent kit

- **Date:** 2026-09-16
- **Status:** Accepted

## Context

This repo mounts [refaqt/refaqt-agents](https://github.com/refaqt/refaqt-agents)
as a submodule at `.agents/`. The gitlink is committed, but a cloud session
starts with an empty `.agents/` folder. The container clones `doqs` without
`--recurse-submodules`, so the kit is never downloaded. An agent then cannot
read `.agents/rules/*.md` or `.agents/skills/*`, and the first step in
[AGENTS.md](../../AGENTS.md) fails without anybody noticing.

The failure is quiet, which is the worst part. The folder exists. It is simply
empty. An agent that does not look reads no rules and keeps working.

`.gitmodules` sets `update = none` on `.agents`. That flag is deliberate: it
stops a second copy of the kit appearing at `doqs/.agents/` inside a machine
repo. The cost is that git skips this submodule in almost every command that
would otherwise fetch it.

## Decision

Add a `SessionStart` hook at the root of this repo.

1. [`.claude/settings.json`](../../.claude/settings.json) registers the hook.
2. [`.claude/hooks/session-start.sh`](../../.claude/hooks/session-start.sh) runs
   `git submodule update --init --remote --checkout .agents`.

The hook runs in every session, local and cloud. The problem is a clone without
submodules, and that can happen anywhere, so the hook is not limited to cloud
sessions.

The hook does not use async mode. The kit must be on disk before the agent reads
its rules, and the download takes about one second.

## Why `--checkout` is required

We tested both commands in a session container, from an empty `.agents/` folder:

| Command | Result |
| --- | --- |
| `git submodule update --init --remote .agents` | prints `Skipping submodule '.agents'`, exits 0, downloads nothing |
| `git submodule update --init --remote --checkout .agents` | checks the kit out, `.agents/rules/core.md` appears |

`--checkout` overrides `update = none` for this one call. The first command is
the dangerous one: it reports success and leaves the folder empty.

The hook therefore checks for the file `.agents/rules/core.md` rather than the
exit code of git.

## No network

The hook must never stop a session. It uses `set -uo pipefail` without `-e`,
captures the output of git, and always exits 0. Without a network it prints the
error from git, says the rules under `.agents/` are missing, and repeats the
command to run by hand later. `GIT_TERMINAL_PROMPT=0` stops git from waiting for
a password, and `timeout 120` stops a dead network from holding the session
open.

## Why not `submodules: recursive` in CI

[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) does not get the
option. Two reasons:

1. **It would not work.** `actions/checkout@v4` runs
   `git submodule update --init --recursive`, which has no `--checkout`, so
   `update = none` makes git skip `.agents` exactly as it does locally. We
   tested this command too, and the folder stayed empty.
2. **CI does not need the kit.** The rules and skills are for agents, not for
   the validators. `iter_submodule_paths()` in `scripts/license_rules.py` skips
   `.agents/` on purpose, and `validate_cad.py` skips it as well.

## Consequences

- A session starts with the kit on disk, or with a clear message saying why not.
- `--remote` moves the `.agents` gitlink to the latest `main`, so `git status`
  can show a modified submodule. That is the behaviour AGENTS.md already
  describes: leave the moved gitlink uncommitted unless you mean to set a new
  pin.
- This repo now has a `.claude/` folder. `scripts/install_root_tools.py` still
  skips `doqs`, so it does not write or overwrite anything here. The folder is
  covered by GPL-3.0, next to `.github/` and `.cursor/`; see
  [LICENSE](../../LICENSE).
- A machine repo gets its own `.claude/settings.json` from
  `templates/agent-cad/claude-settings.json`, which holds the FreeCAD guard.
  That file and this hook are separate things and do not overlap.
