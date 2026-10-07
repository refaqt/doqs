"""Edit an `okh.toml` as text, so comments and layout survive.

Python reads TOML (`tomllib`) but does not write it. A tool that adds a
`[[part]]` or a `[[provides-interface]]` to a manifest must not rewrite the
whole file: a person's comments would vanish and `git diff` would show the
whole file. So the edits here work on lines.

Every function takes the text and returns the new text. An entry that is
already there is left alone, so a rerun changes nothing. Only the standard
library is used. See docs/architecture.md, "OKH manifests".
"""
from __future__ import annotations

import re
import tomllib

_TABLE_HEADER = re.compile(r"^\s*(\[\[?)\s*([A-Za-z0-9_.\-]+)\s*\]\]?\s*(#.*)?$")
_KEY_LINE = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*=")


class OkhError(ValueError):
    """A request the manifest cannot satisfy."""


def load(text: str) -> dict:
    """The manifest as a dict, or an error naming the TOML problem."""
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as err:
        raise OkhError(f"not valid TOML: {err}") from err


def format_value(value) -> str:
    """One TOML value: strings are quoted, lists are inline, dates stay as given."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(format_value(v) for v in value) + "]"
    if isinstance(value, RawValue):
        return value.text
    text = str(value)
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


class RawValue(str):
    """A value written as is, like a date ``2026-10-07`` or a table."""

    @property
    def text(self) -> str:
        return str(self)


def _tables(text: str) -> list[tuple[int, int, str, bool]]:
    """``(start line, end line, name, is_array)`` for every table in the text.

    The end line is exclusive. The first entry, when present, is the root
    table with an empty name: the key lines before any header.
    """
    lines = text.splitlines()
    found: list[tuple[int, int, str, bool]] = []
    current_start, current_name, current_array = 0, "", False
    for i, line in enumerate(lines):
        m = _TABLE_HEADER.match(line)
        if not m:
            continue
        found.append((current_start, i, current_name, current_array))
        current_start, current_name, current_array = i, m.group(2), m.group(1) == "[["
    found.append((current_start, len(lines), current_name, current_array))
    return found


def has_table(text: str, header: str, match: dict | None = None) -> bool:
    """True when a table ``header`` exists, with every key in ``match`` equal."""
    return find_table(text, header, match) is not None


def find_table(text: str, header: str, match: dict | None = None) -> tuple[int, int] | None:
    """``(start line, end line)`` of the first table that matches, or ``None``."""
    name = header.strip("[]").strip()
    data = load(text)
    entries = data.get(name)
    candidates = entries if isinstance(entries, list) else ([entries] if entries else [])
    index = -1
    for start, end, table_name, _ in _tables(text):
        if table_name != name:
            continue
        index += 1
        entry = candidates[index] if index < len(candidates) else {}
        if match and any(entry.get(k) != v for k, v in match.items()):
            continue
        return start, end
    return None


def _render_table(header: str, fields: dict, comment: str | None) -> str:
    width = max((len(k) for k in fields), default=0)
    lines = []
    if comment:
        lines += [f"# {line}" for line in comment.splitlines()]
    lines.append(header)
    for key, value in fields.items():
        lines.append(f"{key.ljust(width)} = {format_value(value)}")
    return "\n".join(lines) + "\n"


def append_table(text: str, header: str, fields: dict, comment: str | None = None,
                 match: dict | None = None) -> str:
    """Add a ``[[table]]`` or ``[table]`` at the end. Unchanged when it exists.

    ``match`` names the keys that identify the entry; by default every key in
    ``fields`` that is a string counts, so the same entry is never added twice.
    """
    load(text)
    if match is None:
        match = {k: v for k, v in fields.items() if isinstance(v, (str, int)) and not isinstance(v, RawValue)}
    if has_table(text, header, match or None):
        return text
    block = _render_table(header, fields, comment)
    if text and not text.endswith("\n"):
        text += "\n"
    if text.strip():
        text += "\n"
    return text + block


def set_key(text: str, key: str, value, header: str = "", match: dict | None = None) -> str:
    """Set ``key`` in the root table (``header`` empty) or in one table.

    An existing key line is replaced; a missing key is added at the end of
    the table, before any blank lines that separate it from the next one.
    """
    lines = text.splitlines(keepends=True)
    name = header.strip("[]").strip()
    if name:
        span = find_table(text, header, match)
        if span is None:
            raise OkhError(f"no table {header} in the manifest")
    else:
        tables = _tables(text)
        span = (0, tables[0][1]) if tables and tables[0][2] == "" else (0, 0)
    start, end = span
    rendered = f"{key} = {format_value(value)}\n"
    for i in range(start, end):
        m = _KEY_LINE.match(lines[i])
        if m and m.group(1) == key:
            comment = lines[i].split("#", 1)[1] if "#" in lines[i] and not lines[i].strip().startswith("#") else ""
            lines[i] = rendered if not comment else rendered.rstrip("\n") + "  #" + comment
            return "".join(lines)
    # Add after the last non-blank line of the table.
    insert = end
    while insert > start and not lines[insert - 1].strip():
        insert -= 1
    lines.insert(insert, rendered)
    return "".join(lines)


def get_key(text: str, key: str, header: str = "", match: dict | None = None):
    """A value from the root table or one table, or ``None``."""
    data = load(text)
    if not header:
        return data.get(key)
    name = header.strip("[]").strip()
    entries = data.get(name)
    candidates = entries if isinstance(entries, list) else ([entries] if entries else [])
    for entry in candidates:
        if not match or all(entry.get(k) == v for k, v in match.items()):
            return entry.get(key)
    return None


def render_manifest(fields: dict, comment: str | None = None) -> str:
    """A fresh manifest: the root keys, in the order given."""
    head = "".join(f"# {line}\n" for line in (comment or "").splitlines())
    return head + "".join(f"{k} = {format_value(v)}\n" for k, v in fields.items())


def interface_entries(text: str, key: str) -> list[tuple[str, str]]:
    """``(name, version)`` of every ``[[provides-interface]]`` or consumes entry."""
    data = load(text)
    return [
        (str(e.get("name", "")), str(e.get("version", "")))
        for e in data.get(key, []) or []
        if isinstance(e, dict)
    ]
