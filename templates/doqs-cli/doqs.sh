#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The one doqs command. Run from the repo root:
#   bash doqs.sh check
#   bash doqs.sh list
# Installed by doqs/scripts/install_root_tools.py. Do not run this file from
# doqs/templates/doqs-cli/ — dirname would be wrong.
set -euo pipefail
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  python3 doqs/doqs.py "$@"
else
  python doqs/doqs.py "$@"
fi
