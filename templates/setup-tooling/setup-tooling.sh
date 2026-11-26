#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2025-2026 Refaqt (BE 0804.145.539) and contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# Copy to the consumer repo root and run from there:
#   bash setup-tooling.sh           fill .agents/ and doqs/, then install the root tools
#   bash setup-tooling.sh --check   only say whether both folders are filled
# Do not run this file from doqs/templates/setup-tooling/ — dirname would be wrong.
set -euo pipefail
cd "$(dirname "$0")"
if [ "${1:-}" = "--check" ]; then
  # The marker files are the real test: an empty folder still exists.
  missing=""
  for marker in .agents/rules/core.md doqs/scripts/validate_all.py; do
    if [ -f "$marker" ]; then
      echo "ok    $marker"
    else
      echo "FAIL  $marker is missing"
      missing=1
    fi
  done
  if [ -n "$missing" ]; then
    echo "Fill the folders with: bash setup-tooling.sh"
    exit 1
  fi
  exit 0
fi
git submodule sync --recursive
# Check out every submodule at its recorded pin. Extracted modules under
# modules/ stay SHA-pinned, so this must not use --remote.
git submodule update --init --recursive
# Only the tooling submodules track main. No --recursive here: it would reach
# doqs/.agents and move it off the pin doqs records.
git submodule update --remote -- doqs .agents
if command -v python3 >/dev/null 2>&1; then
  python3 doqs/scripts/install_root_tools.py
else
  python doqs/scripts/install_root_tools.py
fi
