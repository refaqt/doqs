#!/usr/bin/env bash
# Copy to the consumer repo root and run from there:
#   bash syson.sh
# Do not run this file from doqs/templates/syson/ — dirname would be wrong.
set -euo pipefail
cd "$(dirname "$0")"
echo "Starting SysON control panel. Close this terminal to quit."
python3 doqs/scripts/syson.py ui
