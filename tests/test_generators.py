"""First tests for three scripts that had none: validate_build, aggregate_bom, resolve_graph.

All three are run by hand or by CI in machine repositories, and until now a
change to any of them could only be caught by a person noticing.
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import aggregate_bom  # noqa: E402
import resolve_graph  # noqa: E402
import validate_build  # noqa: E402

_MINIMAL = _REPO / "tests" / "fixtures" / "minimal-machine"
_VARIANT_MACHINE = _REPO / "tests" / "fixtures" / "variant-machine"

_MODULE_OKH = """\
okhv = "OKH-LOSHv1.0"
name = "{name}"
repo = "https://example.com/{name}"
version = "v1.0.0"
license = {{ hardware = "CERN-OHL-S-2.0" }}
licensor = "Tests"
function = "A test module."
"""


class TempRoot(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="doqs-generators-"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = self._tmp / "machine"
        self.root.mkdir()

    def module(self, slug: str, *, provides=(), consumes=()) -> Path:
        """A module with an okh.toml, and optionally interface declarations."""
        path = self.root / "modules" / slug
        path.mkdir(parents=True)
        text = _MODULE_OKH.format(name=slug)
        for iface in provides:
            text += f'\n[[provides-interface]]\nname = "{iface}"\nversion = "1.0"\n'
        for iface in consumes:
            text += f'\n[[consumes-interface]]\nname = "{iface}"\nversion = "1.0"\n'
        (path / "okh.toml").write_text(text, encoding="utf-8")
        return path

    def lockfile(self, name: str, modules: list[str]) -> Path:
        build_dir = self.root / "builds" / name
        build_dir.mkdir(parents=True)
        text = 'schema = "doqs-build-v1"\nmachine = "test"\n'
        for index, slug in enumerate(modules):
            # A record must name where to fetch from and the exact commit, so
            # these tests carry them too. See ADR-007.
            text += (
                f'\n[[module]]\npath = "modules/{slug}"\n'
                f'repo = "https://example.com/{slug}"\n'
                f'version = "v1.0.0"\ncommit = "{str(index) * 40}"\n'
            )
        path = build_dir / "build.toml"
        path.write_text(text, encoding="utf-8")
        return path


class TestValidateBuild(TempRoot):
    def test_a_satisfied_interface_passes(self):
        self.module("frame", provides=["FrameMount_v1"])
        self.module("x-axis", consumes=["FrameMount_v1"])
        build = self.lockfile("serial-1", ["frame", "x-axis"])
        self.assertEqual(validate_build.validate(build, self.root), [])

    def test_an_unsatisfied_interface_fails_and_names_it(self):
        self.module("x-axis", consumes=["FrameMount_v1"])
        build = self.lockfile("serial-1", ["x-axis"])
        errors = validate_build.validate(build, self.root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("FrameMount_v1", errors[0])

    def test_no_lockfiles_is_not_a_failure(self):
        (self.root / "builds").mkdir()
        self.assertEqual(validate_build.main(["--root", str(self.root)]), 0)

    def test_the_real_fixture_passes(self):
        self.assertEqual(validate_build.main(["--root", str(_VARIANT_MACHINE)]), 0)


class TestAggregateBom(TempRoot):
    def _bom(self, slug: str, rows: list[tuple[str, str]]) -> None:
        path = self.root / "modules" / slug / "bom"
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "bom.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name"])
            writer.writerows(rows)

    def test_every_module_row_lands_in_one_file_tagged_with_its_module(self):
        self.module("frame")
        self.module("x-axis")
        self._bom("frame", [("FRM-001", "extrusion")])
        self._bom("x-axis", [("XAX-001", "rail"), ("XAX-002", "carriage")])

        out = self.root / "bom" / "bom.csv"
        aggregate_bom.main(["--root", str(self.root), "--out", str(out)])

        rows = list(csv.DictReader(out.open(encoding="utf-8")))
        self.assertEqual(len(rows), 3)
        self.assertEqual({r["module"] for r in rows}, {"modules/frame", "modules/x-axis"})
        self.assertIn("FRM-001", {r["id"] for r in rows})

    def test_no_module_boms_still_writes_a_file_with_only_headers(self):
        # A machine with no BOMs yet gets a valid, empty purchasing list rather
        # than no file at all, so anything reading bom.csv keeps working.
        self.module("frame")
        out = self.root / "bom" / "bom.csv"
        aggregate_bom.main(["--root", str(self.root), "--out", str(out)])

        self.assertTrue(out.exists())
        self.assertEqual(list(csv.DictReader(out.open(encoding="utf-8"))), [])
        self.assertIn("module", out.read_text(encoding="utf-8").splitlines()[0])


class TestResolveGraph(TempRoot):
    def test_the_graph_names_every_module(self):
        self.module("frame")
        self.module("x-axis")
        (self.root / "okh.toml").write_text(_MODULE_OKH.format(name="machine"), encoding="utf-8")

        graph = resolve_graph.build(self.root)
        self.assertEqual(set(graph), {".", "modules/frame", "modules/x-axis"})
        self.assertEqual(graph["modules/frame"]["current_version"], "v1.0.0")

    def test_check_reports_a_missing_graph(self):
        (self.root / "okh.toml").write_text(_MODULE_OKH.format(name="machine"), encoding="utf-8")
        self.assertEqual(resolve_graph.main(["--root", str(self.root), "--check"]), 1)

    def test_check_reports_a_stale_graph(self):
        (self.root / "okh.toml").write_text(_MODULE_OKH.format(name="machine"), encoding="utf-8")
        self.assertEqual(resolve_graph.main(["--root", str(self.root)]), 0)
        self.assertEqual(resolve_graph.main(["--root", str(self.root), "--check"]), 0)

        self.module("added-later")
        self.assertEqual(resolve_graph.main(["--root", str(self.root), "--check"]), 1)

    def test_writing_twice_gives_the_same_bytes(self):
        # CI in a machine repo commits this file and fails on any diff, so a
        # rerun that reorders keys would turn that repo red for no reason.
        (self.root / "okh.toml").write_text(_MODULE_OKH.format(name="machine"), encoding="utf-8")
        self.module("frame")
        out = self.root / "graph" / "usage-graph.json"

        resolve_graph.main(["--root", str(self.root)])
        first = out.read_text(encoding="utf-8")
        resolve_graph.main(["--root", str(self.root)])
        self.assertEqual(out.read_text(encoding="utf-8"), first)
        json.loads(first)

    def test_the_tooling_submodules_are_skipped(self):
        (self.root / "okh.toml").write_text(_MODULE_OKH.format(name="machine"), encoding="utf-8")
        kit = self.root / "doqs"
        kit.mkdir()
        (kit / "okh.toml").write_text(_MODULE_OKH.format(name="doqs-sample"), encoding="utf-8")

        self.assertNotIn("doqs", resolve_graph.build(self.root))


class TestMinimalFixtureStillPasses(unittest.TestCase):
    def test_validate_build_on_the_minimal_machine(self):
        self.assertEqual(validate_build.main(["--root", str(_MINIMAL)]), 0)


if __name__ == "__main__":
    unittest.main()
