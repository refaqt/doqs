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
| `doqs/docs/naming-lexicon.md` | BOM and part display names |
| `doqs/skills/doqs-naming/SKILL.md` | Applying naming rules and validation commands |
| `doqs/templates/` | Creating dev-log, ADR, mistake, OKH entries |

The machine’s `docs/architecture.md` is a **short overview + pointer** to `doqs/docs/architecture.md`, not a second full spec.

### 3. DOQS naming skill in the machine repo

Install the skill from the submodule so Cursor can load it:

**Symlink (preferred):**

```powershell
# From machine repo root (PowerShell, admin may be required on Windows)
New-Item -ItemType SymbolicLink -Path ".cursor/skills/doqs-naming" -Target "doqs/skills/doqs-naming"
```

**Copy** when symlinks are unavailable (e.g. some CI clones).

Add a project rule from [doqs/templates/cursor-rule-doqs-naming.mdc](../templates/cursor-rule-doqs-naming.mdc) to `.cursor/rules/` in the machine repo.

### 4. If the submodule is missing or empty

```powershell
git submodule update --init --recursive
```

Without `doqs/`, validators and templates are unavailable — do not guess DOQS layout from memory.

## Updating the spec

- Change **process or cross-machine rules** → commit to **doqs** repo, bump submodule in machine repo(s).
- Change **Qarve-specific** behaviour → machine `docs/` and `.cursor/rules/` only.

## CI

Machine CI should checkout with `submodules: recursive` and run from the machine root:

```yaml
- uses: actions/checkout@v4
  with:
    submodules: recursive
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
- run: python doqs/scripts/validate_all.py
```

Optional release job:

```yaml
- run: python doqs/scripts/validate_okh.py --expected-version ${{ vars.RELEASE_VERSION }}
```

`validate_all.py` runs, in order: `validate_okh.py`, `check_names.py`, `check_links.py`, `validate_build.py`. Regenerate `graph/usage-graph.json` separately with `build_graph.py` when composition changes.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full gate list.
