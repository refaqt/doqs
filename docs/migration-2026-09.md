# Moving to the September 2026 doqs

What changed for a machine repository, and what you have to do about it.

**Nothing breaks when you bump your doqs pin.** Everything below is opt-in, except
one file that moved. Read this once and you are done.

## 1. There is one command now

```bash
bash doqs.sh check       # every gate, plus "are the generated files current?"
bash doqs.sh generate    # write every generated file, in the right order
bash doqs.sh list        # every command, and the scripts each one runs
```

`setup-tooling.sh` installs `doqs.sh` and `doqs.bat` in your repository root, next
to `syson.sh`. Run it once after the pin bump.

You do not have to change anything. `python doqs/scripts/validate_all.py` still
runs the same seven gates it always has, so your CI keeps working untouched.

## 2. `doqs check` is stricter than `validate_all.py`

`doqs check` runs the seven gates **plus** three checks on your committed generated
files:

- `resolve_params.py --table --check` — is `cad/params-table.csv` current?
- `resolve_instance.py --check` — are the resolved instance files current?
- `apply_licenses.py --check` — do the licence files match the templates?

So before you switch CI over, run `bash doqs.sh generate` once, read the diff, and
commit what it wrote. Then `doqs check` is green and you can change your workflow:

```yaml
- run: python doqs/doqs.py check
```

## 3. `docs/agent-guide.md` is gone

Read [using-doqs.md](using-doqs.md) instead. It holds everything that page had,
plus what to copy and what each gate checks. If your repository links to
`doqs/docs/agent-guide.md`, update the link.

## 4. You get a session hook, and it gets registered

`setup-tooling.sh` now installs `.claude/hooks/session-start.sh` and adds the line
that starts it to `.claude/settings.json`. The hook fills `doqs/` and `.agents/` at
the start of every session, which is what a cloud clone does not do for you.

Two things to know:

- **The hook file is doqs's.** It is overwritten when the template changes, like
  `doqs.sh` and `syson.sh`. If you already have a hand-written one, the first run
  replaces it — check that diff once.
- **The settings file is shared, and nothing is removed.** doqs adds the hook
  registration and the agent-CAD deny rules if they are missing, and leaves every
  other key, and the existing order, exactly as it is. If you delete a deny rule on
  purpose, the next run adds it back and `doqs check` fails while it is gone.

`doqs check` now also fails when the hook file is on disk and the settings file does
not run it. That combination looks set up and is not, which is the quietest way to
lose the tooling submodules.

## 5. Small things

- `check_names.py --warnings-only` did nothing and is removed. If a script of yours
  passes it, drop the flag.
- `build_graph.py` gained `--check`, which reports a stale `graph/usage-graph.json`
  instead of rewriting it. If your CI does `build_graph.py` followed by
  `git diff --exit-code graph/usage-graph.json`, one command replaces both:

  ```bash
  python doqs/scripts/build_graph.py --check
  ```

- `check_links.py --markdown` also checks relative markdown links. It is **off by
  default** so a pin bump cannot turn your repository red. Turn it on when you are
  ready to fix what it finds.

## 6. What did not change

- Every script under `doqs/scripts/` keeps its name and its command line.
- `validate_all.py` runs the same seven gates, in the same order, with the same
  output.
- `setup-tooling.sh` works the same way, and still installs the launchers.
- `templates/cad/build_model.py` is still a seed you copy per module by hand.
