# 2026-09-16 — The session hook is a template now

**Role(s):** software

## What happened

Each repository wrote its own `SessionStart` hook by hand. `templates/` held none,
so a fix in one repository never reached another. aqtuator had a good one. qarve
has none at all, which means a cloud session there starts with `doqs/` and
`.agents/` empty and nothing says why.

`templates/session-hook/session-start.sh` is seeded **from aqtuator's working
file**, byte for byte apart from one comment: it pointed at aqtuator's own decision
record, and now points at `doqs/docs/using-doqs.md`, section 3. Seeding from the
file that already works means the first install in aqtuator changes that one line
and nothing else. We checked, against a copy of aqtuator:

```
updated .claude/hooks/session-start.sh     # the one comment line
created doqs.sh, doqs.bat                  # new, from step 2
                                           # .claude/settings.json: untouched
```

## The installer gained a third mechanism

It had two: copy a launcher to the root and overwrite it when the template
changes, or write a config file once and never touch it again. The hook fits
neither — it belongs at `.claude/hooks/`, and it is ours, not the user's.

`TOOL_TEMPLATES` and `install_tools()` copy to a nested path, overwrite a stale
copy, and set the file executable. Claude Code runs the hook directly, so mode 644
would simply not start. `session-hook` is in `SKIP_TEMPLATE_DIRS`, or the launcher
walk would also drop a second, unregistered copy in the repository root.

## The settings file is merged now, not copied once

This is the part that mattered. `.claude/settings.json` was copy-once, and that
produced two silent failures:

- A fresh repository got a settings file with no `hooks` block, so the hook we just
  installed was never started. It looks set up and is not.
- A repository that already had the file, like aqtuator, never received the
  agent-CAD deny rules. aqtuator merged them in by hand for exactly this reason.

`install_settings()` now merges. It adds the hook registration if nothing already
runs a `session-start.sh`, adds any missing deny rule, and **removes nothing**.
Keys doqs knows nothing about survive, and so does the order of what is there.
Broken JSON fails loudly instead of being overwritten — the one case where writing
would destroy something we cannot get back.

`.mcp.json` stays copy-once. That one is genuinely the user's.

## A new gate

`validate_cad.py` now fails when `.claude/hooks/session-start.sh` exists and the
settings file does not run it. Unlike the agent-CAD guard, it does not wait for a
`.FCStd`: a hook nobody runs costs you the tooling submodules whether or not the
repository has CAD.

## Numbers

272 tests pass, up from 253. Two existing tests changed, because the settings file
moved out of the copy-once path; their intent is kept.

## Next Steps

Step 5, the last one in doqs: rename `check_names.py`, `check_links.py` and
`build_graph.py`, with a stub for each that names its replacement.
