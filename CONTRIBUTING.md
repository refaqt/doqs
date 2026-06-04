# Contributing to DOQS

DOQS is the **tools and specification** repository. Machine design work happens in machine repos (e.g. [qarve](https://github.com/refaqt/qarve)) with this repo as a submodule at `doqs/`.

## Machine repo workflow

1. Clone with submodules: `git clone --recurse-submodules …`
2. Work from the **machine repository root** (parent of `doqs/`).
3. After OKH, BOM, or path changes, run:

```powershell
python doqs/scripts/validate_all.py
```

4. Before a release tag, confirm manifest versions:

```powershell
python doqs/scripts/validate_okh.py --expected-version X.Y.Z
```

5. Regenerate the usage graph when composition changes (not part of `validate_all`):

```powershell
python doqs/scripts/build_graph.py
```

Commit updated `graph/usage-graph.json` with the change.

## PR validation gates

| Script | Purpose |
|--------|---------|
| `validate_all.py` | Runs all gates below in order |
| `validate_okh.py` | Required OKH fields, file refs, semver `version` |
| `check_names.py` | Module slugs, BOM ids/headers, model slugs, lexicon |
| `check_links.py` | SysML imports, OKH relative paths |
| `validate_build.py` | Lockfile interface compatibility |

Optional flags: `--root PATH`, `--strict-lexicon`, `--expected-version X.Y.Z`.

## Naming and versioning

See [docs/naming.md](docs/naming.md) and [docs/naming-lexicon.md](docs/naming-lexicon.md). Record product-specific exceptions as ADRs in the machine repo under `docs/decisions/`.

## Updating the doqs submodule in a machine repo

1. Commit and push changes in **doqs**.
2. In the machine repo: `git submodule update --remote doqs` (or pin a specific commit).
3. Commit the submodule pointer on the machine repo.

See [docs/agent-guide.md](docs/agent-guide.md) for Cursor skills and CI examples.

## Developing doqs itself

From this repository root:

```powershell
python -m compileall scripts
python -m unittest discover -s tests -p "test_*.py"
python scripts/check_names.py --root tests/fixtures/minimal-machine
```

CI runs the same checks on push and pull request.
