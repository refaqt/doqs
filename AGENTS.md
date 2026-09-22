# Working on doqs — agent instructions

Start here if you are an agent (Cursor, Claude Code, or similar) changing **this** repository:
the validators, templates and specification.

Working in a machine repository that has doqs as a submodule is a different job. That is
[docs/using-doqs.md](docs/using-doqs.md).

## First step (required)

Check the shared agent kit before you read its rules or skills. Run this from the repository
root:

```bash
ls .agents/rules/core.md
```

If the file is missing, fill the folder and update it to the latest `main`:

```bash
git submodule update --init --remote --checkout .agents
```

`--checkout` is required: `.gitmodules` marks `.agents` as `update = none`, so a plain
`git submodule update` skips it. See [Shared kit](#shared-kit) for why.

In Claude Code a `SessionStart` hook runs that command for you. It lives in
[`.claude/hooks/session-start.sh`](.claude/hooks/session-start.sh) and is registered in
[`.claude/settings.json`](.claude/settings.json). It matters most in a cloud session, where the
container clones this repo without `--recurse-submodules` and `.agents/` starts empty. The hook
never stops a session: with no network it prints a message and lets the session run.

Do not trust the hook blindly. It runs only when the session opens **this folder** as its
project folder. Claude Code reads `.claude/settings.json` from that folder only, so a session
that opens a parent folder, or that attaches several repositories at once, never reads the file,
never starts the hook, and prints nothing at all. Silence and success look the same. The `ls`
check above is the only step that works in every session, in every tool.

Do **not** copy `setup-tooling.sh` to this root. That helper is a template this repo *ships* for
machine repos (see [`templates/setup-tooling/`](templates/setup-tooling/)); it runs
`doqs/scripts/install_root_tools.py`, a path that does not exist here because this **is** doqs.

Leave the moved `.agents` gitlink uncommitted unless you mean to freeze a new pin.

## Shared kit

This repo mounts [refaqt/refaqt-agents](https://github.com/refaqt/refaqt-agents) at [`.agents/`](.agents/).

1. Read [`.agents/rules/core.md`](.agents/rules/core.md),
   [`.agents/rules/communication.md`](.agents/rules/communication.md),
   [`.agents/rules/living-docs.md`](.agents/rules/living-docs.md), and
   [`.agents/rules/reporting.md`](.agents/rules/reporting.md).
2. Read [`docs/decisions/`](docs/decisions/) before larger work, and say which decisions apply.
3. Read [`docs/architecture.md`](docs/architecture.md) before any change to the DOQS specification.
4. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for the gate list you must run before a pull request.

Write every reply and every file in B2 English. Follow `.agents/rules/communication.md`.
Keep licence names, file paths, script names, and version numbers exact.

Write pull requests, commit messages, comments on GitHub and log entries in the shape
`.agents/rules/reporting.md` gives. The box on GitHub already starts with those headings,
from [`.github/pull_request_template.md`](.github/pull_request_template.md).

## This repository

doqs is the **tools and specification** repository: validators, schemas, templates, and the
canonical architecture spec. Machine repos (for example [qarve](https://github.com/refaqt/qarve))
mount it at `doqs/`. Machine design work does **not** happen here.

Machine repos mount this repo at `doqs/` and already mount the same kit at their own
`.agents/`. To stop a second copy appearing at `doqs/.agents/`, `.gitmodules` sets
`update = none` on this submodule. Git then skips it in a consumer repo — on
`git clone --recurse-submodules`, on `git submodule update --recursive`, and in CI with
`submodules: recursive`. The machine's own `.agents/` is the only kit there.

That flag is also why the first step above needs `--checkout`: it overrides `update = none`
so the kit is checked out when you work on doqs on its own.

| You are adding | It goes in |
| --- | --- |
| Why a choice was made | `docs/decisions/YYYY-MM-DD_topic.md` |
| A day's work write-up | `docs/log/YYYY-MM-DD_topic.md` |
| Something that went wrong | `docs/mistakes/YYYY-MM-DD_topic.md` |

Each of those folders has a `README.md` index. Update the index when you add a file.

Skills that belong only to this repo go in `.agents-local/skills/` (not inside the submodule).

### Writing `docs/architecture.md`

That file states contracts and formats. It never reproduces the source of a script: a copy drifts
from the real file and then teaches the wrong thing. Describe what a script promises and link to it.

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
`tests/fixtures/`. `python scripts/apply_licenses.py --root .` is safe here: the script sees the
tools repo and writes the GPL / CC BY-SA kit, not the machine CERN-OHL-S one. Use `--check` when
you only want to know whether the files are current.

### Licensing

[LICENSE](LICENSE) says which licence applies where. It is the only full list; do not repeat it
in another file. A new `.py`, `.sh` or `.bat` file under `templates/` needs an
`SPDX-License-Identifier` header — see [`templates/LICENSE`](templates/LICENSE).

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

## Working in a machine repository instead

This file is for agents changing **doqs itself**. Everything about using doqs in a machine
repository is in [docs/using-doqs.md](docs/using-doqs.md).
