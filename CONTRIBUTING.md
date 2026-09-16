# Contributing to DOQS

DOQS is the **tools and specification** repository. Machine design work happens in machine repos (e.g. [qarve](https://github.com/refaqt/qarve)) with this repo as a submodule at `doqs/`.

## Working in a machine repository

Everything about *using* doqs — what to run, what gets copied, what each gate
checks, how to set CI up — is on one page:
**[docs/using-doqs.md](docs/using-doqs.md)**.

The short version: `bash doqs.sh check` before every commit, `bash doqs.sh generate`
after changing anything generated, and `bash doqs.sh list` when you forget a command.

The rest of this file is about changing doqs itself.

## Naming and versioning

See [docs/naming.md](docs/naming.md) and [docs/naming-lexicon.md](docs/naming-lexicon.md). Record product-specific exceptions as ADRs in the machine repo under `docs/decisions/`.

## Branching

Every task that changes the repo must start on a **new git branch** off `main`, unless the user explicitly says otherwise. Do not land task work as commits directly on `main`.

## Developing doqs itself

From this repository root:

```powershell
python -m compileall scripts templates doqs.py
python -m unittest discover -s tests -p "test_*.py"
python scripts/check_names.py --root tests/fixtures/minimal-machine
python scripts/validate_okh.py --root tests/fixtures/minimal-machine
python scripts/validate_licenses.py --root tests/fixtures/minimal-machine
python scripts/validate_licenses.py --root .
python scripts/apply_licenses.py --check --root .
python scripts/validate_all.py --root tests/fixtures/variant-family
python scripts/validate_all.py --root tests/fixtures/variant-machine
python scripts/check_links.py --root . --markdown
python doqs.py check --root tests/fixtures/variant-family
python doqs.py check --root tests/fixtures/variant-machine
python doqs.py list
python scripts/resolve_params.py --root tests/fixtures/variant-family --table --check
python scripts/resolve_instance.py --root tests/fixtures/variant-machine --check
```

`tests/fixtures/variant-family/` is a worked product family (three lengths, two
drive options, two feedback options, two compositions) and
`tests/fixtures/variant-machine/` is a machine consuming it at two different
lengths. Both carry committed generated files, so a change to a resolver that
alters output will fail the `--check` runs until the fixtures are regenerated.

`validate_licenses.py --root .` and `apply_licenses.py --check --root .` check the **tools-repo** kit (GPL-3.0 / CC BY-SA). Both are safe to run here: the scripts see the tools repo and never write the machine CERN-OHL-S kit.

CI runs this same list, in this order, on push and pull request. A test keeps the two in step: if you add a command here, add it to `.github/workflows/ci.yml` as well, or `tests/test_ci_matches_contributing.py` fails.
