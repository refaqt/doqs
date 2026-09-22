# 2026-09-22 — The session hook finds its own repository

**Role(s):** software

## What happened

A cloud session opened three repositories at once. Claude Code then opens the folder
above them, and reads `.claude/settings.json` from that folder only. It found none, so
the session hook was never registered and never ran. `.agents/`, `doqs/` and
`modules/stoq/` all stayed empty, and nothing on screen said so. The network was fine.

Looking at the hook showed a second problem underneath. Its first line trusted
`$CLAUDE_PROJECT_DIR`, which in that layout holds the parent folder. Even a hook that did
start would have moved to a folder that is not a git repository, and every git call would
have failed without naming the folder it used.

## What changed

- Both hooks — `templates/session-hook/session-start.sh` and `.claude/hooks/session-start.sh`
  — now find the repository root from their own place on disk, check it is a git work
  tree, and name it in every message. They still always exit 0.
- `CLAUDE.md` grew from one line into a first step: look for `.agents/rules/core.md`, and
  fill the folder when it is missing. Claude Code reads `CLAUDE.md` from every repository
  a session attaches, so this step works where the hook cannot.
- `templates/setup-tooling/CLAUDE.md` is the same first step for machine repositories, to
  be copied by hand. The installer still never writes a repository's own text.
- `docs/using-doqs.md` and `templates/session-hook/README.md` now say under which
  condition the hook runs, instead of promising that it always does.
- `.gitattributes` pins every `*.sh` to LF, so a Windows checkout cannot hand a CRLF hook
  to `install_root_tools.py`.
- New `tests/test_session_hook.py` runs both hooks from a parent folder with a wrong
  `CLAUDE_PROJECT_DIR`, and fails on the old first line.

## What this rules out

Nothing a repository commits can start a hook in a session that opens a parent folder.
That part is a session setting: attach one repository, or run `setup-tooling.sh` from the
environment's own setup script.

## Related

- [The session hook finds its own repository](../decisions/2026-09-22_hook-finds-its-own-root.md)
