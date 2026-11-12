#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2025-2026 Refaqt (BE 0804.145.539) and contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# Copy to the consumer repo root and run from there:
#   bash syson.sh
# Do not run this file from doqs/templates/syson/ — dirname would be wrong.
set -euo pipefail
cd "$(dirname "$0")"
echo "Starting SysON control panel. Close this terminal to quit."
python3 doqs/scripts/syson.py ui
