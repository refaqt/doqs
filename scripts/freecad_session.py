"""Find out how an agent can reach FreeCAD, and start the connection if it can.

    python doqs/scripts/freecad_session.py status [--file cad/rail.FCStd] [--json]
    python doqs/scripts/freecad_session.py autostart
    python doqs/scripts/freecad_session.py start [cad/rail.FCStd] [--wait 60]

The freecad-mcp add-on runs an RPC server inside the FreeCAD window. No MCP
tool can start that server, and nothing can reach a window whose server is
off. The add-on can start the server by itself each time FreeCAD starts: it
reads ``auto_start_rpc`` from ``freecad_mcp_settings.json`` in FreeCAD's user
data folder. So an agent can:

* switch that setting on (``autostart``), and
* start FreeCAD when no FreeCAD runs (``start``), then wait for the server.

It cannot switch on the server of a window that is already open. ``status``
says so, and says which way to edit is safe now (``advice``):

* ``mcp``      - the window answers. Edit an open document through MCP.
* ``headless`` - no FreeCAD runs. ``FreeCADCmd`` cannot overwrite a window.
* ``ask-user`` - FreeCAD runs but does not answer. Nobody can see which files
  it has open, so headless is not safe. Ask the person to click
  **Start RPC Server**, once.

See docs/agent-cad.md, "Headless or MCP: the agent decides".
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import xmlrpc.client
from dataclasses import asdict, dataclass, field
from pathlib import Path

from freecad_rules import RPC_URL, _socket_timeout, find_freecad, rpc_available

SETTINGS_FILE = "freecad_mcp_settings.json"
ADDON_DIR = "FreeCADMCP"

#: FreeCAD's user data folders, newest first, used when FreeCADCmd cannot say.
_DATA_DIR_CANDIDATES = (
    "%APPDATA%/FreeCAD/v1-1",
    "%APPDATA%/FreeCAD",
    "~/Library/Application Support/FreeCAD/v1-1",
    "~/Library/Application Support/FreeCAD",
    "~/.local/share/FreeCAD/v1-1",
    "~/.local/share/FreeCAD",
    "~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1",
)

#: Printed by the code that asks the open window for its documents.
_DOCS_MARKER = "DOQS_OPEN_DOCUMENTS="

_LIST_DOCUMENTS = f"""
import json, FreeCAD
print({_DOCS_MARKER!r} + json.dumps(
    [{{"name": d.Name, "file": d.FileName}} for d in FreeCAD.listDocuments().values()]))
"""

ASK_USER = (
    "FreeCAD is open, but its MCP server does not answer. In FreeCAD, select the "
    "MCP Addon workbench and click Start RPC Server in the FreeCAD MCP toolbar, "
    "or restart FreeCAD."
)


@dataclass
class Status:
    """What an agent can reach, and which way to edit is safe."""
    rpc: bool
    gui_running: bool
    data_dir: str | None
    addon_installed: bool
    auto_start: bool
    documents: list[dict] = field(default_factory=list)
    file_open: bool | None = None
    advice: str = ""
    reason: str = ""


def user_data_dir(freecad: str | None = None) -> Path | None:
    """FreeCAD's user data folder: asked from FreeCADCmd, else the first that exists."""
    binary = find_freecad(freecad, gui=False)
    if binary:
        try:
            proc = subprocess.run(
                [binary, "-c", "import FreeCAD; print('DOQS_DATA=' + FreeCAD.getUserAppDataDir())"],
                capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            proc = None
        if proc is not None:
            for line in (proc.stdout or "").splitlines():
                if line.startswith("DOQS_DATA="):
                    path = Path(line.removeprefix("DOQS_DATA=").strip())
                    if path.is_dir():
                        return path
    for candidate in _DATA_DIR_CANDIDATES:
        path = Path(os.path.expanduser(os.path.expandvars(candidate)))
        if "%" not in str(path) and (path / "Mod").is_dir():
            return path
    return None


def read_settings(data_dir: Path) -> dict:
    path = data_dir / SETTINGS_FILE
    if not path.is_file():
        return {}
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise SystemExit(f"error: {path} is not valid JSON ({err}). Fix it, then run again.")
    return settings if isinstance(settings, dict) else {}


def enable_auto_start(data_dir: Path) -> bool:
    """Switch on ``auto_start_rpc``. Keeps every other key. True if the file changed.

    Remote access, allowed addresses and the token stay as the person set
    them: the server runs any Python it gets and must stay on localhost.
    """
    if not (data_dir / "Mod" / ADDON_DIR).is_dir():
        raise SystemExit(
            f"error: the freecad-mcp add-on is not in {data_dir / 'Mod'}. "
            "Install it first, see doqs/docs/agent-cad.md.")
    settings = read_settings(data_dir)
    if settings.get("auto_start_rpc") is True:
        return False
    settings["auto_start_rpc"] = True
    (data_dir / SETTINGS_FILE).write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return True


def gui_running() -> bool:
    """True when a FreeCAD window process runs. FreeCADCmd does not count."""
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                                 text=True, timeout=30).stdout
        except (OSError, subprocess.TimeoutExpired):
            return False
        names = [line.split(",", 1)[0].strip('"').lower() for line in out.splitlines()]
        return "freecad.exe" in names
    try:
        out = subprocess.run(["ps", "-eo", "comm="], capture_output=True, text=True,
                             timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    names = [Path(line.strip()).name.lower() for line in out.splitlines()]
    # An AppImage shows up under its own name; FreeCADCmd is "freecadcmd".
    return any(name == "freecad" or (name.startswith("freecad") and name.endswith(".appimage"))
               for name in names)


def open_documents(url: str = RPC_URL, timeout: float = 10.0) -> list[dict]:
    """The documents the open window holds, with their file names.

    Uses the add-on's ``execute_code``, which runs on FreeCAD's main thread.
    """
    proxy = xmlrpc.client.ServerProxy(url, allow_none=True)
    try:
        with _socket_timeout(timeout):
            result = proxy.execute_code(_LIST_DOCUMENTS)
    except Exception:  # noqa: BLE001 - the window stopped answering
        return []
    output = str(result.get("message", result.get("output", ""))) if isinstance(result, dict) else str(result)
    for line in output.splitlines():
        if _DOCS_MARKER in line:
            return json.loads(line.split(_DOCS_MARKER, 1)[1])
    return []


def _same_file(a: str, b: Path) -> bool:
    if not a:
        return False
    try:
        return Path(a).resolve() == b.resolve()
    except OSError:
        return False


def decide(rpc: bool, running: bool, file_open: bool | None) -> tuple[str, str]:
    """The safe way to edit, and why. See the module text."""
    if rpc:
        if file_open:
            return "mcp", "the file is open in FreeCAD: edit it there, never headless"
        if file_open is False:
            return "mcp", ("FreeCAD answers and the file is not open: headless is safe too; "
                           "use MCP when the person wants to see it")
        return "mcp", "FreeCAD answers"
    if running:
        return "ask-user", ASK_USER
    return "headless", "no FreeCAD runs: FreeCADCmd cannot overwrite an open window"


def status(file: Path | None = None, url: str = RPC_URL, freecad: str | None = None) -> Status:
    rpc = rpc_available(url)
    running = rpc or gui_running()
    data_dir = user_data_dir(freecad)
    addon = bool(data_dir and (data_dir / "Mod" / ADDON_DIR).is_dir())
    auto = bool(data_dir and read_settings(data_dir).get("auto_start_rpc") is True)
    documents = open_documents(url) if rpc else []
    file_open = None
    if rpc and file is not None:
        file_open = any(_same_file(doc.get("file", ""), file) for doc in documents)
    advice, reason = decide(rpc, running, file_open)
    return Status(rpc, running, str(data_dir) if data_dir else None, addon, auto,
                  documents, file_open, advice, reason)


def start(file: Path | None = None, *, wait: float = 60.0, url: str = RPC_URL,
          freecad: str | None = None) -> tuple[int, str]:
    """Make sure a FreeCAD window answers. Returns an exit code and a message.

    Never starts a second window: two windows can save over each other.
    """
    if rpc_available(url):
        return 0, f"FreeCAD answers on {url}"
    data_dir = user_data_dir(freecad)
    if data_dir is None:
        return 1, "error: FreeCAD's user data folder was not found; is FreeCAD installed?"
    changed = enable_auto_start(data_dir)
    note = " Auto-start is now on, so this is needed only once." if changed else ""
    if gui_running():
        return 2, ASK_USER + note
    binary = find_freecad(freecad, gui=True)
    if binary is None:
        return 1, "error: no FreeCAD binary found; pass --freecad"
    cmd = [binary] + ([str(file)] if file else [])
    flags = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} \
        if os.name == "nt" else {"start_new_session": True}
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, **flags)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if rpc_available(url):
            return 0, f"started {binary}; FreeCAD answers on {url}"
        time.sleep(1.0)
    return 1, (f"error: started {binary}, but nothing answered on {url} within {wait:.0f} s. "
               "Check that the freecad-mcp add-on loads (Report view).")


def _print_status(s: Status) -> None:
    print(f"rpc server     {'answers' if s.rpc else 'does not answer'} ({RPC_URL})")
    print(f"freecad window {'runs' if s.gui_running else 'not running'}")
    print(f"add-on         {'installed' if s.addon_installed else 'not found'} ({s.data_dir or 'no data folder'})")
    print(f"auto-start     {'on' if s.auto_start else 'off'}")
    for doc in s.documents:
        print(f"open           {doc.get('name')}  {doc.get('file') or '(not saved yet)'}")
    print(f"advice         {s.advice}: {s.reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--freecad", help="FreeCAD binary to use")
    parser.add_argument("--url", default=RPC_URL, help=f"RPC server (default {RPC_URL})")
    subs = parser.add_subparsers(dest="command", required=True)
    st = subs.add_parser("status", help="What runs, and which way to edit is safe")
    st.add_argument("--file", type=Path, help="The .FCStd you want to edit")
    st.add_argument("--json", action="store_true", help="Print JSON")
    subs.add_parser("autostart", help="Start the RPC server each time FreeCAD starts")
    sa = subs.add_parser("start", help="Start FreeCAD with its RPC server, if none runs")
    sa.add_argument("file", nargs="?", type=Path, help="The .FCStd to open")
    sa.add_argument("--wait", type=float, default=60.0, help="Seconds to wait for the server")
    args = parser.parse_args(argv)

    if args.command == "status":
        s = status(args.file, url=args.url, freecad=args.freecad)
        if args.json:
            print(json.dumps(asdict(s), indent=2))
        else:
            _print_status(s)
        return 0
    if args.command == "autostart":
        data_dir = user_data_dir(args.freecad)
        if data_dir is None:
            print("error: FreeCAD's user data folder was not found; is FreeCAD installed?",
                  file=sys.stderr)
            return 1
        changed = enable_auto_start(data_dir)
        print(f"{'switched on' if changed else 'already on'}: auto-start in {data_dir / SETTINGS_FILE}")
        if changed:
            print("It takes effect the next time FreeCAD starts.")
        return 0
    code, message = start(args.file, wait=args.wait, url=args.url, freecad=args.freecad)
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
