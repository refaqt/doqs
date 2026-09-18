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
| `gitignore.snippet` | append to the root `.gitignore` |

Then run `python doqs/scripts/apply_licenses.py --root .` at the library root.
It detects the marker and writes the library licence kit: CC BY-SA 4.0 for the
record you compile, and a carve-out for every `cad/` and `docs/datasheets/`
directory, because those hold the brand's own work.

**Do not** copy a `LICENSE` by hand. `apply_licenses.py` renders them.
