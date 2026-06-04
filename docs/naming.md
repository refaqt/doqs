# Naming conventions (draft)

Conventions for **machines**, **modules**, **parts**, and repository names across DOQS projects. This document will be expanded with Refaqt-specific rules.

## Principles

- Names should be stable, URL-safe, and meaningful in Git paths.
- A **machine** is the top-level product (repository root module).
- A **module** is any folder with the standard DOQS layout and an `okh.toml`.
- A **part** is a manufactured item declared inline in OKH or as a leaf module.

## Current examples

| Kind | Example | Repository |
|------|---------|------------|
| Machine | Qarve | `github.com/refaqt/qarve` |
| Tools | DOQS | `github.com/refaqt/doqs` |
| Module | `x-axis`, `frame` | Path under `modules/` |

## Open questions (to decide)

- [ ] Machine repo naming: product codename vs descriptive (`qarve` vs `cnc-mill-300`)?
- [ ] Extracted module repos: same name as folder (`x-axis`) or prefixed (`qarve-x-axis`)?
- [ ] Part IDs in BOM: prefix by module (`XA-01`) vs global (`QRV-01`)?
- [ ] Interface names: `{Assembly}{Role}Interface` + semver in SysML port name?
- [ ] Parametric model slugs: `500mm`, `500mm-hd` — charset and max length?

Record decisions as ADRs in the **machine** repo under `docs/decisions/` once agreed.
