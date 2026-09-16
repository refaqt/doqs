# 2026-09-16 — Fixed what the documentation got wrong

**Role(s):** software

## What happened

The owner said doqs has become hard to use: "I don't know which files should be
run, what should be copied and what for." We mapped the repository before
changing anything. The map is in the plan for this clean-up; this entry records
the first step, which changes documentation only.

### Four contradictions

- **The licence map was written four times** and the code agreed with none of
  them. `LICENSE` is now the only full list. `README.md`, `AGENTS.md` and
  `docs/architecture.md` link to it instead of restating it. `LICENSE` also says
  which folders carry a `LICENSE` stub and which do not.
- **`AGENTS.md` said never to run `apply_licenses.py --root .`**, claiming it
  writes the machine kit. It does not: `apply_any_repo()` sees the tools repo and
  writes the GPL / CC BY-SA kit. `CONTRIBUTING.md` said the opposite and was
  right. Both now say the same thing.
- **`AGENTS.md` said `docs/log/` and `docs/mistakes/` do not exist.** Both exist,
  with an index each.
- **CI and `CONTRIBUTING.md` claimed to run the same commands** and did not.
  `CONTRIBUTING.md` had a licence check CI never ran; CI had a parameter check
  `CONTRIBUTING.md` never mentioned. Both lists now hold all eleven commands in
  the same order, and `tests/test_ci_matches_contributing.py` fails if they drift
  apart again.

### Three copies of source code, all drifted

`docs/architecture.md` printed the source of three scripts. Every copy had
drifted from the real file:

- A per-module `cad/resolve_params.py`, 24 lines below a sentence saying
  "Resolution is a doqs script, not a per-module copy".
- `validate_build.py`, with "In a full implementation this would…" where the real
  script resolves compositions inside families.
- `validate_okh.py`, skipping the submodule with a substring test the real code
  replaced.

All three are gone. Each section now says what the script promises and links to
it. `AGENTS.md` carries the rule: architecture states contracts and formats, and
never reproduces source.

### A script that never existed

`bom/process_bom.py` appeared three times, including 24 lines of its source. No
such file has ever shipped. The section beside it printed a second script,
`bom/aggregate_bom.py`, as something a machine repo owns — and qarve has a
hand-copied 30-line version of exactly that, kept by hand while
`doqs/scripts/aggregate_bom.py` sits in the submodule. Both listings are replaced
by a pointer to `resolve_bom.py` and `aggregate_bom.py`.

### One claim that sent a repository down the wrong path

`docs/architecture.md` said `build_graph.py` reads `known-consumers.toml`. It
does not — there is no such read anywhere in the script. qarve maintains that
file believing it feeds the usage graph. The text now says plainly that the file
is the agreed place to list external consumers, but that nothing reads it yet.

## Checked, and kept

`builds/example-baseline.toml` looked stale, because doqs ships no such template.
It is not: both folder trees show it as a file a **machine repo** owns, and qarve
has one. Left as it is.

## Numbers

`docs/architecture.md` is 227 lines shorter. 215 tests pass, up from 213. Every
command in the list passes.

## Next Steps

Step 2 of the plan: one command to run, `doqs.sh` / `doqs.bat`, so nobody has to
pick from nineteen script names.
