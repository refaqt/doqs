# Parts-library kit

Files for a new **parts library**: a repository recording parts other people
design, make and sell. The specification is
[docs/parts-library.md](../../docs/parts-library.md); the decision behind it is
[ADR-004](../../docs/decisions/2026-09-18_parts-library.md).

| Template | Copy to |
| --- | --- |
| `library.toml` | the repository root — this file is what makes it a library |
| `brand-okh.toml` | `modules/<brand>/okh.toml` |
| `family-okh.toml` | `modules/<brand>/modules/<family>/okh.toml` |
| `bom/parts.csv` | `modules/<brand>/modules/<family>/bom/parts.csv` |
| `cad/own/features.csv` | `modules/<brand>/modules/<family>/cad/own/<pn>.features.csv`, filled in before you model |
| `cad/own/params.csv` | `.../cad/own/<pn>.params.csv`: every value the build uses, and where it came from |
| `cad/own/build.py` | `.../cad/own/<pn>.build.py`: the script that builds the model |
| `cad/own/checks.csv` | `.../cad/own/<pn>.checks.csv`: whether the model matches the brand's |
| `gitignore.snippet` | append to the root `.gitignore` |

Then run `python doqs/scripts/apply_licenses.py --root .` at the library root.
It detects the marker and writes the library licence kit: CC BY-SA 4.0 for the
record you compile, and a carve-out for every `cad/` and `docs/datasheets/`
directory, because those hold the brand's own work. A `cad/own/` directory is
carved back to CC BY-SA: it holds models we drew ourselves from the datasheet.

For a **private** library, uncomment `private = true` in `library.toml` first.
Then `apply_licenses.py` writes an internal-use `LICENSE` and no CC BY-SA, and
each `okh.toml` names the supplier's licence. See
[docs/parts-library.md](../../docs/parts-library.md#a-private-library).

**Do not** copy a `LICENSE` from these templates by hand. `apply_licenses.py`
renders them. The one exception is a supplier's own licence text in a private
library: copy that from the supplier into the brand or family folder.
