# 2026-10-07 — After a merge, reopen the files that FreeCAD has open

**Role(s):** cad, software

## What happened

A question came up about a common way of working. You work locally on the `main` branch, with
FreeCAD open. You ask Claude to commit and open a pull request. Claude makes a new branch and a
pull request. You merge it, go back to `main`, and pull. FreeCAD is still open. Is it showing the
latest version?

The answer is no. Git has put the latest version on disk, but FreeCAD still shows the old one.
Close the documents in FreeCAD and open them again. You do not need to quit FreeCAD itself.

Why this happens:

- FreeCAD reads a `.FCStd` file once, when you open it. After that, it works on its own copy in
  memory.
- FreeCAD does not watch the file on disk. When `git pull` writes a new version, FreeCAD does not
  notice and gives no warning.
- So after the pull there are two versions. The file on disk is the latest version from `main`.
  The FreeCAD window still shows the version from before the merge.

The risk: if you press Ctrl+S in the old window, FreeCAD writes the old version over the new file.
The merged changes are then lost on disk. You see this later as an unexpected change in
`git status`.

What to do after you merge and pull:

1. Check that you have the latest version. Run `git fetch origin` and then `git status`. It should
   say "Your branch is up to date with 'origin/main'" and "nothing to commit, working tree clean".
2. In FreeCAD, look for unsaved work. A document with unsaved changes has an asterisk (`*`) in its
   tab name.
   - No asterisk: close the document and open it again, or use File → Revert. Revert reloads the
     file from disk.
   - Asterisk: do not save over the file. Those edits were never in the commit, because Git only
     sees what is on disk. Use File → Save As with a new name, then compare the two versions.
3. Save in FreeCAD before you ask Claude to commit. Claude can only commit what FreeCAD has
   written to disk.

One special case: the model is built by `cad/build_model.py`, and the `.FCStd` file is generated
from it. If a pull request changed only that Python file, reopening the `.FCStd` file can still
show the old shape. Run the build again, in FreeCAD or with `FreeCADCmd cad/build_model.py`.

The Claude bridge into FreeCAD never saves files. It also cannot reload a document from disk,
because doqs blocks that tool on purpose: reloading would throw away unsaved work. So reloading is
always your step. See [the agent CAD guide](../agent-cad.md).

## Next Steps

- Consider adding this advice to [the agent CAD guide](../agent-cad.md), so people find it
  without searching the log.

<details>
<summary>Technical notes</summary>

- The blocked tools are `mcp__freecad__reload_document` and `mcp__freecad__execute_code_headless`.
  `validate_cad.py` fails the build if those deny rules go missing.
- No code changed. This entry records advice only.

</details>
