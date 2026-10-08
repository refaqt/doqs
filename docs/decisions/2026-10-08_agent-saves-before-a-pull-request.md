# ADR-019 — The agent saves open FreeCAD documents before a pull request

- **Date:** 2026-10-08
- **Status:** Accepted

Write this file in B2 English. Follow `.agents/rules/communication.md`. Keep official names, file paths, and numbers exact.

## Context

An agent edits a model in the open FreeCAD window through the FreeCAD MCP server. Until now
the rule was that the agent never saves: the person saves. In practice the person often asks the
agent to commit and open a pull request before they save. Git only sees what is on disk, so the
pull request then misses the change in the model, and nothing warns about it.

The save guard exists for a different risk: a second FreeCAD process that writes the file
behind the open window. A save inside the open window has no second copy, so it carries no such
risk.

## Decision

- Before the agent commits or opens a pull request, it saves the open documents it changed. It
  runs `doc.save()` inside the running FreeCAD, with the `execute_code` tool.
- The agent saves only documents that already have a file in the repository. It tells the person
  which files it saved. A new document with no file name needs a name, so the agent asks.
- The two blocked tools stay blocked: `execute_code_headless` and `reload_document`.
- A build script still never saves an open document. The save is a separate step at the end.

## Consequences

- A pull request now holds the model the person saw in FreeCAD.
- The agent may save work the person made by hand in the same document. That work then goes into
  the commit as well. The person sees it in the pull request and can ask for it to be left out.
- The rule is in [agent-cad.md](../agent-cad.md) and in the FreeCAD skill of the shared agent kit.
