# 2026-10-08 — The agent now saves FreeCAD files before a pull request

**Role(s):** cad, software

## What happened

When an agent changed a model in the open FreeCAD window, it did not save the file. The person had
to save first. If they forgot, the pull request did not hold the change, because Git only sees
what is on disk.

The rule is now different. Before the agent commits or opens a pull request, it saves the open
documents it changed, inside the running FreeCAD. It tells you which files it saved. For a new
document with no file name, it asks you for a name.

This is safe. The save happens in the same FreeCAD window you are looking at, so there is no
second copy that can overwrite your work. The two tools that could write behind your window stay
blocked.

This replaces the advice in the entry
[After a merge, reopen the files that FreeCAD has open](2026-10-07_freecad-open-after-merge.md)
that the Claude bridge never saves files.

## Next Steps

- Nothing. The guides already carry the new rule.

<details>
<summary>Technical notes</summary>

- Decision: [ADR-019](../decisions/2026-10-08_agent-saves-before-a-pull-request.md).
- Changed pages: `docs/agent-cad.md` (save table, guard section, step 4 of "Working with a file
  open"), `docs/using-doqs.md` (section 5), `templates/agent-cad/README.md`.
- The shared kit's `skills/freecad/SKILL.md` gets the same rule in refaqt/refaqt-agents.
- No code changed. `scripts/cad_build.py` still never saves an open GUI document.

</details>
