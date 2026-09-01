"""Unit tests for the SysON session adapter (no Docker / no live server)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from syson import (  # noqa: E402
    COMPOSE_FILE,
    PANEL_HTML,
    UI_COMMANDS,
    collect_sysml,
    docker_missing_message,
    document_name,
    extra_export_path,
    import_order,
    looks_like_machine_repo,
    looks_like_textual_sysml,
    panel_response,
    parse_manifest_documents,
    parse_projects,
    path_for_document,
    project_name,
    run_ui_command,
)


class TestProjectName(unittest.TestCase):
    def test_okh_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "okh.toml").write_text(
                'name = "Qarve CNC Milling Machine"\n', encoding="utf-8"
            )
            self.assertEqual(project_name(root), "Qarve CNC Milling Machine")

    def test_fallback_directory_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ab"
            root.mkdir()
            self.assertEqual(project_name(root), "ab-machine")


class TestCollectAndOrder(unittest.TestCase):
    def _tree(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="doqs-syson-"))
        self.addCleanup(
            lambda: __import__("shutil").rmtree(tmp, ignore_errors=True)
        )
        (tmp / "architecture").mkdir()
        (tmp / "architecture" / "machine.sysml").write_text(
            "import '../modules/x-axis/architecture/x-axis.sysml'::XAxis::*;\n"
            "package Machine {}\n",
            encoding="utf-8",
        )
        axis = tmp / "modules" / "x-axis" / "architecture"
        axis.mkdir(parents=True)
        (axis / "x-axis.sysml").write_text("package XAxis {}\n", encoding="utf-8")
        (tmp / "doqs" / "architecture").mkdir(parents=True)
        (tmp / "doqs" / "architecture" / "ignored.sysml").write_text(
            "package Ignored {}\n", encoding="utf-8"
        )
        (tmp / "notes.sysml").write_text("package Notes {}\n", encoding="utf-8")
        return tmp

    def test_collects_architecture_only_skips_doqs(self):
        root = self._tree()
        files = collect_sysml(root)
        rels = {str(p.relative_to(root)).replace("\\", "/") for p in files}
        self.assertEqual(
            rels,
            {
                "architecture/machine.sysml",
                "modules/x-axis/architecture/x-axis.sysml",
            },
        )

    def test_import_order_dependencies_first(self):
        root = self._tree()
        files = collect_sysml(root)
        ordered = import_order(files)
        names = [p.name for p in ordered]
        self.assertEqual(names[0], "x-axis.sysml")
        self.assertEqual(names[-1], "machine.sysml")


class TestDocumentNames(unittest.TestCase):
    def test_unique_basename(self):
        rels = [Path("architecture/machine.sysml")]
        self.assertEqual(document_name(rels[0], rels), "machine.sysml")

    def test_collision_uses_joined_path(self):
        rels = [
            Path("modules/x-axis/architecture/axis.sysml"),
            Path("modules/y-axis/architecture/axis.sysml"),
        ]
        self.assertEqual(
            document_name(rels[0], rels),
            "modules__x-axis__architecture__axis.sysml",
        )

    def test_round_trip_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "architecture" / "machine.sysml"
            a.parent.mkdir()
            a.write_text("package A {}\n", encoding="utf-8")
            files = [a]
            name = document_name(a.relative_to(root), [a.relative_to(root)])
            self.assertEqual(path_for_document(name, root, files), a)

    def test_extra_export_path(self):
        root = Path("/repo")
        self.assertEqual(
            extra_export_path(root, "extra.sysml"),
            root / "architecture" / "extra.sysml",
        )
        self.assertIsNone(extra_export_path(root, "SysMLv2"))


class TestParseAndDetect(unittest.TestCase):
    def test_parse_projects_list(self):
        payload = [{"@id": "abc", "name": "Qarve CNC Milling Machine"}]
        self.assertEqual(
            parse_projects(payload),
            [{"id": "abc", "name": "Qarve CNC Milling Machine"}],
        )

    def test_parse_manifest(self):
        docs = parse_manifest_documents(
            {"documentIdsToName": {"uuid-1": "machine.sysml", "uuid-2": "x-axis.sysml"}}
        )
        self.assertEqual(
            docs,
            [("uuid-1", "machine.sysml"), ("uuid-2", "x-axis.sysml")],
        )

    def test_looks_like_textual_sysml(self):
        text = b"// comment\npackage QarveMachine {}\n"
        self.assertTrue(looks_like_textual_sysml(text))
        json_blob = b'{"json":{"version":"1.0"},"content":[{"eClass":"sysml:Package"}]}'
        self.assertFalse(looks_like_textual_sysml(json_blob))

    def test_docker_missing_message(self):
        msg = docker_missing_message()
        self.assertIn("Docker Desktop", msg)
        self.assertIn("https://docs.docker.com", msg)

    def test_compose_file_exists(self):
        self.assertTrue(COMPOSE_FILE.is_file(), COMPOSE_FILE)

    def test_looks_like_machine_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(looks_like_machine_repo(root))
            (root / "architecture").mkdir()
            self.assertTrue(looks_like_machine_repo(root))

    def test_help_parses(self):
        from syson import build_parser

        parser = build_parser()
        args = parser.parse_args(["status", "--no-browser"])
        self.assertEqual(args.command, "status")
        self.assertTrue(args.no_browser)

    def test_ui_is_a_command(self):
        from syson import build_parser

        parser = build_parser()
        args = parser.parse_args(["ui", "--no-browser"])
        self.assertEqual(args.command, "ui")


class TestControlPanel(unittest.TestCase):
    def test_html_file_exists(self):
        self.assertTrue(PANEL_HTML.is_file(), PANEL_HTML)
        text = PANEL_HTML.read_text(encoding="utf-8")
        for command in UI_COMMANDS:
            self.assertIn(f'data-command="{command}"', text)
        self.assertIn('data-confirm="This deletes diagrams in SysON"', text)

    def test_unknown_post_is_rejected(self):
        root = Path("/repo")
        status, ctype, body = panel_response(
            "POST", "/run/wipe", root=root, url="http://localhost:8080", name="Qarve"
        )
        self.assertEqual(status, 404)
        self.assertIn("json", ctype)
        payload = json.loads(body.decode("utf-8"))
        self.assertFalse(payload["ok"])
        self.assertIn("Unknown command", payload["output"])

    def test_run_ui_command_rejects_unknown(self):
        ok, output = run_ui_command("wipe", Path("/repo"), "http://localhost:8080", "Qarve")
        self.assertFalse(ok)
        self.assertIn("Unknown command", output)

    def test_get_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "qarve"
            root.mkdir()
            status, ctype, body = panel_response(
                "GET",
                "/api/meta",
                root=root,
                url="http://localhost:8080",
                name="Qarve CNC Milling Machine",
            )
        self.assertEqual(status, 200)
        self.assertIn("json", ctype)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["folder"], "qarve")
        self.assertEqual(payload["project"], "Qarve CNC Milling Machine")

    def test_get_panel_html(self):
        status, ctype, body = panel_response(
            "GET", "/", root=Path("/repo"), url="http://localhost:8080", name="Qarve"
        )
        self.assertEqual(status, 200)
        self.assertIn("html", ctype)
        self.assertIn(b"SysON control panel", body)

    def test_unknown_get_is_404(self):
        status, _ctype, _body = panel_response(
            "GET", "/secret", root=Path("/repo"), url="http://localhost:8080", name="Qarve"
        )
        self.assertEqual(status, 404)

    def test_get_run_path_is_rejected(self):
        status, _ctype, _body = panel_response(
            "GET", "/run/open", root=Path("/repo"), url="http://localhost:8080", name="Qarve"
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
