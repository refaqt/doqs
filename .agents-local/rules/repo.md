# doqs: rules for this repository

doqs is the **tools and specification** repository: validators, schemas, templates, and the
specification. Machine repositories (for example [qarve](https://github.com/refaqt/qarve)) mount it
at `doqs/`. Machine design work does not happen here. Using doqs in a machine repository is
explained in [docs/using-doqs.md](../../docs/using-doqs.md).

- **The first step needs `--checkout`.** `.gitmodules` sets `update = none` on `.agents`, so a
  machine repository does not get a second kit at `doqs/.agents/`. A plain
  `git submodule update` then skips the folder and still exits 0.
- **Do not copy `setup-tooling.sh` to this root.** It is a template for machine repositories, and
  it calls `doqs/scripts/install_root_tools.py`, a path that does not exist here.
- **The specification** is `docs/architecture.md` (a short overview) and the topic pages in
  `docs/architecture/`. Read only the page you change. Describe what a script promises and link to
  it. Never copy a script's source into the docs: the copy drifts.
- **Licences.** [LICENSE](../../LICENSE) is the only full list of which licence applies where. A new
  `.py`, `.sh` or `.bat` file under `templates/` needs an `SPDX-License-Identifier` line.
- **Before a pull request**, run the gates in
  [CONTRIBUTING.md](../../CONTRIBUTING.md#developing-doqs-itself) from this root. Usually:
  `python -m unittest discover -s tests -p "test_*.py"` and
  `python scripts/validate_licenses.py --root .`. Validators take `--root`, pointing at a machine
  repository or a fixture in `tests/fixtures/`.
- `tests/test_export_variant.py` has one test that fails on a machine where FreeCAD is installed.
  It expects no FreeCAD binary.
