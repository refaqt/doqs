"""Tests for how doqs runs a macro in the open FreeCAD window."""
from __future__ import annotations

import sys
import threading
import types
import unittest
from pathlib import Path
from xmlrpc.server import SimpleXMLRPCServer

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))

import freecad_rules  # noqa: E402


class _FakeAddOn:
    """The two calls of the freecad-mcp add-on that run code, and what they got."""

    def __init__(self, reply: dict):
        self.reply = reply
        self.calls: list[str] = []

    def ping(self):
        return True

    def execute_code(self, code):
        self.calls.append("execute_code")
        return self.reply

    def execute_code_async(self, code):
        # Runs on a worker thread in FreeCAD. A document job there crashed it.
        self.calls.append("execute_code_async")
        return {"success": True, "job_id": "job-1"}


class TestRpcRun(unittest.TestCase):
    def serve(self, reply: dict) -> tuple[_FakeAddOn, str]:
        addon = _FakeAddOn(reply)
        server = SimpleXMLRPCServer(("127.0.0.1", 0), logRequests=False, allow_none=True)
        server.register_instance(addon)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return addon, f"http://127.0.0.1:{server.server_address[1]}"

    def test_a_macro_runs_on_the_gui_thread_never_on_a_worker(self):
        addon, url = self.serve({"success": True,
                                 "message": f"Output: {freecad_rules.DONE_MARKER}\n"})
        result = freecad_rules.rpc_run("print('x')", url=url, timeout=10)
        self.assertTrue(result.ok, result)
        self.assertEqual(addon.calls, ["execute_code"])

    def test_an_error_in_freecad_is_reported(self):
        addon, url = self.serve({"success": False, "error": "NameError: name 'x' is not defined"})
        result = freecad_rules.rpc_run("x", url=url, timeout=10)
        self.assertFalse(result.ok)
        self.assertIn("NameError", result.error)
        self.assertEqual(addon.calls, ["execute_code"])

    def test_no_done_marker_is_not_success(self):
        _, url = self.serve({"success": True, "message": "Output: \n"})
        self.assertFalse(freecad_rules.rpc_run("pass", url=url, timeout=10).ok)


class TestRenderMacro(unittest.TestCase):
    def test_an_open_window_imports_doqs_again_from_the_given_scripts(self):
        # An open FreeCAD keeps modules from earlier macros, maybe from another
        # copy of doqs. On 2026-10-22 that ran the old wrap code after a fix.
        macro = freecad_rules.render_macro(_REPO / "scripts", "import cad_rules\n")
        head = macro.split("import FreeCAD\n", 1)[0]
        stale = types.ModuleType("cad_rules")
        stale.__file__ = "/another/copy/of/doqs/scripts/cad_rules.py"
        saved_path, saved = list(sys.path), sys.modules.get("cad_rules")
        sys.modules["cad_rules"] = stale
        try:
            exec(head, {})
            self.assertNotIn("cad_rules", sys.modules)
            self.assertIn("json", sys.modules)
        finally:
            sys.path[:] = saved_path
            if saved is not None:
                sys.modules["cad_rules"] = saved


if __name__ == "__main__":
    unittest.main()
