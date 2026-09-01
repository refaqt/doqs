#!/usr/bin/env bash
# Copy to the consumer repo root and run from there:
#   bash setup-tooling.sh
# Do not run this file from doqs/templates/setup-tooling/ — dirname would be wrong.
set -euo pipefail
cd "$(dirname "$0")"
git submodule sync --recursive
git submodule update --init --recursive --remote
if command -v python3 >/dev/null 2>&1; then
  python3 doqs/scripts/install_root_tools.py
else
  python doqs/scripts/install_root_tools.py
fi
