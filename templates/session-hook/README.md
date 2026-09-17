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
