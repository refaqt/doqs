# Copy-once: tooling submodule helpers

These files are **templates**. Copy them to the **consumer repo root** and run them from there. Do **not** run `setup-tooling.sh` or `setup-tooling.bat` from this folder — `dirname` / `%~dp0` would be `doqs/templates/setup-tooling/`, not the repo root.

`setup-tooling.sh` / `.bat` themselves stay copy-once (bootstrap). They check every submodule out at its recorded pin (`git submodule update --init --recursive`), then track `main` for the tooling submodules only (`git submodule update --remote -- doqs .agents`). After that they run `python doqs/scripts/install_root_tools.py`, which copies `*.bat` and `*.sh` from `doqs/templates/<tool>/` (except this folder) to the consumer root. New tools appear on the next helper run without another copy of `setup-tooling.*`. Existing machine repos need a **one-time** refresh of `setup-tooling.sh` / `.bat` from this folder so that installer step exists.

doqs still does not write `AGENTS.md`, `CLAUDE.md` or `README.md`. Those are the repository's own text.

Clone tokens must be able to read [refaqt/doqs](https://github.com/refaqt/doqs) and [refaqt/refaqt-agents](https://github.com/refaqt/refaqt-agents) (public repos are fine; private clones need read access).

## Checklist for a new consumer repo

1. Copy `setup-tooling.sh` and `setup-tooling.bat` to the **repository root**. Commit them. Do not gitignore them.
2. Add this line to the consumer `.gitattributes` (see `gitattributes.snippet`) so Windows cannot store CRLF in the shell helper:

   ```
   setup-tooling.sh text eol=lf
   .claude/hooks/session-start.sh text eol=lf
   ```

3. Merge `gitmodules.snippet` into root `.gitmodules`, or `git submodule add` the tooling remotes if they are missing. Set `branch = main` only on **tooling** submodules (`doqs`, `.agents`). Extracted machine modules under `modules/` stay SHA-pinned without `branch`; the helper names the tooling submodules explicitly so `--remote` cannot reach them.
4. Copy or adapt the **First step (required)** block from [refaqt-agents `templates/AGENTS.md`](https://github.com/refaqt/refaqt-agents/blob/main/templates/AGENTS.md) into root `AGENTS.md`. That wording lives in refaqt-agents, not here.
5. Copy `CLAUDE.md` from this folder to the **repository root** and put your machine's name in the title. It holds the check an agent runs before anything else. It matters most in a session where the start-up hook cannot run: Claude Code reads `.claude/settings.json` from the session's own project folder only, but it reads `CLAUDE.md` from every repository the session attaches. Adapt this file by hand; the installer never writes it.
6. After clone, from the consumer root:
   - Agents (any OS): `bash setup-tooling.sh`
   - Humans on Windows may double-click `setup-tooling.bat` (`pause` is OK there only). Agents must not run the `.bat`.
   The helper also installs root launchers such as `syson.bat` / `syson.sh`.
7. Do not commit dirty submodule gitlinks after `--remote` unless you intend to freeze a pin. CI should keep `submodules: recursive` (recorded pin), not `--remote`. Only `doqs` and `.agents` should show as dirty after a helper run; anything under `modules/` showing as dirty means the helper is an old copy.

`doqs` mounts the same kit at `doqs/.agents/`, but its `.gitmodules` sets `update = none`, so git skips it and the consumer repo gets only one copy of the kit, at its own `.agents/`.
