"""Unit tests for instance modules — the consumer's choice of family variant."""
from __future__ import annotations

import csv
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import resolve_instance  # noqa: E402
from resolve_instance import InstanceError, render_all, targets  # noqa: E402

MACHINE = _REPO / "tests" / "fixtures" / "variant-machine"


class MachineCopy(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "machine"
        shutil.copytree(MACHINE, self.root)
        self.x = self.root / "modules" / "x-stage"
        self.y = self.root / "modules" / "y-stage"
        self.core = self.root / "modules/linear-stage/modules/linear-stage"
        self.addCleanup(self._tmp.cleanup)

    def resolved_bom(self, instance: Path) -> list[dict]:
        with open(instance / "bom" / "resolved.csv", newline="") as f:
            return list(csv.DictReader(f))


class TestDiscovery(MachineCopy):
    def test_instances_are_found_by_their_instance_table(self) -> None:
        found = {p.name for p in resolve_instance.instance_modules(self.root)}
        self.assertEqual(found, {"x-stage", "y-stage"})

    def test_family_path_is_repo_root_relative(self) -> None:
        target = targets(self.root, self.x)
        self.assertEqual(target["family"], self.root / "modules" / "linear-stage")


class TestTwoInstancesOfOneFamily(MachineCopy):
    """The case a single shared params.csv inside the submodule cannot do."""

    def test_each_instance_resolves_its_own_length(self) -> None:
        x_rail = next(r for r in self.resolved_bom(self.x) if r["id"] == "PRF-001")
        y_rail = next(r for r in self.resolved_bom(self.y) if r["id"] == "PRF-001")
        self.assertEqual(x_rail["brand_pn"], "HGR20R500")
        self.assertEqual(y_rail["brand_pn"], "HGR20R300")

    def test_each_instance_resolves_its_own_drive(self) -> None:
        x_motor = next(r for r in self.resolved_bom(self.x) if r["id"] == "MOT-001")
        y_motor = next(r for r in self.resolved_bom(self.y) if r["id"] == "MOT-001")
        self.assertEqual(x_motor["name"], "Servo Motor")
        self.assertEqual(y_motor["name"], "Stepper Motor")

    def test_the_submodule_is_never_written_to(self) -> None:
        before = {p: p.read_bytes() for p in sorted(
            (self.root / "modules" / "linear-stage").rglob("*")) if p.is_file()}
        resolve_instance.process(self.root, self.x, check=False)
        after = {p: p.read_bytes() for p in sorted(
            (self.root / "modules" / "linear-stage").rglob("*")) if p.is_file()}
        self.assertEqual(before, after)


class TestGeneratedFiles(MachineCopy):
    def test_committed_outputs_are_current_in_the_fixture(self) -> None:
        self.assertTrue(resolve_instance.process(self.root, self.x, check=True))

    def test_stale_output_fails_check(self) -> None:
        bom = self.x / "bom" / "resolved.csv"
        bom.write_text(bom.read_text().replace("HGR20R500", "HGR25R500"))
        self.assertFalse(resolve_instance.process(self.root, self.x, check=True))

    def test_missing_output_fails_check(self) -> None:
        (self.x / "cad" / "resolved" / "params.csv").unlink()
        self.assertFalse(resolve_instance.process(self.root, self.x, check=True))

    def test_own_bom_has_the_plain_doqs_header(self) -> None:
        first = (self.x / "bom" / "bom.csv").read_text().splitlines()[0]
        self.assertTrue(first.startswith("id,name,spec,"))

    def test_provenance_records_the_selection(self) -> None:
        text = (self.x / "cad" / "resolved" / "provenance.toml").read_text()
        self.assertIn('model = "500mm"', text)
        self.assertIn('sku = "ALS-SL-500"', text)
        self.assertIn('composition = "modules/linear-stage-servo-linear"', text)

    def test_vendor_cad_lists_one_file_per_purchased_part(self) -> None:
        with open(self.x / "cad" / "resolved" / "vendor-cad.csv", newline="") as f:
            entries = {r["id"]: r["cad"] for r in csv.DictReader(f)}
        self.assertEqual(entries["PRF-001"], "cad/vendor/hiwin/HGR20R500.step")
        self.assertEqual(entries["MOT-001"], "cad/vendor/beckhoff/AM8113.step")


class TestUpstreamChanges(MachineCopy):
    """A family update must never break a consumer silently."""

    def test_model_removed_upstream_is_reported(self) -> None:
        (self.core / "cad" / "params" / "500mm.csv").unlink()
        okh = self.core / "okh.toml"
        okh.write_text(okh.read_text().replace('name        = "500mm"', 'name        = "gone"'))
        with self.assertRaisesRegex(InstanceError, "no longer declares model '500mm'"):
            render_all(self.root, self.x)

    def test_composition_removed_upstream_is_reported(self) -> None:
        shutil.rmtree(self.root / "modules/linear-stage/modules/linear-stage-servo-linear")
        with self.assertRaisesRegex(InstanceError, "does not contain composition"):
            render_all(self.root, self.x)

    def test_unchecked_out_submodule_is_reported(self) -> None:
        shutil.rmtree(self.root / "modules" / "linear-stage")
        (self.root / "modules" / "linear-stage").mkdir()
        with self.assertRaisesRegex(InstanceError, "git submodule update"):
            render_all(self.root, self.x)

    def test_supplier_change_upstream_shows_in_the_resolved_bom(self) -> None:
        """The review surface: a rail swap must appear as a diff, not a surprise."""
        table = self.core / "bom" / "tables" / "hgr20-rail.csv"
        table.write_text(table.read_text().replace("HGR20R500", "HGR25R500"))
        rendered = render_all(self.root, self.x)
        self.assertIn("HGR25R500", rendered[Path("bom") / "resolved.csv"])


if __name__ == "__main__":
    unittest.main()
