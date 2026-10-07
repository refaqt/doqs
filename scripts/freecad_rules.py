"""Run a piece of Python inside FreeCAD, from outside FreeCAD.

Three ways exist, and a tool picks the first one that works:

1. **The open FreeCAD window**, through the RPC server of the freecad-mcp
   add-on on ``127.0.0.1:9875``. The person sees the result and saves it.
2. **A FreeCAD window started for the job** (``freecad macro.py``). The
   macro does its work, saves, and closes the window. Needed when a STEP
   file is imported: only the GUI importer keeps the colours.
3. **FreeCADCmd**, headless. Fine for a build or an empty document. It loses
   colours on import, so a tool that needs them refuses this mode.

The macro is written to a file and handed over, like ``export_variant.py``
does. Success is never decided by the exit code: FreeCADCmd does not pass a
failure on reliably. A macro prints ``DOQS_MACRO_DONE`` as its last act, and
the caller also checks the file it expected. See docs/agent-cad.md.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import xmlrpc.client
from dataclasses import dataclass, field
from pathlib import Path

RPC_URL = "http://127.0.0.1:9875"
DONE_MARKER = "DOQS_MACRO_DONE"

#: Where FreeCAD lives when it is not on the PATH, by platform.
_GUI_CANDIDATES = (
    "freecad", "FreeCAD",
    "C:/Program Files/FreeCAD 1.1/bin/freecad.exe",
    "C:/Program Files/FreeCAD 1.0/bin/freecad.exe",
    "/Applications/FreeCAD.app/Contents/MacOS/FreeCAD",
    "/usr/bin/freecad",
)
_CMD_CANDIDATES = (
    "freecadcmd", "FreeCADCmd",
    "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe",
    "C:/Program Files/FreeCAD 1.0/bin/freecadcmd.exe",
    "/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd",
    "/usr/bin/freecadcmd",
)

MODES = ("auto", "rpc", "gui", "cmd")


@dataclass
class MacroResult:
    """What happened when a macro ran."""
    ok: bool
    mode: str
    output: str = ""
    exit_code: int | None = None
    error: str | None = None
    steps: list[str] = field(default_factory=list)


def find_freecad(explicit: str | None = None, gui: bool = False) -> str | None:
    """The FreeCAD binary to start: the explicit one, else the first found.

    An explicit binary that does not exist gives ``None``: a tool must not
    quietly run another FreeCAD than the one it was told to use.
    """
    candidates = [explicit] if explicit else list(_GUI_CANDIDATES if gui else _CMD_CANDIDATES)
    for candidate in candidates:
        if not candidate:
            continue
        found = shutil.which(candidate)
        if found:
            return found
        if Path(candidate).is_file():
            return str(Path(candidate))
    return None


def rpc_available(url: str = RPC_URL, timeout: float = 1.5) -> bool:
    """True when the open FreeCAD window answers on the RPC port."""
    try:
        proxy = xmlrpc.client.ServerProxy(url, allow_none=True)
        with _socket_timeout(timeout):
            return bool(proxy.ping())
    except Exception:  # noqa: BLE001 - any failure means "not reachable"
        return False


class _socket_timeout:
    """Set a default socket timeout for the duration of one call."""

    def __init__(self, seconds: float):
        self.seconds = seconds
        self.previous = None

    def __enter__(self):
        import socket

        self.previous = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.seconds)

    def __exit__(self, *exc):
        import socket

        socket.setdefaulttimeout(self.previous)
        return False


def render_macro(scripts: Path, body: str, close_gui: bool = False) -> str:
    """The macro text: a fixed header, the body, and the done marker.

    ``scripts`` is put on ``sys.path`` explicitly, so nothing in the body
    has to infer a location from ``__file__``. With ``close_gui`` the macro
    closes the FreeCAD window at the end, for a window started for the job.
    """
    head = (
        "import sys\n"
        f"sys.path.insert(0, {str(scripts)!r})\n"
        "import FreeCAD\n"
    )
    tail = f"\nprint({DONE_MARKER!r})\nsys.stdout.flush()\n"
    if close_gui:
        tail += (
            "try:\n"
            "    import FreeCADGui\n"
            "    for _name in list(FreeCAD.listDocuments()):\n"
            "        FreeCAD.closeDocument(_name)\n"
            "    FreeCADGui.getMainWindow().close()\n"
            "except Exception as _exc:  # no GUI, or already closed\n"
            "    print('could not close the window:', _exc)\n"
        )
    return head + body.rstrip("\n") + "\n" + tail


def rpc_run(code: str, url: str = RPC_URL, timeout: float = 600.0,
            poll: float = 0.5) -> MacroResult:
    """Run ``code`` in the open FreeCAD window and wait for it to finish.

    Uses the add-on's asynchronous call when it has one, so a long import
    does not hit the synchronous call's time limit.
    """
    proxy = xmlrpc.client.ServerProxy(url, allow_none=True)
    try:
        with _socket_timeout(max(timeout, 5.0)):
            started = proxy.execute_code_async(code)
    except xmlrpc.client.Fault:
        started = None
    except Exception as exc:  # noqa: BLE001
        return MacroResult(False, "rpc", error=f"RPC call failed: {exc}")
    if isinstance(started, dict) and started.get("job_id"):
        job = started["job_id"]
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                status = proxy.get_async_status(job)
            except Exception as exc:  # noqa: BLE001
                return MacroResult(False, "rpc", error=f"RPC status failed: {exc}")
            state = str(status.get("status", "")).lower() if isinstance(status, dict) else ""
            if state in ("done", "completed", "finished", "success", "error", "failed"):
                output = str(status.get("output", status.get("message", "")))
                ok = state not in ("error", "failed") and status.get("success", True) is not False
                return MacroResult(ok and DONE_MARKER in output, "rpc", output=output,
                                   error=None if ok else output)
            time.sleep(poll)
        return MacroResult(False, "rpc", error=f"timed out after {timeout:.0f} s")
    try:
        with _socket_timeout(max(timeout, 5.0)):
            result = proxy.execute_code(code)
    except Exception as exc:  # noqa: BLE001
        return MacroResult(False, "rpc", error=f"RPC call failed: {exc}")
    output = str(result.get("message", result.get("output", ""))) if isinstance(result, dict) else str(result)
    ok = bool(result.get("success", True)) if isinstance(result, dict) else True
    return MacroResult(ok and DONE_MARKER in output, "rpc", output=output,
                       error=None if ok else output)


def run_macro(macro: str, *, mode: str = "auto", freecad: str | None = None,
              timeout: float = 600.0, url: str = RPC_URL, needs_gui: bool = False,
              display: str | None = None) -> MacroResult:
    """Run a rendered macro. Returns what happened; never raises for FreeCAD.

    ``mode`` is ``auto`` (RPC, then a GUI window, then FreeCADCmd), or one
    of the three. ``needs_gui`` refuses FreeCADCmd, for a job that imports a
    STEP file. ``display`` names a virtual display command such as
    ``xvfb-run -a`` for a server without a screen.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    steps: list[str] = []
    if mode in ("auto", "rpc"):
        if rpc_available(url):
            steps.append("rpc: the open FreeCAD window")
            result = rpc_run(macro, url=url, timeout=timeout)
            result.steps = steps
            if result.ok or mode == "rpc":
                return result
            steps.append(f"rpc failed: {result.error}")
        elif mode == "rpc":
            return MacroResult(False, "rpc", error=f"no FreeCAD answers on {url}", steps=steps)
        else:
            steps.append(f"rpc: nothing answers on {url}")
    if mode in ("auto", "gui"):
        binary = find_freecad(freecad, gui=True)
        if binary:
            steps.append(f"gui: {binary}")
            result = _spawn(macro, binary, timeout, "gui", display)
            result.steps = steps + result.steps
            if result.ok or mode == "gui":
                return result
            steps.append(f"gui failed: {result.error}")
        elif mode == "gui":
            return MacroResult(False, "gui", error="no FreeCAD GUI binary found; pass --freecad", steps=steps)
        else:
            steps.append("gui: no FreeCAD binary found")
    if needs_gui:
        return MacroResult(False, "cmd", steps=steps,
                           error="this job needs the FreeCAD window (colours are lost headless) "
                                 "and no window could be reached or started")
    binary = find_freecad(freecad, gui=False)
    if binary is None:
        return MacroResult(False, "cmd", error="no FreeCADCmd binary found; pass --freecad", steps=steps)
    steps.append(f"cmd: {binary}")
    result = _spawn(macro, binary, timeout, "cmd", None)
    result.steps = steps + result.steps
    return result


def _spawn(macro: str, binary: str, timeout: float, mode: str, display: str | None) -> MacroResult:
    staging = Path(tempfile.mkdtemp(prefix="doqs-macro-"))
    try:
        path = staging / "macro.py"
        path.write_text(macro, encoding="utf-8")
        cmd = ([*display.split()] if display else []) + [binary, str(path)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                  env={**os.environ, "DOQS_MACRO": "1"})
        except subprocess.TimeoutExpired:
            return MacroResult(False, mode, error=f"{binary} did not finish in {timeout:.0f} s")
        except OSError as exc:
            return MacroResult(False, mode, error=f"could not start {binary}: {exc}")
        output = (proc.stdout or "") + (proc.stderr or "")
        ok = DONE_MARKER in output
        return MacroResult(ok, mode, output=output, exit_code=proc.returncode,
                           error=None if ok else f"{binary} exited {proc.returncode} without finishing the macro")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
