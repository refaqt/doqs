"""Tests for how an agent finds and starts the FreeCAD MCP connection."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from xmlrpc.server import SimpleXMLRPCServer

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))

import freecad_session  # noqa: E402


class _FakeAddOn:
    def __init__(self, documents: list[dict]):
        self.documents = documents
        self.calls: list[str] = []

    def ping(self):
        return True

    def execute_code(self, code):
        self.calls.append("execute_code")
        line = freecad_session._DOCS_MARKER + json.dumps(self.documents)
        return {"success": True, "message": f"Output: {line}\n"}


def _serve(test: unittest.TestCase, documents: list[dict]) -> tuple[_FakeAddOn, str]:
    addon = _FakeAddOn(documents)
    server = SimpleXMLRPCServer(("127.0.0.1", 0), logRequests=False, allow_none=True)
    server.register_instance(addon)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    test.addCleanup(server.server_close)
    test.addCleanup(server.shutdown)
    return addon, f"http://127.0.0.1:{server.server_address[1]}"


class _DataDir(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = Path(tmp.name)
        (self.data / "Mod" / freecad_session.ADDON_DIR).mkdir(parents=True)
        self.settings = self.data / freecad_session.SETTINGS_FILE


class TestAutoStart(_DataDir):
    def test_it_creates_the_settings_file(self):
        self.assertTrue(freecad_session.enable_auto_start(self.data))
        self.assertEqual(json.loads(self.settings.read_text()), {"auto_start_rpc": True})

    def test_it_keeps_every_other_key(self):
        # Remote access and the token are the person's choice, and a safety one.
        mine = {"remote_enabled": False, "allowed_ips": "127.0.0.1", "auth_token": "x",
                "auto_start_rpc": False}
        self.settings.write_text(json.dumps(mine))
        self.assertTrue(freecad_session.enable_auto_start(self.data))
        self.assertEqual(json.loads(self.settings.read_text()), {**mine, "auto_start_rpc": True})

    def test_a_second_run_changes_nothing(self):
        freecad_session.enable_auto_start(self.data)
        self.assertFalse(freecad_session.enable_auto_start(self.data))

    def test_it_refuses_without_the_add_on(self):
        (self.data / "Mod" / freecad_session.ADDON_DIR).rmdir()
        with self.assertRaises(SystemExit):
            freecad_session.enable_auto_start(self.data)
        self.assertFalse(self.settings.exists())

    def test_broken_json_is_not_overwritten(self):
        self.settings.write_text("{not json")
        with self.assertRaises(SystemExit):
            freecad_session.enable_auto_start(self.data)
        self.assertEqual(self.settings.read_text(), "{not json")


class TestDecide(unittest.TestCase):
    def test_an_open_file_is_edited_through_mcp(self):
        self.assertEqual(freecad_session.decide(True, True, True)[0], "mcp")

    def test_no_freecad_means_headless(self):
        self.assertEqual(freecad_session.decide(False, False, None)[0], "headless")

    def test_a_silent_window_means_ask_the_person(self):
        # Nobody can see which files that window holds, so headless is not safe.
        self.assertEqual(freecad_session.decide(False, True, None)[0], "ask-user")


class TestStatus(_DataDir):
    def test_it_sees_which_file_is_open(self):
        part = self.data / "rail.FCStd"
        addon, url = _serve(self, [{"name": "rail", "file": str(part)}])
        with mock.patch.object(freecad_session, "user_data_dir", return_value=self.data):
            s = freecad_session.status(part, url=url)
            other = freecad_session.status(self.data / "other.FCStd", url=url)
        self.assertTrue(s.rpc)
        self.assertTrue(s.file_open)
        self.assertEqual(s.advice, "mcp")
        self.assertFalse(other.file_open)
        self.assertEqual(addon.calls, ["execute_code", "execute_code"])

    def test_without_the_server_it_does_not_guess_open_files(self):
        with mock.patch.object(freecad_session, "user_data_dir", return_value=self.data), \
                mock.patch.object(freecad_session, "gui_running", return_value=True):
            s = freecad_session.status(self.data / "rail.FCStd", url="http://127.0.0.1:9")
        self.assertIsNone(s.file_open)
        self.assertEqual(s.advice, "ask-user")


class TestStart(_DataDir):
    def patches(self, running: bool):
        return (mock.patch.object(freecad_session, "user_data_dir", return_value=self.data),
                mock.patch.object(freecad_session, "gui_running", return_value=running),
                mock.patch.object(freecad_session, "find_freecad", return_value="/bin/freecad"),
                mock.patch.object(freecad_session.subprocess, "Popen"))

    def test_an_answering_window_needs_nothing(self):
        _, url = _serve(self, [])
        code, _ = freecad_session.start(url=url)
        self.assertEqual(code, 0)
        self.assertFalse(self.settings.exists())

    def test_it_never_starts_a_second_window(self):
        a, b, c, popen = self.patches(running=True)
        with a, b, c, popen as launched:
            code, message = freecad_session.start(url="http://127.0.0.1:9", wait=0)
        self.assertEqual(code, 2)
        self.assertIn("Start RPC Server", message)
        launched.assert_not_called()
        # The next restart of that window answers by itself.
        self.assertTrue(json.loads(self.settings.read_text())["auto_start_rpc"])

    def test_it_starts_freecad_with_the_file_and_waits(self):
        a, b, c, popen = self.patches(running=False)
        answers = iter([False, True])
        with a, b, c, popen as launched, \
                mock.patch.object(freecad_session, "rpc_available", lambda url: next(answers)), \
                mock.patch.object(freecad_session.time, "sleep"):
            code, _ = freecad_session.start(Path("cad/rail.FCStd"), wait=5)
        self.assertEqual(code, 0)
        self.assertEqual(launched.call_args.args[0], ["/bin/freecad", "cad/rail.FCStd"])

    def test_it_says_so_when_the_window_never_answers(self):
        a, b, c, popen = self.patches(running=False)
        with a, b, c, popen:
            code, message = freecad_session.start(url="http://127.0.0.1:9", wait=0)
        self.assertEqual(code, 1)
        self.assertIn("nothing answered", message)


if __name__ == "__main__":
    unittest.main()
