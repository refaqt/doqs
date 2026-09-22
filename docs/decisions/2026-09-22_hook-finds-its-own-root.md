# 2026-09-22 — The session hook finds its own repository

- **Date:** 2026-09-22
- **Status:** Accepted

## Context

Both session hooks started with the same line:

```bash
root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
```

A cloud session set `CLAUDE_PROJECT_DIR` to the folder it opened. That is normally the
repository root, so the line looked right for a year. It is not right when a session
attaches **several** repositories at once. The session then opens their shared parent
folder, and sets the variable to it. The parent folder is not a git work tree, so every
`git submodule` call in the hook failed, and no message said which folder it had used.

A real session showed the second, larger half of the problem. Claude Code reads
`.claude/settings.json` from the session's own project folder only. With the parent folder
open, it never read the file, so the hook was never registered and never ran. It printed
nothing at all. `.agents/`, `doqs/` and `modules/stoq/` all stayed empty:

```
$ git submodule status
-58fd8512... .agents
-4decc8aa... doqs
-7043e422... modules/stoq
```

The network was fine. Nothing was broken. Nothing ran.

The same session did load `CLAUDE.md` from every repository it had attached. That
asymmetry is the opening: settings come from one folder, `CLAUDE.md` comes from all of
them.

## Decision

1. Both hooks find the repository root from their own place on disk. The file always sits
   at `<root>/.claude/hooks/session-start.sh`, so its own folder gives the answer.
   `$CLAUDE_PROJECT_DIR` is tried second, the working folder third. Each candidate must
   pass `git rev-parse --show-toplevel` before it is used.
2. When no candidate is a git work tree, the hook says so, names every folder it tried,
   and exits 0. It still never stops a session.
3. Every message names the root it worked in, so a person can see at a glance whether the
   hook worked on the repository they meant.
4. `CLAUDE.md` carries the check that always works: look for the marker files, and run the
   setup helper when they are missing. `templates/setup-tooling/CLAUDE.md` is the version
   for machine repositories.

## Consequences

The hook is now correct in more layouts, but it still cannot start itself. That is
harness behaviour, not something a repository can commit. Two things carry the rest: the
`CLAUDE.md` check, and the choice of how many repositories a session attaches. One source
per session is the layout to prefer, because it also switches on everything else in
`.claude/settings.json`.

`tests/test_session_hook.py` runs both hooks from a parent folder with a wrong
`CLAUDE_PROJECT_DIR` and reads what they print. That test fails on the old line.

Both hooks now share the root-finding block. They stay different in every other way: doqs
keeps `--checkout` and one submodule, the template keeps two submodules and no
`--checkout`. A test guards that split, which used to live only in prose.

## Related

- [A session hook downloads the shared agent kit](2026-09-16_agent-kit-session-hook.md)
- [docs/using-doqs.md](../using-doqs.md), section 3
