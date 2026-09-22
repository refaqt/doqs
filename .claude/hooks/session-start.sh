#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Download the shared agent kit into .agents/ at the start of every session.
#
# Why this exists: a session container clones doqs without
# --recurse-submodules, so .agents/ stays empty and an agent cannot read
# .agents/rules/*.md or .agents/skills/*. This hook fetches the kit itself.
#
# What this hook cannot do is start itself. Claude Code reads
# .claude/settings.json from the session's own project folder only. A session
# that opens a parent folder, or that attaches several repositories at once,
# never reads that file, so this hook never runs and prints nothing at all.
# CLAUDE.md carries the check that works in every session.
#
# --checkout is required. .gitmodules marks .agents as "update = none", so a
# plain "git submodule update --init --remote .agents" prints
# "Skipping submodule '.agents'", exits 0, and downloads nothing.
#
# --remote moves the .agents gitlink to the latest main. That change stays
# uncommitted on purpose. See AGENTS.md, section "First step (required)".
#
# This hook never stops a session. With no network it prints a message and
# exits 0.

set -uo pipefail

# Find the repository root from this script's own place on disk.
#
# The file always sits at <root>/.claude/hooks/session-start.sh, so its own
# folder gives the answer. $CLAUDE_PROJECT_DIR does not: a session that attaches
# more than one repository opens their shared parent folder and sets the
# variable to it. That folder is not a git repository, so every git call below
# would fail and nothing would say why.
start_dir="$PWD"
self="${BASH_SOURCE[0]:-$0}"
here="$(cd "$(dirname "$self")" 2>/dev/null && pwd -P)"

# Print the top folder of the git work tree that holds "$1", or print nothing.
work_tree() {
  [ -n "${1:-}" ] || return 1
  git -C "$1" rev-parse --show-toplevel 2>/dev/null
}

# Take the folder next to this script only when it really is .claude/hooks, so
# a stray copy somewhere else cannot guess two levels up.
root=""
case "$here" in
  */.claude/hooks) root="$(work_tree "$here/../..")" ;;
esac
[ -n "$root" ] || root="$(work_tree "${CLAUDE_PROJECT_DIR:-}")"
[ -n "$root" ] || root="$(work_tree "$start_dir")"

if [ -z "$root" ]; then
  echo "The session hook found no git repository, so it checked nothing out."
  echo "It looked next to itself (${here:-unknown}), at CLAUDE_PROJECT_DIR"
  echo "(${CLAUDE_PROJECT_DIR:-not set}), and at ${start_dir}."
  echo "The session continues, but the shared rules are missing."
  echo "Write every reply and every file in B2 English anyway: short sentences, common words."
  exit 0
fi

cd "$root" || exit 0

# Say it only when it is worth saying. In a normal session these are the same.
[ "$root" = "$start_dir" ] || echo "Session hook: the repository root is ${root}, not ${start_dir}."

marker=".agents/rules/core.md"

# A session start has no keyboard, so git must never wait for a password.
export GIT_TERMINAL_PROMPT=0

update_kit() {
  # timeout keeps a dead network from holding the session open.
  if command -v timeout >/dev/null 2>&1; then
    timeout 120 git submodule update --init --remote --checkout .agents 2>&1
  else
    git submodule update --init --remote --checkout .agents 2>&1
  fi
}

output="$(update_kit)"
status=$?

# The marker file is the real test. The command above can exit 0 and still
# leave .agents/ empty, so an exit code on its own proves nothing.
if [ -f "$marker" ]; then
  pin="$(git -C .agents rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "Shared agent kit ready in ${root}: .agents/ (commit ${pin}). Read .agents/rules/core.md first."
  echo "Write every reply and every file in B2 English: .agents/rules/communication.md."
  exit 0
fi

echo "Could not download the shared agent kit into ${root}/.agents/ (git exit code ${status})."
if [ -n "$output" ]; then
  echo "git said: ${output}"
fi
echo "The session continues, but the rules and skills under .agents/ are missing."
echo "Write every reply and every file in B2 English anyway: short sentences, common words."
echo "Once you have a network again, run this from ${root}:"
echo "  git submodule update --init --remote --checkout .agents"
exit 0
