"""Unit tests for model-aware BOM resolution: overlays, templates, length tables."""
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

import resolve_bom  # noqa: E402
from resolve_bom import BomError, apply_overlay, load_bom, resolve  # noqa: E402

FAMILY = _REPO / "tests" / "fixtures" / "variant-family"
CORE_REL = Path("modules") / "linear-stage"


class FamilyCopy(unittest.TestCase):
    """Each test gets a scratch copy so fixtures are never mutated."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "family"
        shutil.copytree(FAMILY, self.root)
        self.core = self.root / CORE_REL
        self.addCleanup(self._tmp.cleanup)

    def row(self, rows: list[dict], part_id: str) -> dict:
        return next(r for r in rows if r["id"] == part_id)


class TestLengthTables(FamilyCopy):
    def test_part_number_follows_the_selected_length(self) -> None:
        expected = {"default": "HGR20R300", "500mm": "HGR20R500", "800mm": "HGR20R800"}
        for model, pn in expected.items():
            with self.subTest(model=model):
                rows, _ = resolve(self.core, model)
                self.assertEqual(self.row(rows, "PRF-001")["supplier_1_pn"], pn)

    def test_price_and_mass_come_from_the_table(self) -> None:
        rows, _ = resolve(self.core, "500mm")
        rail = self.row(rows, "PRF-001")
        self.assertEqual(rail["unit_cost_eur"], "27.10")
        self.assertEqual(rail["unit_mass_g"], "2150")

    def test_vendor_step_follows_the_selected_length(self) -> None:
        _, vendor = resolve(self.core, "800mm")
        entry = next(v for v in vendor if v["id"] == "PRF-001")
        self.assertEqual(entry["cad"], "cad/vendor/hiwin/HGR20R800.step")

    def test_unstocked_length_is_refused(self) -> None:
        """A length nobody sells must fail here, not at purchasing."""
        (self.core / "cad" / "params" / "640mm.csv").write_text(
            "alias,value,unit,description\nrail_length,640,mm,x\n")
        with self.assertRaises(BomError) as caught:
            resolve(self.core, "640mm")
        self.assertIn("Stocked: 300, 500, 800", str(caught.exception))

    def test_nearest_up_buys_stock_and_records_the_cut(self) -> None:
        sources = self.core / "bom" / "sources.toml"
        sources.write_text(sources.read_text().replace('match   = "exact"',
                                                       'match   = "nearest-up"'))
        (self.core / "cad" / "params" / "640mm.csv").write_text(
            "alias,value,unit,description\nrail_length,640,mm,x\n")
        rows, _ = resolve(self.core, "640mm")
        rail = self.row(rows, "PRF-001")
        self.assertEqual(rail["supplier_1_pn"], "HGR20R800")
        self.assertIn("stock length 800, cut to 640", rail["notes"])


class TestTemplates(FamilyCopy):
    def test_alias_placeholders_are_substituted(self) -> None:
        rows, _ = resolve(self.core, "500mm")
        self.assertEqual(self.row(rows, "PRF-002")["spec"],
                         "40x80 profile, cut to 540 mm")

    def test_unknown_placeholder_is_reported(self) -> None:
        bom = self.core / "bom" / "bom.csv"
        bom.write_text(bom.read_text().replace("{extrusion_length}", "{nope}"))
        with self.assertRaisesRegex(BomError, "unknown parameter"):
            resolve(self.core, "default")


class TestOverlays(FamilyCopy):
    def overlay(self, text: str) -> list[dict]:
        models = self.core / "bom" / "models"
        models.mkdir(parents=True, exist_ok=True)
        (models / "500mm.csv").write_text(text)
        rows, _ = resolve(self.core, "500mm")
        return rows

    def test_only_columns_in_the_overlay_header_change(self) -> None:
        rows = self.overlay("id,qty\nSTD-001,32\n")
        bolt = self.row(rows, "STD-001")
        self.assertEqual(bolt["qty"], "32")
        self.assertEqual(bolt["name"], "Rail Bolt")          # untouched
        self.assertEqual(bolt["unit_cost_eur"], "0.14")      # untouched

    def test_qty_zero_removes_a_row(self) -> None:
        rows = self.overlay("id,qty\nSTD-001,0\n")
        self.assertNotIn("STD-001", [r["id"] for r in rows])

    def test_new_id_needs_the_full_header(self) -> None:
        with self.assertRaisesRegex(BomError, "full BOM header"):
            self.overlay("id,qty\nHW-001,4\n")

    def test_unknown_column_is_rejected(self) -> None:
        with self.assertRaisesRegex(BomError, "unknown BOM columns"):
            self.overlay("id,colour\nSTD-001,red\n")

    def test_overlay_preserves_base_row_order(self) -> None:
        base_order = [r["id"] for r in load_bom(self.core / "bom" / "bom.csv")]
        rows = self.overlay("id,qty\nSTD-001,32\n")
        self.assertEqual([r["id"] for r in rows], base_order)


class TestOutputShape(FamilyCopy):
    def test_render_keeps_the_exact_doqs_bom_header(self) -> None:
        """validate_names reads generated BOMs like any hand-written one."""
        rows, _ = resolve(self.core, "500mm")
        first = resolve_bom.render(rows).splitlines()[0]
        self.assertEqual(first, ",".join(resolve_bom.BOM_HEADERS))
        self.assertFalse(first.startswith("#"))


if __name__ == "__main__":
    unittest.main()
