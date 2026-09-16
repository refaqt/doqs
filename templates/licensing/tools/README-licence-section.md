## Licence

This tools repository uses different licences for different kinds of content:

- **Software** (`scripts/`, `schemas/`, `tests/`, `tools/`, `.github/`) —
  [GPL-3.0](LICENSES/GPL-3.0.txt)
- **Documentation** (`docs/`, `templates/`, `data/`) —
  [CC BY-SA 4.0](LICENSES/CC-BY-SA-4.0.txt)

The executable launchers under `templates/` are GPL-3.0-or-later and carry SPDX
headers; `templates/cad/build_model.py` is a seed whose resulting per-module file
belongs to the machine repository. See [`templates/LICENSE`](templates/LICENSE).

`spec/otrl.ttl` is GPL-3.0-or-later from [iop-alliance/OpenKnowHow](https://github.com/iop-alliance/OpenKnowHow).

Machine repos that include this submodule use a **content-type split** (CERN-OHL-S hardware, GPL-3.0 firmware/software, CC BY-SA docs). See [docs/architecture.md](docs/architecture.md#licensing) and `python doqs/scripts/apply_licenses.py`.

The REFAQT name and logo, and the DOQS name and logo, are trademarks and are not covered by the above — see [TRADEMARKS.md](TRADEMARKS.md).

See [LICENSE](LICENSE) for the full overview and directory mapping.
