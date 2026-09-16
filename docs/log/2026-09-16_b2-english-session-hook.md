# 2026-09-16 — The session hook names the language rule

**Role(s):** software

## What happened

`.agents/rules/communication.md` asks every agent to write in B2 English. The
rule covers chat replies, not only files. An agent that opens the file still
has to remember it while it writes. In a real session that failed: the agent
read the rule at the start and then wrote long, dense replies anyway. A person
had to ask for plain English by hand.

Work done:

- `.claude/hooks/session-start.sh` prints one more line when the agent kit is
  ready: `Write every reply and every file in B2 English:
  .agents/rules/communication.md.`
- The no-network branch prints a short version of the same line. The kit is
  missing there, so the path would help nobody, but the rule still holds.

The hook output goes into the agent's context at the start of every session.
The rule is now in front of the agent before it writes its first word.

## Decisions

Keep the line short and put the file path in it. The hook is not the place for
the rule itself; it is a pointer.

Each repository keeps its own copy of this hook. `templates/` holds no hook, so
this change covers doqs only. Machine repositories need the same one-line change
in their own hook.

## Next Steps

If this helps, `templates/` could grow a session-hook seed, and
`install_root_tools.py` could install it once per repository. That is a bigger
change: the doqs hook fetches one submodule, a machine hook fetches two.
