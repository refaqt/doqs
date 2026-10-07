"""Names that tie a SysML port to a FreeCAD mounting frame and an okh entry.

An interface between two parts exists three times: as a ``port def`` with
its ports in SysML, as an ``IF_`` frame in each part's FreeCAD file, and,
when it faces outside the module, as a ``[[provides-interface]]`` or
``[[consumes-interface]]`` entry in ``okh.toml``. One rule gives all three
their names, so a tool can create them together and a validator can check
that they agree. See docs/decisions/2026-10-07_port-and-frame-share-a-name.md.

- A port ``referenceRailMount`` on a part means the frame
  ``IF_reference_rail_mount`` in that part's file.
- An interface called ``RailMount`` at major version 1 is the SysML
  ``port def RailMountInterface_v1`` and the okh entry
  ``name = "RailMountInterface"``, ``version = "1.0"``.
"""
from __future__ import annotations

import re

from cad_rules import FRAME_PREFIX

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_PORT_NAME = re.compile(r"^[a-z][A-Za-z0-9]*$")
_INTERFACE_SUFFIX = "Interface"
_PORT_DEF = re.compile(r"^(?P<base>[A-Z][A-Za-z0-9]*?)(?:Interface)?_v(?P<major>\d+)$")


def snake_case(name: str) -> str:
    """``referenceRailMount`` -> ``reference_rail_mount``; ``IF_rail_A`` stays."""
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def frame_label(port_name: str) -> str:
    """The frame label a port owns: ``referenceRailMount`` -> ``IF_reference_rail_mount``."""
    if port_name.startswith(FRAME_PREFIX):
        return port_name
    return FRAME_PREFIX + snake_case(port_name)


def port_name_of(frame_label_: str) -> str:
    """The port a frame belongs to: ``IF_reference_rail_mount`` -> ``referenceRailMount``."""
    body = frame_label_[len(FRAME_PREFIX):] if frame_label_.startswith(FRAME_PREFIX) else frame_label_
    words = [w for w in body.split("_") if w]
    if not words:
        return ""
    return words[0].lower() + "".join(w[:1].upper() + w[1:] for w in words[1:])


def is_port_name(name: str) -> bool:
    """A port name is lowerCamelCase, like ``baseMount``."""
    return bool(_PORT_NAME.match(name))


def port_def_name(name: str, major: int = 1) -> str:
    """``RailMount`` -> ``RailMountInterface_v1``; a full name is kept."""
    if _PORT_DEF.match(name):
        return name
    base = name if name.endswith(_INTERFACE_SUFFIX) else name + _INTERFACE_SUFFIX
    return f"{base}_v{major}"


def split_port_def(port_def: str) -> tuple[str, int] | None:
    """``RailMountInterface_v1`` -> ``("RailMountInterface", 1)``; ``None`` if not versioned."""
    m = _PORT_DEF.match(port_def)
    if not m:
        return None
    base = m.group("base")
    if not base.endswith(_INTERFACE_SUFFIX):
        base += _INTERFACE_SUFFIX
    return base, int(m.group("major"))


def okh_entry(port_def: str) -> dict:
    """The ``[[provides-interface]]`` fields for a port def: name and ``"<major>.0"``."""
    split = split_port_def(port_def)
    if split is None:
        raise ValueError(f"{port_def!r} has no version suffix like _v1")
    base, major = split
    return {"name": base, "version": f"{major}.0"}


def okh_matches(port_def: str, name: str, version: str) -> bool:
    """True when an okh entry names this port def at the same major version."""
    split = split_port_def(port_def)
    if split is None:
        return False
    base, major = split
    return name == base and version.split(".", 1)[0] == str(major)
