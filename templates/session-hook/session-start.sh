#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Check the tooling submodules out at the start of every session.
#
# Why this exists: a cloud session clones this repository without
# --recurse-submodules, so .agents/ and doqs/ stay empty. An agent then cannot
# read .agents/rules/*.md, .agents/skills/*, or doqs/docs/architecture.md, and
# cannot run doqs/scripts/validate_all.py. The folders exist, so the failure is
# silent: an agent that does not look reads no rules and keeps working.
#
# What this hook cannot do is start itself. Claude Code reads
# .claude/settings.json from the session's own project folder only. A session
# that opens a parent folder, or that attaches several repositories at once,
# never reads that file, so this hook never runs and prints nothing at all.
# CLAUDE.md carries the check that works in every session. See
# doqs/docs/using-doqs.md, section 3.
#
# The two git calls mirror setup-tooling.sh and must stay in that order:
#
#   1. --init --recursive checks every submodule out at its recorded pin.
#      Extracted machine modules under modules/ stay SHA-pinned, so this call
#      must never use --remote.
#   2. --remote -- doqs .agents moves only the tooling submodules to the latest
#      main. No --recursive here: it would reach doqs/.agents and move it off
#      the pin doqs records.
#
# No --checkout either, unlike the hook in doqs itself. That flag is only needed
# to override "update = none", which doqs sets on its own nested .agents. This
# repository sets it on neither tooling submodule, and git already honours the
# nested flag while recursing, so doqs/.agents stays unmounted and the kit is
# not mounted twice. See doqs/docs/using-doqs.md, section 3.
#
# --remote leaves the two gitlinks modified on purpose. See AGENTS.md, section
# "First step (required)": leave them uncommitted unless you mean to set a pin.
#
# This hook never stops a session. With no network it prints a message and
# exits 0.
#
# .cursor/environment.json runs this same script, so Cursor cloud agents get
# the same result from one implementation.

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

# A session start has no keyboard, so git must never wait for a password.
export GIT_TERMINAL_PROMPT=0

# timeout keeps a dead network from holding the session open.
run_git() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "$1" git "${@:2}" 2>&1
  else
    git "${@:2}" 2>&1
  fi
}

output="$(run_git 180 submodule update --init --recursive)"
status=$?

output+=$'\n'"$(run_git 120 submodule update --remote -- doqs .agents)"
remote_status=$?

# The marker files are the real test. Both commands above can exit 0 and still
# leave a folder empty -- git prints "Skipping submodule" and succeeds -- so an
# exit code on its own proves nothing.
# A plain string, not an array: "set -u" plus an empty array is an unbound
# variable in bash 3.2, which is what macOS still ships.
missing=""
[ -f ".agents/rules/core.md" ] || missing="${missing} .agents"
[ -f "doqs/scripts/validate_all.py" ] || missing="${missing} doqs"

if [ -z "$missing" ]; then
  kit="$(git -C .agents rev-parse --short HEAD 2>/dev/null || echo unknown)"
  tools="$(git -C doqs rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "Tooling submodules ready in ${root}: .agents/ (${kit}), doqs/ (${tools})."
  # The folders are usable even when only the first call succeeded, but then
  # they hold the recorded pins rather than the latest main. Say so, rather
  # than let a stale kit pass for a fresh one.
  if [ $remote_status -ne 0 ]; then
    echo "Could not reach the remotes, so both sit at their recorded pins, not the latest main."
    echo "Once you have a network again, run this from ${root}:"
    echo "  bash setup-tooling.sh"
  fi
  echo "Read .agents/rules/core.md first, then AGENTS.md."
  echo "Write every reply and every file in B2 English: .agents/rules/communication.md."
  exit 0
fi

echo "Could not check out:${missing} in ${root} (git exit codes ${status} and ${remote_status})."

# A failing clone repeats itself once per submodule per retry, so the raw output
# runs to dozens of lines. A session start is not the place for that: keep the
# lines that name the cause, and cap them.
reason="$(printf '%s\n' "$output" | grep -E '^(fatal|error):' | sort -u | head -4)"
if [ -n "$reason" ]; then
  echo "git said:"
  printf '%s\n' "$reason" | sed 's/^/  /'
fi
echo "The session continues, but rules, skills and the doqs validators are missing."
echo "Write every reply and every file in B2 English anyway: short sentences, common words."
echo "Once you have a network again, run this from ${root}:"
echo "  bash setup-tooling.sh"
exit 0
