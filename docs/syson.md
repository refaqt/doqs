# SysON for DOQS machine repos

Eclipse [SysON](https://mbse-syson.org/) is a graphical SysML v2 editor. DOQS
keeps the **canonical** model as text in `architecture/*.sysml`. This adapter
starts SysON in Docker, creates a project named after the machine, imports
those files, and writes them back after you edit.

Do not use the homepage **Download** action to save work. That zip is SysON’s
internal JSON (models + diagram layouts), not SysML text.

## Once: install Docker Desktop

SysON’s server and PostgreSQL run in Docker. You install Docker Desktop once
per computer; the script starts the rest.

1. Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
   (Windows, macOS, or Linux).
2. On Windows, enable **WSL 2** if the installer asks.
3. Start Docker Desktop and wait until the engine is running.
4. In a terminal:

```powershell
docker version
```

If that fails, Docker is not on `PATH` or the engine is still starting.

You do **not** need to install Java, Node, or PostgreSQL yourself.

## Every session

Install Docker Desktop once (above). Then, from the **machine repository root**:

**Windows:** double-click `syson.bat` (created by `setup-tooling.bat` / `setup-tooling.sh`).

**macOS / Linux:** `bash syson.sh`

That starts a small **control panel** at `http://127.0.0.1:8765` (not the SysON editor). Use the buttons:

| Button | What it does |
| --- | --- |
| Open | Start SysON, import `architecture/*.sysml` if the project is new, open the graphical editor |
| Save | Export textual `.sysml` back into the repo |
| Reload | Delete the SysON project and re-import from git (**drops diagrams**) |
| Stop | Stop Docker containers; diagrams stay in the volume |
| Status | Docker engine, SysML files, and SysON projects |

Keep the console window open while you use the panel. Close it to quit the panel.

Agents and scripts can still call the same actions from the command line:

```powershell
python doqs/scripts/syson.py ui
python doqs/scripts/syson.py open
python doqs/scripts/syson.py save
```

`open` does not re-import when the project already exists, so diagrams stay.
Use **Reload** only when git should replace the SysON working copy.

Flags: `--root PATH`, `--url http://localhost:8080`, `--name "…"`,
`--no-browser`.

## Import and export (what the UI is doing)

| Action | Result |
| --- | --- |
| Script `open` / explorer **Upload** of a `.sysml` file | Textual SysML → SysON model |
| Script `save` / explorer **Download** on a document named `*.sysml` | SysON model → textual SysML |
| Homepage **… → Download** | JSON zip (models + diagrams). Not for git. |
| Homepage **Upload project** | Expects that JSON zip, not `.sysml` |

Homepage download is a valid **backup of diagrams** on your machine. It is
not the DOQS source of truth. Diagrams live in the local Docker volume;
shared review uses `architecture/*.sysml`.

## Troubleshooting

- **`Docker is not installed`:** follow the Once section above.
- **`engine is not running`:** start Docker Desktop and wait.
- **Port 8765 already in use:** the control panel is probably already open.
  Use that tab, or close the other console window.
- **Export is JSON:** you used homepage Download, or the document is not
  named `*.sysml`. Use `python doqs/scripts/syson.py save`.
- **`save` dropped comments or `: Real`:** SysON’s textual exporter does not
  round-trip perfectly. Review `git diff` before committing. Standard-library
  types such as `Real` may need a library import in SysON.
- **Lost diagrams after `reload`:** that command is meant to reset from git.
  Use `open` + `save` for the normal loop.
- **`docker compose down -v`:** deletes the volume and all local SysON data.

Pinned image: `eclipsesyson/syson:v2026.7.0` in
`tools/syson/docker-compose.yml`. Override with `IMAGE_TAG` if needed.
