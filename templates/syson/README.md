# Copy-once: SysON control panel launcher

Copy `syson.bat` (Windows) and/or `syson.sh` (macOS/Linux) to the **machine
repository root** and run them from there. Do not run them from this folder —
`dirname` / `%~dp0` would be `doqs/templates/syson/`, not the repo root.

Double-click `syson.bat` (or run `bash syson.sh`) to open a local control
panel at `http://127.0.0.1:8765`. Agents should use
`python doqs/scripts/syson.py ui` instead of the `.bat`.

See [docs/syson.md](../../docs/syson.md).
