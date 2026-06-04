# Agent workflow — machine repo + DOQS submodule

## Is the submodule approach correct?

**Yes.** For DOQS, a Git submodule at `doqs/` in each machine repo is the intended model:

| Approach | Verdict |
|----------|---------|
| **`doqs/` submodule** | Recommended — same path as the architecture spec; scripts stay `python doqs/scripts/...`; pin a known tools version per machine release |
| Copy-paste `doqs/` into each machine | Avoid — drift between machines |
| Publish `doqs` only as pip package | Possible later; submodule is enough for now |
| Monorepo with machine + tools | Fine for solo dev; split before collaborators need independent tool releases |

**Workflow:** develop tools in `github.com/refaqt/doqs`, push, then in the machine repo bump the submodule pointer (`git submodule update --remote` or pin a commit).

## What agents read (Cursor)

Two layers work together:

### 1. Machine repo `.cursor/` (always-on behaviour)

In [qarve](https://github.com/refaqt/qarve), project rules under `.cursor/rules/` and `.cursor/skills/` load automatically:

- No `.FCStd` edits, SysML for requirements, validators after OKH changes, prompts log, etc.
- These rules are **short** and **machine-specific** (FreeCAD version, module list).

**Keep machine `.cursor/` in the machine repo** — it is not replaced by the submodule.

### 2. `doqs/` submodule (canonical specification)

Agents doing structural or process work should read:

| File | When |
|------|------|
| `doqs/docs/architecture.md` | Non-trivial design, new modules, versioning, interfaces, builds |
| `doqs/docs/readiness-levels.md` | Setting or explaining OTRL/ODRL in `okh.toml` |
| `doqs/docs/naming.md` | Naming modules, parts, repos |
| `doqs/templates/` | Creating dev-log, ADR, mistake, OKH entries |

The machine’s `docs/architecture.md` is a **short overview + pointer** to `doqs/docs/architecture.md`, not a second full spec.

### 3. If the submodule is missing or empty

```powershell
git submodule update --init --recursive
```

Without `doqs/`, validators and templates are unavailable — do not guess DOQS layout from memory.

## Updating the spec

- Change **process or cross-machine rules** → commit to **doqs** repo, bump submodule in machine repo(s).
- Change **Qarve-specific** behaviour → machine `docs/` and `.cursor/rules/` only.

## CI

Machine CI should checkout with `submodules: recursive` and run `python doqs/scripts/*.py` from the machine root.
