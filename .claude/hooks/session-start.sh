#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Download the shared agent kit into .agents/ at the start of every session.
#
# Why this exists: a session container clones doqs without
# --recurse-submodules, so .agents/ stays empty and an agent cannot read
# .agents/rules/*.md or .agents/skills/*. This hook fetches the kit itself.
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

root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$root" || exit 0

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
  echo "Shared agent kit ready at .agents/ (commit ${pin}). Read .agents/rules/core.md first."
  echo "Write every reply and every file in B2 English: .agents/rules/communication.md."
  exit 0
fi

echo "Could not download the shared agent kit into .agents/ (git exit code ${status})."
if [ -n "$output" ]; then
  echo "git said: ${output}"
fi
echo "The session continues, but the rules and skills under .agents/ are missing."
echo "Write every reply and every file in B2 English anyway: short sentences, common words."
echo "Once you have a network again, run:"
echo "  git submodule update --init --remote --checkout .agents"
exit 0
