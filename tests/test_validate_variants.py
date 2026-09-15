"""Unit tests for the product-family validator."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from validate_variants import check_all  # noqa: E402

FAMILY = _REPO / "tests" / "fixtures" / "variant-family"
MACHINE = _REPO / "tests" / "fixtures" / "variant-machine"


class FixtureCopy(unittest.TestCase):
    fixture = FAMILY

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        shutil.copytree(self.fixture, self.root)
        self.addCleanup(self._tmp.cleanup)

    def messages(self) -> tuple[list[str], list[str]]:
        errors, warnings = check_all(self.root)
        return ([f"{f.path}: {f.message}" for f in errors],
                [f"{f.path}: {f.message}" for f in warnings])

    def assertFails(self, needle: str) -> None:
        errors, _ = self.messages()
        self.assertTrue(any(needle in e for e in errors),
                        f"expected an error containing {needle!r}, got {errors}")

    def append_sku(self, block: str) -> None:
        catalog = self.root / "catalog.toml"
        catalog.write_text(catalog.read_text() + block)


class TestCleanFixtures(FixtureCopy):
    def test_family_fixture_passes(self) -> None:
        errors, warnings = self.messages()
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("fetch-only", warnings[0])


class TestCleanMachine(FixtureCopy):
    fixture = MACHINE

    def test_machine_fixture_passes(self) -> None:
        errors, _ = self.messages()
        self.assertEqual(errors, [])


class TestCatalogue(FixtureCopy):
    def test_unknown_model_is_refused(self) -> None:
        self.append_sku('\n[[sku]]\nname = "ALS-SL-640"\n'
                        'composition = "modules/linear-stage-servo-linear"\n'
                        'model = "640mm"\n')
        self.assertFails("model '640mm' is not declared")

    def test_unknown_composition_is_refused(self) -> None:
        self.append_sku('\n[[sku]]\nname = "ALS-X-1"\n'
                        'composition = "modules/nope"\nmodel = "default"\n')
        self.assertFails("composition 'modules/nope' not found")

    def test_lowercase_sku_is_refused(self) -> None:
        self.append_sku('\n[[sku]]\nname = "als-x-1"\n'
                        'composition = "modules/linear-stage-stepper"\nmodel = "default"\n')
        self.assertFails("must match")

    def test_duplicate_sku_is_refused(self) -> None:
        self.append_sku('\n[[sku]]\nname = "ALS-S-300"\n'
                        'composition = "modules/linear-stage-stepper"\nmodel = "default"\n')
        self.assertFails("duplicate sku 'ALS-S-300'")

    def test_bad_status_is_refused(self) -> None:
        self.append_sku('\n[[sku]]\nname = "ALS-X-2"\n'
                        'composition = "modules/linear-stage-stepper"\n'
                        'model = "default"\nstatus = "maybe"\n')
        self.assertFails("status must be one of")


class TestModels(FixtureCopy):
    def test_undeclared_params_file_is_refused(self) -> None:
        (self.root / "modules/linear-stage/cad/params/1200mm.csv").write_text(
            "alias,value,unit,description\nrail_length,1200,mm,x\n")
        self.assertFails("is not declared as a [[model]]")

    def test_declared_model_without_a_file_is_refused(self) -> None:
        (self.root / "modules/linear-stage/cad/params/800mm.csv").unlink()
        self.assertFails("has no cad/params/800mm.csv")

    def test_length_with_no_stocked_row_is_refused(self) -> None:
        """The guardrail: you cannot ship a length nobody sells."""
        (self.root / "modules/linear-stage/cad/params/1200mm.csv").write_text(
            "alias,value,unit,description\nrail_length,1200,mm,x\n")
        self.assertFails("no row for key 1200")


class TestComposition(FixtureCopy):
    def test_missing_core_is_refused(self) -> None:
        okh = self.root / "modules/linear-stage-stepper/okh.toml"
        okh.write_text(okh.read_text().replace(
            'core    = "modules/linear-stage"', 'core    = "modules/nope"'))
        self.assertFails("core 'modules/nope' not found")

    def test_missing_option_is_refused(self) -> None:
        okh = self.root / "modules/linear-stage-stepper/okh.toml"
        okh.write_text(okh.read_text().replace(
            "modules/linear-stage/modules/feedback-none",
            "modules/linear-stage/modules/feedback-telepathy"))
        self.assertFails("option 'modules/linear-stage/modules/feedback-telepathy' not found")


class TestVendorGeometry(FixtureCopy):
    def test_missing_redistributable_file_is_an_error(self) -> None:
        (self.root / "modules/linear-stage/modules/drive-servo"
                     "/cad/vendor/beckhoff/AM8113.step").unlink()
        self.assertFails("cad not found: cad/vendor/beckhoff/AM8113.step")

    def test_missing_fetch_only_file_is_only_a_warning(self) -> None:
        """CI must stay green on a fresh clone of a repo with fetch-only CAD."""
        errors, warnings = self.messages()
        self.assertEqual(errors, [])
        self.assertTrue(any("fetch-only" in w for w in warnings))

    def test_vendor_binding_to_an_unknown_bom_id_is_refused(self) -> None:
        sources = self.root / "modules/linear-stage/bom/sources.toml"
        sources.write_text(sources.read_text().replace('id     = "PRF-001"',
                                                       'id     = "PRF-009"'))
        self.assertFails("vendor targets unknown BOM id 'PRF-009'")

    def test_vendor_index_header_is_enforced(self) -> None:
        index = self.root / "modules/linear-stage/cad/vendor/vendor-index.csv"
        index.write_text("supplier,pn\nhiwin,HGR20R300\n")
        self.assertFails("header must be exactly")


class TestInstanceFreshness(FixtureCopy):
    fixture = MACHINE

    def test_stale_resolved_bom_is_refused(self) -> None:
        bom = self.root / "modules/x-stage/bom/resolved.csv"
        bom.write_text(bom.read_text().replace("27.10", "99.99"))
        self.assertFails("stale")

    def test_missing_resolved_file_is_refused(self) -> None:
        (self.root / "modules/x-stage/cad/resolved/vendor-cad.csv").unlink()
        self.assertFails("missing")


if __name__ == "__main__":
    unittest.main()
