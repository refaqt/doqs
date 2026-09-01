# SysON control panel launcher

`setup-tooling.sh` / `.bat` copies `syson.bat` and `syson.sh` to the **machine
repository root**. Do not run them from this folder — `dirname` / `%~dp0`
would be `doqs/templates/syson/`, not the repo root.

Double-click `syson.bat` (or run `bash syson.sh`) to open a local control
panel at `http://127.0.0.1:8765`. Agents should use
`python doqs/scripts/syson.py ui` instead of the `.bat`.

See [docs/syson.md](../../docs/syson.md).
