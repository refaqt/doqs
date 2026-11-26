# The session hook

`session-start.sh` fills `.agents/` and `doqs/` at the start of every session.

Why it exists: a cloud session clones a repository **without** submodules, so both
folders arrive empty. Nothing warns about it. An agent then reads no rules, no
skills and no doqs specification, and every `doqs` command fails. The folders are
there, so the failure is silent — the worst kind.

`install_root_tools.py` copies this file to `.claude/hooks/session-start.sh` in the
consumer repository and sets it executable. It is **overwritten when the template
changes**, like the root launchers: it is a doqs tool, not your file. Do not edit
your copy; change it here.

The file alone does nothing. `.claude/settings.json` is what starts it, and
`install_root_tools.py` merges that registration in without touching anything else
you keep in that file. `validate_cad.py` fails when the hook is on disk and the
settings file does not run it, because that combination looks set up and is not.

When the folders are filled, the hook also runs the kit's `link_skills.sh`, if the
kit has it. On success it prints two lines: the commits it checked out, and a line
that says `CLAUDE.md` and `AGENTS.md` are already loaded. When something fails, it
says which folder is empty, what git said, and which command to run later.

## When the hook does not run

This is the one full explanation. Other pages link here.

The registration has one limit that no repository can lift. Claude Code reads
`.claude/settings.json` from the session's own project folder only. A session that
opens a parent folder, or that attaches several repositories at once, never reads
that file, so the hook never starts and prints nothing at all. A thread inside a
Claude project does not run it either. The permission mode does not matter: the
hook runs in plan mode too. Silence then means
"never ran", not "nothing to report". The output cannot tell you, because silence
looks the same as success.

So check the two marker files instead. An empty folder still exists, so only a file
inside it proves anything:

```bash
bash setup-tooling.sh --check     # or: ls .agents/rules/core.md doqs/scripts/validate_all.py
bash doqs.sh doctor               # the same, plus each folder's commit and its pin
```

If a file is missing, run `bash setup-tooling.sh`. In plan mode the agent must ask
the person to approve that command, because plan mode blocks commands that change
files. It only fills the two tooling folders and changes no file that git tracks.
`doqs doctor` needs `doqs/` itself, so when `doqs/` is empty only
`setup-tooling.sh --check` can answer.

Root `CLAUDE.md` carries this check, because Claude Code reads `CLAUDE.md` from
every repository a session attaches. The shared kit writes it with `.agents/scripts/sync_root.py`.

With no network, the hook says so and the session continues. Until someone runs
`bash setup-tooling.sh` online, `doqs/` may be empty and every `doqs` command fails
with a missing-file error.

## How the hook finds the repository

The hook finds the repository root from its own place on disk, not from
`$CLAUDE_PROJECT_DIR`. In the layout above that variable holds the parent folder,
which is not a repository, so trusting it made every git call fail with no
explanation.

`.cursor/environment.json` can run the same script, so Cursor cloud agents get the
same result from one implementation:

```json
{ "name": "<your machine>", "install": "bash .claude/hooks/session-start.sh" }
```

## Why doqs does not use this template itself

doqs has its own hook at `.claude/hooks/session-start.sh`, written by hand, and it
stays that way. It fetches **one** submodule and needs `--checkout`, because doqs
marks its own nested `.agents` as `update = none`; without the flag git prints
`Skipping submodule`, exits 0, and downloads nothing.

No machine repository sets that flag, so no machine repository needs `--checkout`.
This template fetches **two** submodules and leaves the flag out. Two shapes, one
cause, and neither will ever be right for the other.

`install_root_tools.py` also returns immediately on the tools repo, so doqs could
not install this into itself even if the shapes matched.

Both files find the repository root the same way, from their own place on disk.
Everything else about them stays different, for the reason above.
