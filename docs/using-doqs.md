# Using doqs in your repository

This page is for someone working **in a machine repository** that has doqs as a
submodule. It says what to run, what gets copied, and what for.

Developing doqs itself is a different job: see [CONTRIBUTING.md](../CONTRIBUTING.md).

## 1. One command

```bash
bash doqs.sh check
```

That runs every gate on your repository. `doqs.bat check` is the same on Windows,
and `python doqs/doqs.py check` works without either launcher.

You never need to know a script name. `bash doqs.sh list` prints every command.

## 2. Add doqs to a repository

Do this once, by hand.

1. Copy `setup-tooling.sh` and `setup-tooling.bat` from
   [`templates/setup-tooling/`](../templates/setup-tooling/) to your **repository
   root**. Commit them. Do not gitignore them. Do not run them from the templates
   folder — `dirname` would point at the wrong place.
2. Add this line to your `.gitattributes`, so Windows cannot store the wrong line
   endings in a shell helper:

   ```
   *.sh text eol=lf
   ```

3. Merge [`templates/setup-tooling/gitmodules.snippet`](../templates/setup-tooling/gitmodules.snippet)
   into your `.gitmodules`, or add the two submodules yourself. Set
   `branch = main` **only** on `doqs` and `.agents`. Modules under `modules/` stay
   pinned to a commit and must never get a branch.
4. Copy the **First step (required)** block from the
   [refaqt-agents `templates/AGENTS.md`](https://github.com/refaqt/refaqt-agents/blob/main/templates/AGENTS.md)
   into your root `AGENTS.md`.
5. From your repository root, run `bash setup-tooling.sh`.

Your clone token needs read access to
[refaqt/doqs](https://github.com/refaqt/doqs) and
[refaqt/refaqt-agents](https://github.com/refaqt/refaqt-agents). Both are public.

## 3. Every session

```bash
bash setup-tooling.sh
```

It checks every submodule out at its recorded pin, then moves **only** `doqs` and
`.agents` to the latest `main`, then installs the root launchers and agent
configuration (see section 8).

Two things to expect:

- `git status` shows `doqs` and `.agents` as modified. That is the `--remote` step
  doing its job. **Leave them uncommitted** unless you mean to set a new pin.
- Anything under `modules/` showing as modified means your `setup-tooling.sh` is an
  old copy. Replace it from the template.

Claude Code and Cursor run a `SessionStart` hook that does the submodule part for
you, so a cloud session starts with the folders filled. The hook does not install
the launchers; `setup-tooling.sh` does.

`setup-tooling.sh` installs that hook at `.claude/hooks/session-start.sh` and
registers it in `.claude/settings.json`. The file on its own does nothing — the
settings entry is what starts it — so `doqs check` fails when the file is there and
nothing runs it. To use the same hook in Cursor, point `.cursor/environment.json`
at it:

```json
{ "name": "<your machine>", "install": "bash .claude/hooks/session-start.sh" }
```

**No network?** The hook says so and the session continues. Run
`bash setup-tooling.sh` when you are online again. Until then `doqs/` may be empty,
and every `doqs` command will fail with a missing-file error.

## 4. The commands

`bash doqs.sh list` prints this table from the code, so it can never go stale.

| Command | What it does | When |
| --- | --- | --- |
| `doqs check` | Every gate, plus "are the generated files current?" | Before every commit and in CI |
| `doqs generate` | Writes every generated file, in the right order | After changing parameters, a BOM, an instance, or adding a content folder |
| `doqs setup` | Installs the root launchers and agent configuration | Rarely: `setup-tooling.sh` already does it |
| `doqs syson …` | Opens or saves `architecture/*.sysml` in SysON | Graphical SysML editing — see [syson.md](syson.md) |
| `doqs export …` | Exports geometry for one composition and model | Making a STEP file for one variant |
| `doqs bom …` | Resolves one module's BOM for one model | Checking what one variant costs |
| `doqs run <script> …` | Runs any script in `doqs/scripts/` by name | Something the commands above do not cover |
| `doqs list` | Every command, and the scripts each one runs | When you forget |

`doqs check` runs seven read-only gates, then three checks that your committed
generated files match what the resolvers produce today.

`python doqs/scripts/validate_all.py` still works and still runs the same **seven**
gates, without the three staleness checks. Repositories that have not moved their
CI over keep the behaviour they had.

### What each gate checks

When `doqs check` fails, this tells you which part of your repository it is about.

| Gate | Checks |
| --- | --- |
| `validate_okh.py` | Required OKH fields, the licence expression, file references, the `version` format |
| `validate_licenses.py` | Split-licence files, the README licence section, `TRADEMARKS.md` |
| `validate_names.py` | Module slugs, BOM ids and headers, model slugs, the naming lexicon |
| `validate_links.py` | SysML imports and OKH relative paths. With `--markdown`, markdown links too |
| `validate_build.py` | Every `builds/**/build.toml`: does each consumed interface have a provider? |
| `validate_variants.py` | Families: the catalogue, models, compositions, length-table coverage, vendor geometry, instance freshness |
| `validate_cad.py` | FreeCAD documents: the save guard, fingerprint currency, stale exports |
| `resolve_params.py --check` | Is `cad/params-table.csv` current? |
| `resolve_instance.py --check` | Are the resolved instance files current? |
| `apply_licenses.py --check` | Do the licence files match the current templates? |

The last three are the staleness checks. `doqs generate` fixes all three.

Useful flags: `--root PATH` to work on another repository, `--strict-lexicon` to
treat naming warnings as errors, `--expected-version X.Y.Z` before a release tag,
and `validate_cad.py --check-clean` to catch a `.FCStd` an agent left modified.

## 5. Before a pull request

```bash
bash doqs.sh generate      # write the generated files
bash doqs.sh check         # prove everything is consistent
git diff                   # read what generate wrote, then commit it
```

`generate` writes files. Always read the diff before committing it.

## 6. In CI

```yaml
- uses: actions/checkout@v4
  with:
    submodules: recursive     # the recorded pin, not the latest main
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
- run: python doqs/doqs.py check
```

Use `submodules: recursive` and not `--remote`. CI should test the pin you
committed, not whatever landed in doqs this morning.

## 7. Which doqs page to read

| Page | When |
| --- | --- |
| [architecture.md](architecture.md) | New modules, versioning, interfaces, builds, licensing, folder layout |
| [variants.md](variants.md) | Product families: several lengths or options of one design |
| [agent-cad.md](agent-cad.md) | Creating or editing FreeCAD models, the save guard, fingerprints |
| [naming.md](naming.md) | Naming modules, parts, campaigns, BOM ids |
| [naming-lexicon.md](naming-lexicon.md) | Approved words for BOM and part names |
| [readiness-levels.md](readiness-levels.md) | OTRL and ODRL values in `okh.toml` |
| [syson.md](syson.md) | Graphical SysML editing |
| [decisions/2026-06-24_freecad-master-sketches-body.md](decisions/2026-06-24_freecad-master-sketches-body.md) | FreeCAD top-down design and master sketches |

Your own `docs/architecture.md` should be a short overview that points here, not a
second copy of the specification.

## 8. What doqs puts in your repository

| Template | Lands at | How | Who does it |
| --- | --- | --- | --- |
| `doqs-cli/doqs.sh`, `doqs.bat` | repository root | Overwritten when the template changes | `setup-tooling.sh` |
| `syson/syson.sh`, `syson.bat` | repository root | Overwritten when the template changes | `setup-tooling.sh` |
| `session-hook/session-start.sh` | `.claude/hooks/session-start.sh` | Overwritten when the template changes | `setup-tooling.sh` |
| `agent-cad/mcp.json` | `.mcp.json` | Written once, never touched again | `setup-tooling.sh` |
| `agent-cad/claude-settings.json` | `.claude/settings.json` | **Merged**: what doqs owns is added, nothing is removed | `setup-tooling.sh` |
| `setup-tooling/setup-tooling.sh`, `.bat` | repository root | Copy once | **You**, at the start |
| `setup-tooling/gitmodules.snippet` | `.gitmodules` | Merge by hand | **You**, at the start |
| `setup-tooling/gitattributes.snippet` | `.gitattributes` | Merge by hand | **You**, at the start |
| `cad/build_model.py` | `modules/<module>/cad/` | Copy per module, then write `build()` | **You**, per module |
| `variants/*` (9 files) | a family root | Copy per family — see [`templates/variants/README.md`](../templates/variants/README.md) | **You**, per family |
| `measurement-case.md`, `measurement-summary.md` | a campaign folder | Copy per campaign | **You**, per campaign |
| `okh-module-with-parts.toml`, `data-index.csv` | wherever you need them | Copy and edit | **You** |
| `licensing/**` | — | **Never copied.** `apply_licenses.py` renders these files | `doqs generate` |

Three rules follow from that table:

- **A launcher and the session hook are doqs's files.** Do not edit `doqs.sh`,
  `syson.sh` or `.claude/hooks/session-start.sh`; your change is lost on the next
  update. Change them in doqs instead.
- **`.mcp.json` is yours.** doqs writes it once and never again.
- **`.claude/settings.json` is shared.** doqs owns two keys in it: the agent-CAD
  deny rules, and the line that starts the session hook. It adds those if they are
  missing and **removes nothing** — your own keys, and your own order, stay as they
  are. If you delete a deny rule on purpose, the next `setup-tooling.sh` run puts it
  back, and `doqs check` fails while it is gone.
- **`build_model.py` is a seed, not a tool.** There is no single place to put it, so
  no script puts it anywhere. Copy it into the module you are building and replace
  `build()` with your geometry.

## 9. Working in FreeCAD

Three scripts run **inside** FreeCAD, so no `doqs` command can reach them. `doqs list`
names them too.

```python
# in the FreeCAD Python console, from the module root
exec(open("doqs/scripts/cad_sync_params.py").read())
sync_active()          # writes cad/params.csv into the Params spreadsheet
```

```bash
# headless rebuild of one module's geometry
FreeCADCmd modules/<module>/cad/build_model.py
```

`cad_fingerprint.py` runs for you from `build_model.py`; you never call it directly.
`cad_build.py` is imported by `build_model.py` and holds the transaction and save
handling, which is why a module must never carry its own copy.

Read [agent-cad.md](agent-cad.md) before letting an agent touch a model.

## 10. When something goes wrong

| What you see | What it means |
| --- | --- |
| `doqs/` is empty, every command fails | The clone had no submodules. Run `bash setup-tooling.sh` |
| `--check` fails on a generated file | Run `doqs generate`, read the diff, commit it |
| `git status` shows `doqs` and `.agents` modified | Normal after `setup-tooling.sh`. Leave them uncommitted |
| Something under `modules/` shows as modified after the helper | Your `setup-tooling.sh` is an old copy. Replace it from the template |
| `.mcp.json` appears as an untracked file | The installer wrote it. Keep it if you use FreeCAD through an agent; otherwise delete it or gitignore it |
| A `.FCStd` has no fingerprint | Rebuild it: `FreeCADCmd <module>/cad/build_model.py` |

## 11. Where to change what

| Change | Repository |
| --- | --- |
| Cross-machine process rules, agent skills | **refaqt-agents**, mounted at `.agents/` |
| Layout, validators, naming rules, templates | **doqs**, mounted at `doqs/` |
| Anything about this machine | Your own repository, in `docs/` and `.agents-local/` |
