# Agent guide

Start here if you are an agent (Cursor, Claude Code, or similar) working in this repository.

## First step (required)

Update the shared agent kit to the latest `main` before you read its rules or skills:

```bash
git submodule update --init --remote .agents
```

Do **not** copy `setup-tooling.sh` to this root. That helper is a template this repo *ships* for
machine repos (see [`templates/setup-tooling/`](templates/setup-tooling/)); it runs
`doqs/scripts/install_root_tools.py`, a path that does not exist here because this **is** doqs.

Leave the moved `.agents` gitlink uncommitted unless you mean to freeze a new pin.

## Shared kit

This repo mounts [refaqt/refaqt-agents](https://github.com/refaqt/refaqt-agents) at [`.agents/`](.agents/).

1. Read [`.agents/rules/core.md`](.agents/rules/core.md),
   [`.agents/rules/communication.md`](.agents/rules/communication.md), and
   [`.agents/rules/living-docs.md`](.agents/rules/living-docs.md).
2. Read [`docs/decisions/`](docs/decisions/) before larger work, and say which decisions apply.
3. Read [`docs/architecture.md`](docs/architecture.md) before any change to the DOQS specification.
4. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for the gate list you must run before a pull request.

Write every reply and every file in B2 English. Follow `.agents/rules/communication.md`.
Keep licence names, file paths, script names, and version numbers exact.

## This repository

doqs is the **tools and specification** repository: validators, schemas, templates, and the
canonical architecture spec. Machine repos (for example [qarve](https://github.com/refaqt/qarve))
mount it at `doqs/`. Machine design work does **not** happen here.

Because machine repos mount this repo, a recursive clone there also fetches `doqs/.agents`,
next to the machine's own `.agents/`. Both track `main`, so they hold the same kit.

| You are adding | It goes in |
| --- | --- |
| Why a choice was made | `docs/decisions/YYYY-MM-DD_topic.md` |
| A day's work write-up | `docs/log/YYYY-MM-DD_topic.md` |
| Something that went wrong | `docs/mistakes/YYYY-MM-DD_topic.md` |

`docs/log/` and `docs/mistakes/` do not exist yet. Create the one you need from
[`.agents/bootstrap/docs/`](.agents/bootstrap/docs/) the first time you have an entry for it.

Skills that belong only to this repo go in `.agents-local/skills/` (not inside the submodule).

### Branching

Every task that changes this repo starts on a **new git branch** off `main`, unless the user
says otherwise. Do not land task work as commits directly on `main`.

### Validation

Run the gates from this repository root, not from a machine root. The full list is in
[CONTRIBUTING.md](CONTRIBUTING.md#developing-doqs-itself); the usual pair while editing is:

```bash
python -m unittest discover -s tests -p "test_*.py"
python scripts/validate_licenses.py --root .
```

The validators under `scripts/` take `--root` pointing at a machine repo or at a fixture in
`tests/fixtures/`. Never run `python scripts/apply_licenses.py --root .` — that writes the
machine CERN-OHL-S kit, and this repo uses the tools-repo split instead.

### Licensing

This repo splits licences by content type: GPL-3.0 for `scripts/`, `schemas/`, `tests/`,
`tools/`, `.github/` and `.cursor/`; CC BY-SA 4.0 for `docs/`, `templates/` and `data/`.
A new `.py`, `.sh` or `.bat` file under `templates/` needs an `SPDX-License-Identifier`
header. See [LICENSE](LICENSE) and [`templates/LICENSE`](templates/LICENSE).

## Skills

| Skill | Path |
| --- | --- |
| Activity log | `.agents/skills/log/SKILL.md` |
| Mistake log | `.agents/skills/mistake-log/SKILL.md` |
| Maintain patterns | `.agents/skills/maintain-patterns/SKILL.md` |
| DOQS naming | `.agents/skills/doqs-naming/SKILL.md` |
| FreeCAD debugging | `.agents/skills/freecad/SKILL.md` |

The kit also carries role skills under `.agents/skills/{category}/{skill-name}/SKILL.md`
(`business/`, `engineering/`, `supply-chain/`, `compliance/`, `legal/`, `governance/`, `web3/`).

## DOQS spec pointers

[docs/agent-guide.md](docs/agent-guide.md) lists which specification file to read for which kind
of work, and the validation commands machine repos run.
