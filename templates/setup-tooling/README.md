# Copy-once: tooling submodule helpers

These files are **templates**. Copy them to the **consumer repo root** and run them from there. Do **not** run `setup-tooling.sh` or `setup-tooling.bat` from this folder — `dirname` / `%~dp0` would be `doqs/templates/setup-tooling/`, not the repo root.

doqs does not write or overwrite consumer-root files (`AGENTS.md`, `README.md`, `setup-tooling.*`, etc.). There is no apply script for this kit.

Clone tokens must be able to read [refaqt/doqs](https://github.com/refaqt/doqs) and [refaqt/refaqt-agents](https://github.com/refaqt/refaqt-agents) (public repos are fine; private clones need read access).

## Checklist for a new consumer repo

1. Copy `setup-tooling.sh` and `setup-tooling.bat` to the **repository root**. Commit them. Do not gitignore them.
2. Add this line to the consumer `.gitattributes` (see `gitattributes.snippet`) so Windows cannot store CRLF in the shell helper:

   ```
   setup-tooling.sh text eol=lf
   ```

3. Merge `gitmodules.snippet` into root `.gitmodules`, or `git submodule add` the tooling remotes if they are missing. Set `branch = main` only on **tooling** submodules (`doqs`, `.agents`). Extracted machine modules under `modules/` stay SHA-pinned without `branch`.
4. Copy or adapt the **First step (required)** block from [refaqt-agents `templates/AGENTS.md`](https://github.com/refaqt/refaqt-agents/blob/main/templates/AGENTS.md) into root `AGENTS.md`. That wording lives in refaqt-agents, not here.
5. After clone, from the consumer root:
   - Agents (any OS): `bash setup-tooling.sh`
   - Humans on Windows may double-click `setup-tooling.bat` (`pause` is OK there only). Agents must not run the `.bat`.
6. Do not commit dirty submodule gitlinks after `--remote` unless you intend to freeze a pin. CI should keep `submodules: recursive` (recorded pin), not `--remote`.
