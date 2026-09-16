# Agent CAD configuration

Copy-once configuration that lets an agent edit FreeCAD models **while you keep
the files open**, without any path that can silently overwrite your work.

`setup-tooling` installs both files at the machine repository root and never
overwrites them afterwards — they are yours to edit. `validate_cad.py` gates on
the deny rules, so removing them fails CI rather than failing silently.

| Template | Installed as | Purpose |
| --- | --- | --- |
| `mcp.json` | `.mcp.json` | Registers the FreeCAD MCP server, screenshots off by default |
| `claude-settings.json` | `.claude/settings.json` | Denies the two tools that write a `.FCStd` behind an open document |

## Why these two tools are denied

FreeCAD does not notice that a file changed on disk. Two processes with the same
document open will silently overwrite each other on save, with no warning
([FreeCAD#8924](https://github.com/FreeCAD/FreeCAD/issues/8924)).

* `execute_code_headless` runs agent code in a separate `freecadcmd` process and
  its own documentation invites it to open documents from disk and save them.
* `reload_document` is the upstream remedy for that, and it works by discarding
  your unsaved in-memory document.

Denying both by bare name removes them from the agent's context entirely. With
them gone, no code path in the addon writes to disk, so the `.FCStd` changes only
when you press Ctrl+S. Do **not** rely on the OS read-only attribute instead —
FreeCAD ignores it and saves anyway
([FreeCAD#25474](https://github.com/FreeCAD/FreeCAD/issues/25474)).

## Screenshots

`--only-text-feedback` suppresses the screenshot otherwise attached to eight
tools. A 1920x1080 viewport costs about 2,700 tokens and still cannot tell you
whether a rail is 500 mm long; the committed fingerprint answers that in tens of
tokens. The explicit `get_view` tool ignores the flag, so an agent can still ask
to look when the question is genuinely visual:

    get_view(view_name="Isometric", width=640, height=480)

Full setup and rationale: [`doqs/docs/agent-cad.md`](../../docs/agent-cad.md).
