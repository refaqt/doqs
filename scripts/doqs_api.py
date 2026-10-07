"""The functions a tool outside doqs may call, and the version of that promise.

fabriq imports doqs from the machine repository's own `doqs/scripts` folder,
so the pinned doqs is the one used. It checks ``API_VERSION`` first: a tool
built for a newer surface then says "bump the doqs pin" instead of failing in
a strange way. See docs/decisions/2026-10-07_add-and-use-verbs.md.

The names below are the promise. Everything else in `scripts/` may change
without notice.
"""
from __future__ import annotations

#: ``(major, minor)``. Major changes when a name below changes meaning or
#: goes away; minor when one is added.
API_VERSION = (1, 0)

from add_interface import add_interface  # noqa: E402,F401
from add_part import intake  # noqa: E402,F401
from cad_rules import (  # noqa: E402,F401
    document_links,
    document_tree,
    frames,
    joint_targets,
    link_targets,
    object_labels,
    resolve_joint_target,
)
from export_wrapper import wrap_part  # noqa: E402,F401
from freecad_rules import find_freecad, rpc_available, run_macro  # noqa: E402,F401
from install_module import install_brand, install_family, install_module, install_part  # noqa: E402,F401
from interface_rules import frame_label, okh_entry, port_def_name, port_name_of  # noqa: E402,F401
from library_rules import mirror_diff, read_rows  # noqa: E402,F401
from okh_rules import load as load_okh  # noqa: E402,F401
from report_rules import Report  # noqa: E402,F401
from sysml_rules import connections, interfaces, parse as parse_sysml, parts, requirements  # noqa: E402,F401
from use_part import bump_pin, use_part  # noqa: E402,F401
from validate_variants import library_part, mounted_libraries  # noqa: E402,F401


def requires(major: int, minor: int = 0) -> None:
    """Raise when this doqs is older than a tool needs."""
    if API_VERSION[0] != major or API_VERSION[1] < minor:
        raise RuntimeError(
            f"this doqs offers API {API_VERSION[0]}.{API_VERSION[1]}, the tool needs "
            f"{major}.{minor}: bump the doqs pin in this repository (git submodule update "
            "--remote doqs) or use an older tool."
        )
