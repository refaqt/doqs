# ADR-001 — Naming and versioning conventions

- **Date:** 2026-06-04
- **Status:** Accepted

## Context

DOQS machine repos need consistent module folder names, BOM part IDs, and version fields across Git, OKH manifests, lockfiles, and exported drawings. Ad hoc naming causes broken paths, ambiguous BOM references, and conflicting version numbers in CAD files versus Git tags.

## Decision

1. **Module folders** use kebab-case functional slugs (`x-axis`, `drive-belt`). Structural variants use a suffix (`x-axis-belt`). Adapters use `modules/adapters/<from>-to-<to>/`.
2. **BOM part IDs** use `PREFIX-NNN` (three-digit sequence, category prefix per module). Prefixes are defined in [naming.md](../naming.md).
3. **Display names** should follow the [naming lexicon](../naming-lexicon.md); validators warn on unknown tokens.
4. **Authoritative version** is semver in `okh.toml` without a `v` prefix, mirrored by Git tag `vX.Y.Z` and lockfile pins. FreeCAD files keep a stable `Comment` pointing to `okh.toml`; drawing revisions mirror semver at export (hybrid ISO 7200 practice).
5. **Enforcement** via `doqs/scripts/check_names.py`, extended `validate_okh.py`, and `validate_all.py` in machine CI.

## Consequences

- Machine repos must fix legacy names (e.g. `belt-drive` → `drive-belt`, `SW-01` → `SW-001`) incrementally.
- The doqs repo includes fixture tests under `tests/fixtures/minimal-machine/`.
- Product-specific overrides remain in machine `docs/decisions/` only when they differ from this ADR.
