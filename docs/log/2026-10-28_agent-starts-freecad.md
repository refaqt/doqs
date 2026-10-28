# 2026-10-28 — The agent can start the FreeCAD connection itself

**Role(s):** cad, software

## What happened

You no longer need to check that the FreeCAD MCP server runs before you ask an agent for a model
change. A new command, `bash doqs.sh freecad`, lets the agent:

- see if FreeCAD runs, if its server answers, and which files are open;
- make the server start with FreeCAD every time;
- start FreeCAD itself when no FreeCAD runs.

The same command tells the agent which way to edit is safe: in the open window, or headless.
The agent decides from that. The decision record
[ADR-020](../decisions/2026-10-28_agent-starts-freecad-mcp.md) explains the rule.

One case still needs you: FreeCAD is already open and its server is off. Nothing can reach that
window. The agent asks you to click **Start RPC Server** once.

## Next Steps

- Run `bash doqs.sh freecad start` once on a real computer, with FreeCAD closed, and check that
  the window opens and the server answers. The tests use a fake FreeCAD.
- Move each machine repository's `doqs/` submodule to this change and run `setup-tooling.sh`, so
  the new allow rules reach `.claude/settings.json`.
