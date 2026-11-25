# <your machine>

Full guide: [AGENTS.md](AGENTS.md).

## Do this first, before anything else

This repository keeps its rules and its checks in two submodules: `.agents/` and `doqs/`.
A session often starts with both folders empty, and nothing warns you.

Run this in the folder that holds this file:

```bash
ls .agents/rules/core.md doqs/scripts/validate_all.py
```

If either file is missing, fill the folders, then check again:

```bash
bash setup-tooling.sh
```

`setup-tooling.sh` needs a network. If it fails, say so in your reply, and say that you are
working without the shared rules.

**In plan mode, run it too.** Plan mode blocks commands that change files, so ask the user to
approve this one. It only fills the two tooling folders and changes no file that git tracks. Do
not plan without the rules.

A start-up hook does the same work, but only when the session opens this folder as its project
folder. It runs in every mode, plan mode too. A session that attaches several repositories, or a
thread inside a Claude project, never runs it and never says so. The check above always works.

## Then

Read `.agents/rules/core.md`, `.agents/rules/communication.md`, and `AGENTS.md`.

Write every reply and every file in B2 English: short sentences, common words.

Never commit inside `.agents/` or `doqs/`. Those folders belong to their own repositories.
