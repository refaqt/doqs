# ADR-020 — The agent starts the FreeCAD connection, and picks headless or MCP

- **Date:** 2026-10-28
- **Status:** Accepted

Write this file in B2 English. Follow `.agents/rules/communication.md`. Keep official names, file paths, and numbers exact.

## Context

An agent edits a model in the FreeCAD window through the RPC server of the freecad-mcp add-on.
Until now the person had to start that server by hand, and often had to check that it ran before
they asked the agent for a change.

The add-on gives no MCP tool that starts the server or FreeCAD. It can start the server by itself
when FreeCAD starts: it reads `auto_start_rpc` from `freecad_mcp_settings.json` in FreeCAD's user
data folder. Nothing can reach a window that is already open with the server off.

An agent can also edit headless, with `FreeCADCmd`. That is only safe when no window has the same
file open, because FreeCAD does not notice a file that changed on disk
([FreeCAD#8924](https://github.com/FreeCAD/FreeCAD/issues/8924)).

## Decision

- A new command, `doqs freecad` (`scripts/freecad_session.py`), has three parts:
  - `status` says if FreeCAD runs, if the server answers, which files are open, and one advice:
    `mcp`, `headless` or `ask-user`.
  - `autostart` switches on `auto_start_rpc`. It changes no other key.
  - `start` starts FreeCAD, with a file if given, and waits for the server. It switches on
    auto-start first. It never starts a second window when FreeCAD already runs.
- The agent runs `status` before every FreeCAD edit. An open file is edited through MCP. With no
  FreeCAD running, headless is the default. A window that does not answer means: ask the person
  for one click, and no headless edit.
- `.claude/settings.json` allows `bash doqs.sh freecad` without a prompt, and turns on the
  `freecad` server from `.mcp.json`. `install_root_tools.py` merges both into existing files.
- The script has no verb at the start of its name. Like `syson.py`, it opens and drives another
  program, and no verb fits that. It is not called `freecad.py`: on Windows, file names ignore
  upper and lower case, so `import FreeCAD` could load it instead of FreeCAD.
- `execute_code_headless` and `reload_document` stay denied. The headless path is `FreeCADCmd`,
  run by the agent after the check.

## Consequences

- The person no longer starts the server. After the first `autostart`, every FreeCAD start has
  it. The person helps only once, when a window was opened before auto-start was on.
- The agent may start FreeCAD on the person's computer. It does so only when no FreeCAD runs.
- The rule is in [agent-cad.md](../agent-cad.md#headless-or-mcp-the-agent-decides) and in the
  FreeCAD skill of the shared agent kit.
- The tests use a fake add-on. The command has not yet run against a real FreeCAD window.
