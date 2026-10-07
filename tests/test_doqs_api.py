"""The import surface for tools: every promised name exists and the version check works."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import doqs_api  # noqa: E402

PROMISED = (
    "add_interface", "intake", "wrap_part", "install_module", "install_part", "install_brand",
    "install_family", "use_part", "bump_pin", "document_tree", "frames", "object_labels",
    "joint_targets", "resolve_joint_target", "parse_sysml", "interfaces", "parts", "connections",
    "requirements", "load_okh", "read_rows", "mirror_diff", "library_part", "mounted_libraries",
    "frame_label", "port_def_name", "okh_entry", "run_macro", "rpc_available", "find_freecad", "Report",
)


class TestApi(unittest.TestCase):
    def test_every_promised_name_is_callable(self):
        for name in PROMISED:
            self.assertTrue(callable(getattr(doqs_api, name)), name)

    def test_requires(self):
        major, minor = doqs_api.API_VERSION
        doqs_api.requires(major, minor)
        doqs_api.requires(major, 0)
        with self.assertRaises(RuntimeError) as ctx:
            doqs_api.requires(major, minor + 1)
        self.assertIn("bump the doqs pin", str(ctx.exception))
        with self.assertRaises(RuntimeError):
            doqs_api.requires(major + 1)


if __name__ == "__main__":
    unittest.main()
