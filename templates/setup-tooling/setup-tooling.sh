#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copy to the consumer repo root and run from there:
#   bash setup-tooling.sh
# Do not run this file from doqs/templates/setup-tooling/ — dirname would be wrong.
set -euo pipefail
cd "$(dirname "$0")"
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
