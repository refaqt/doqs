# doqs

Full guide: [AGENTS.md](AGENTS.md).

## Do this first, before anything else

This repository keeps its shared rules in the submodule `.agents/`. A session often starts
with that folder empty, and nothing warns you.

Run this in the folder that holds this file:

```bash
ls .agents/rules/core.md
```

If the file is missing, fill the folder, then check again:

```bash
git submodule update --init --remote --checkout .agents
```

`--checkout` is required here. `.gitmodules` marks `.agents` as `update = none`, so a plain
`git submodule update` skips it, exits 0, and downloads nothing.

The command needs a network. If it fails, say so in your reply, and say that you are working
without the shared rules.

A start-up hook does the same work, but only when the session opens this folder as its project
folder. A session that opens a parent folder, or that attaches several repositories, never runs
it and never says so. The check above always works.

## Then

Read `.agents/rules/core.md`, `.agents/rules/communication.md`, and `AGENTS.md`.

Write every reply and every file in B2 English: short sentences, common words.

Do not copy `setup-tooling.sh` here. That helper is a template this repository ships for machine
repositories.
