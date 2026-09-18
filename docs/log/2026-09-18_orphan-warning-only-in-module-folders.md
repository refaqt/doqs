# 2026-09-18 — The orphan warning only looks where a module can sit

**Role(s):** software

## What happened

The naming check warned about folders that the specification says are correct.
Every module may hold `docs/`, `firmware/`, `measurement/`, `simulation/` and
more. The check treated each of those folders, and everything inside them, as a
module that had lost its manifest. One machine repository reported twenty
warnings for a single module. Real warnings were hard to find among them.

The same check could also switch itself off without saying so. It compared
folder names along the full path to the repository. A repository stored in a
folder named `cad`, `bom` or `architecture` — for example `C:\work\cad\` — got
no orphan check at all. The same repository was checked in one place and
silently not checked in another.

Work done:

- The check now looks only where a module can sit: directly under a `modules/`
  folder, or under `modules/adapters/`. Content folders are never looked at, so
  no list of folder names is needed.
- The warning itself is unchanged: same wording, still a warning, never an
  error.
- Five tests cover the check. It had none before.
- `docs/naming.md` gained a short section, "Where a module may sit".

## Decisions

Decide where a module can live, then look only there. The old approach looked
everywhere and tried to excuse the folders it should not have opened. That list
of excuses can never be complete, because a module may hold any content folder.

## Next Steps

Machine repositories pick this up with their usual tools update. Warnings that
disappear were never real.

## Related

- [2026-09-18_orphan-check-read-the-path-to-the-repository.md](../mistakes/2026-09-18_orphan-check-read-the-path-to-the-repository.md)
- [naming.md, Where a module may sit](../naming.md)
