"""Read and edit the SysML v2 text a machine repository keeps, without a parser.

A module's architecture lives in `architecture/*.sysml`: port definitions
(the interfaces), part definitions, part usages, ports, connections, and
requirements. Tools must add to those files without touching anything else,
so a person's comments and layout survive, and `git diff` shows only the
change.

This module is a statement scanner, not a SysML grammar. It masks comments
and strings, follows the braces, and recognises the statement kinds in use:

    package, import, port def, part def, part, port, attribute,
    requirement def, requirement, connect, bind, doc, subject, require,
    enum def, enum

Everything else is kept as an ``other`` node with its exact text span, so a
file round-trips byte for byte. Every ``add_*`` function returns the text
unchanged when the item is already there, so a rerun is a no-op.

Only the standard library is used. See docs/architecture.md, "Interfaces".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Kinds a statement can have. The keyword with a space becomes a kind with
#: an underscore: ``port def`` -> ``port_def``.
KINDS = (
    "package", "import", "port_def", "part_def", "part", "port", "attribute",
    "requirement_def", "requirement", "connect", "bind", "doc", "subject",
    "require", "enum_def", "enum", "other",
)

#: Words that may stand before the keyword of a statement.
_MODIFIERS = ("private", "public", "protected", "abstract", "ref", "readonly",
              "derived", "variation", "individual", "end")

_NAME = r"(?:[A-Za-z_]\w*|'[^']*')"
_QNAME = rf"{_NAME}(?:::{_NAME})*"

_HEAD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("package", re.compile(rf"^package\s+(?P<name>{_NAME})")),
    ("import", re.compile(r"^import\s+(?P<name>\S.*?)\s*$")),
    ("port_def", re.compile(rf"^port\s+def\s+(?P<name>{_NAME})")),
    ("part_def", re.compile(rf"^part\s+def\s+(?P<name>{_NAME})")),
    ("requirement_def", re.compile(
        rf"^requirement\s+def\s*(?:<\s*(?P<short>{_NAME})\s*>)?\s*(?P<name>{_NAME})?")),
    ("enum_def", re.compile(rf"^enum\s+def\s+(?P<name>{_NAME})")),
    ("connect", re.compile(r"^connect\s+(?P<a>\S+)\s+to\s+(?P<b>[^;{]+?)\s*$")),
    ("bind", re.compile(r"^bind\s+(?P<a>[^=]+?)\s*=\s*(?P<b>[^;{]+?)\s*$")),
    ("doc", re.compile(r"^doc\b")),
    ("require", re.compile(r"^require\b")),
)

#: A usage: ``part base : Base``, ``port x : ~Foo_v1``, ``attribute :>> speed = 3 [m/s]``.
_USAGE = re.compile(
    rf"^(?P<kind>part|port|attribute|requirement|subject|enum)\s+"
    rf"(?P<redef>:>>\s*)?(?P<name>{_NAME})?"
    rf"(?:\s*:\s*(?P<conj>~)?\s*(?P<type>{_QNAME}))?"
    rf"(?:\s*=\s*(?P<value>.+?))?\s*$"
)

_VERSION = re.compile(r"_v(\d+)$")


@dataclass
class Node:
    """One statement, with its exact place in the text.

    ``start``/``end`` cover the whole statement including its body and the
    closing brace or semicolon. ``body_start``/``body_end`` are the span
    inside the braces, or ``None`` when the statement has no body.
    """
    kind: str
    name: str | None = None
    short_name: str | None = None
    type_name: str | None = None
    conjugated: bool = False
    redefines: bool = False
    value: str | None = None
    head: str = ""
    start: int = 0
    end: int = 0
    head_start: int = 0
    head_end: int = 0
    body_start: int | None = None
    body_end: int | None = None
    indent: str = ""
    children: list["Node"] = field(default_factory=list)
    parent: "Node | None" = field(default=None, repr=False, compare=False)
    #: The whole file, kept on the root node only.
    text: str = field(default="", repr=False, compare=False)

    @property
    def doc(self) -> str | None:
        """The text of the first ``doc`` child, cleaned of comment marks."""
        for child in self.children:
            if child.kind == "doc":
                return doc_text(child.head)
        return None

    def child(self, kind: str, name: str) -> "Node | None":
        for c in self.children:
            if c.kind == kind and c.name == name:
                return c
        return None

    def of_kind(self, *kinds: str) -> list["Node"]:
        return [c for c in self.children if c.kind in kinds]


class SysmlError(ValueError):
    """A request that the text cannot satisfy, like an unknown part."""


# --------------------------------------------------------------------------
# Scanning
# --------------------------------------------------------------------------

def _skip_blank(text: str, i: int, end: int) -> int:
    """Skip whitespace and plain comments (not a ``doc`` comment)."""
    while i < end:
        c = text[i]
        if c.isspace():
            i += 1
        elif text.startswith("//", i):
            nl = text.find("\n", i, end)
            i = end if nl < 0 else nl + 1
        elif text.startswith("/*", i):
            close = text.find("*/", i + 2, end)
            i = end if close < 0 else close + 2
        else:
            break
    return i


def _end_of_string(text: str, i: int, end: int) -> int:
    quote = text[i]
    i += 1
    while i < end:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    return end


def _walk(text: str, i: int, end: int, stop: str) -> int:
    """Advance to the first ``stop`` character at this depth, or ``end``.

    Strings and comments are skipped. ``stop`` is ``";{"`` for a head and
    ``"}"`` for a body; inside a body, nested braces are followed.
    """
    depth = 0
    while i < end:
        c = text[i]
        if text.startswith("//", i):
            nl = text.find("\n", i, end)
            i = end if nl < 0 else nl + 1
            continue
        if text.startswith("/*", i):
            close = text.find("*/", i + 2, end)
            i = end if close < 0 else close + 2
            continue
        if c in "\"'":
            i = _end_of_string(text, i, end)
            continue
        if c == "{":
            if depth == 0 and c in stop:
                return i
            depth += 1
        elif c == "}":
            if depth == 0:
                return i if c in stop else i
            depth -= 1
        elif c == ";" and depth == 0 and c in stop:
            return i
        i += 1
    return end


def _line_indent(text: str, pos: int) -> str:
    line_start = text.rfind("\n", 0, pos) + 1
    i = line_start
    while i < len(text) and text[i] in " \t":
        i += 1
    return text[line_start:i]


def _strip_modifiers(head: str) -> str:
    words = head.split()
    while words and words[0] in _MODIFIERS and len(words) > 1:
        words.pop(0)
    return " ".join(words)


def _classify(node: Node) -> None:
    head = " ".join(node.head.split())
    head = _strip_modifiers(head)
    for kind, pattern in _HEAD_PATTERNS:
        m = pattern.match(head)
        if not m:
            continue
        node.kind = kind
        groups = m.groupdict()
        if "name" in groups and groups["name"]:
            # An import keeps its quotes: '../x.sysml'::Pkg::* is one name.
            node.name = groups["name"] if kind == "import" else groups["name"].strip("'")
        if groups.get("short"):
            node.short_name = groups["short"].strip("'")
        if kind in ("connect", "bind"):
            node.name = None
            node.value = f"{groups['a'].strip()} {'to' if kind == 'connect' else '='} {groups['b'].strip()}"
        return
    m = _USAGE.match(head)
    if m:
        node.kind = m.group("kind")
        node.name = (m.group("name") or "").strip("'") or None
        node.redefines = bool(m.group("redef"))
        node.conjugated = bool(m.group("conj"))
        node.type_name = m.group("type")
        node.value = m.group("value")
        return
    node.kind = "other"
    node.name = head.split(" ")[0] if head else None


def _scan(text: str, start: int, end: int, parent: Node | None) -> list[Node]:
    nodes: list[Node] = []
    i = _skip_blank(text, start, end)
    while i < end:
        node = Node(kind="other", start=i, head_start=i, indent=_line_indent(text, i), parent=parent)
        if re.match(r"doc\b", text[i:i + 4]):
            open_ = text.find("/*", i, end)
            close = text.find("*/", open_ + 2, end) if open_ >= 0 else -1
            node.head_end = node.end = (close + 2) if close >= 0 else end
            node.head = text[i:node.head_end]
            node.kind = "doc"
        else:
            j = _walk(text, i, end, ";{")
            node.head_end = j
            node.head = text[i:j]
            if j < end and text[j] == "{":
                node.body_start = j + 1
                k = _walk(text, j + 1, end, "}")
                node.body_end = k
                node.end = min(k + 1, end)
                node.children = _scan(text, node.body_start, node.body_end, node)
            elif j < end and text[j] == ";":
                node.end = j + 1
            else:
                node.end = end
            _classify(node)
        nodes.append(node)
        i = _skip_blank(text, node.end, end)
    return nodes


def parse(text: str) -> Node:
    """The root node of a file. Its children are the top-level statements."""
    root = Node(kind="root", start=0, end=len(text), body_start=0, body_end=len(text), text=text)
    root.children = _scan(text, 0, len(text), root)
    return root


def doc_text(comment: str) -> str:
    """``doc /* ... */`` -> the text inside, without the comment marks."""
    m = re.search(r"/\*(.*?)\*/", comment, re.S)
    if not m:
        return ""
    lines = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("*"):
            line = line[1:].strip()
        lines.append(line)
    return " ".join(l for l in lines if l).strip()


# --------------------------------------------------------------------------
# Finding
# --------------------------------------------------------------------------

def _find_named(scope: Node, name: str) -> Node | None:
    for child in scope.children:
        if child.name == name and child.kind not in ("doc", "other", "import"):
            return child
    return None


def find(root: Node, path: str) -> Node | None:
    """A node by its path: ``CompactStage::Base``, ``CompactStage::CompactStage.base``.

    ``::`` steps into a package or a definition; ``.`` steps into a usage
    inside the last definition. ``None`` when a step is missing.
    """
    scope: Node | None = root
    for step in [s for s in path.split("::") if s]:
        if scope is None:
            return None
        parts = step.split(".")
        scope = _find_named(scope, parts[0])
        for usage in parts[1:]:
            if scope is None:
                return None
            scope = _find_named(scope, usage)
    return scope


def _require(root: Node, path: str, kinds: tuple[str, ...]) -> Node:
    node = find(root, path)
    if node is None or node.kind not in kinds:
        raise SysmlError(f"no {' or '.join(k.replace('_', ' ') for k in kinds)} at {path!r}")
    return node


def version_of(name: str) -> int | None:
    """``RailMountInterface_v1`` -> 1; ``None`` when the name has no version."""
    m = _VERSION.search(name)
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------

def path_of(node: Node) -> str:
    """The path ``find()`` accepts for this node."""
    steps: list[str] = []
    current: Node | None = node
    while current is not None and current.kind != "root":
        if current.name:
            steps.append(current.name)
        current = current.parent
    return "::".join(reversed(steps))


def walk(node: Node):
    """Every node below ``node``, depth first, in text order."""
    for child in node.children:
        yield child
        yield from walk(child)


def interfaces(root: Node) -> list[dict]:
    """Every ``port def``: name, version, doc, attributes, package path."""
    out = []
    for node in walk(root):
        if node.kind != "port_def":
            continue
        out.append({
            "name": node.name,
            "version": version_of(node.name or ""),
            "doc": node.doc,
            "package": path_of(node.parent) if node.parent else "",
            "attributes": [
                {"name": a.name, "type": a.type_name, "value": a.value}
                for a in node.of_kind("attribute")
            ],
        })
    return out


def parts(root: Node) -> list[dict]:
    """Every ``part def``: name, doc, ports (name, type, conjugated), usages."""
    out = []
    for node in walk(root):
        if node.kind != "part_def":
            continue
        out.append({
            "name": node.name,
            "doc": node.doc,
            "package": path_of(node.parent) if node.parent else "",
            "ports": [
                {"name": p.name, "type": p.type_name, "conjugated": p.conjugated}
                for p in node.of_kind("port")
            ],
            "usages": [
                {"name": u.name, "type": u.type_name} for u in node.of_kind("part")
            ],
            "connections": [c.value for c in node.of_kind("connect")],
        })
    return out


def connections(root: Node) -> list[tuple[str, str, str]]:
    """``(owner path, a, b)`` for every ``connect a to b``."""
    out = []
    for node in walk(root):
        if node.kind == "connect" and node.value:
            a, b = node.value.split(" to ", 1)
            out.append((path_of(node.parent) if node.parent else "", a, b))
    return out


def requirements(root: Node) -> list[dict]:
    """Every ``requirement def``: short name, name, doc, package, subject, constraint."""
    out = []
    for node in walk(root):
        if node.kind != "requirement_def":
            continue
        subject = next((s for s in node.of_kind("subject")), None)
        require = next((r for r in node.of_kind("require")), None)
        out.append({
            "short": node.short_name,
            "name": node.name,
            "doc": node.doc,
            "package": path_of(node.parent) if node.parent else "",
            "subject": {"name": subject.name, "type": subject.type_name} if subject else None,
            "constraint": " ".join(_body(require).split()) if require else None,
            "members": [
                {"name": r.name, "type": r.type_name} for r in node.of_kind("requirement")
            ],
        })
    return out


def _body(node: Node) -> str:
    """The text inside a node's braces, read from the root's text."""
    if node.body_start is None:
        return ""
    root = node
    while root.parent is not None:
        root = root.parent
    return root.text[node.body_start:node.body_end]


# --------------------------------------------------------------------------
# Editing. Every function takes the text and returns the new text.
# --------------------------------------------------------------------------

def _indent_unit(text: str, scope: Node) -> str:
    """The indentation of statements inside ``scope``."""
    for child in scope.children:
        if child.indent:
            return child.indent
    return scope.indent + "    "


def _reindent(snippet: str, indent: str) -> str:
    lines = snippet.strip("\n").splitlines()
    return "\n".join((indent + line) if line.strip() else "" for line in lines)


def insert_into_body(text: str, scope: Node, snippet: str, after: Node | None = None,
                     before: Node | None = None, blank_line: bool = True) -> str:
    """Insert ``snippet`` inside ``scope``'s braces.

    After ``after``, before ``before``, or else before the closing brace.
    The snippet is indented like the statements already there.
    """
    if scope.body_start is None:
        raise SysmlError(f"{scope.kind} {scope.name!r} has no body to insert into")
    indent = _indent_unit(text, scope)
    block = _reindent(snippet, indent)
    if after is not None:
        pos = after.end
        # Keep a trailing comment on the same line with its statement.
        nl = text.find("\n", pos)
        if nl >= 0 and text[pos:nl].strip().startswith("//"):
            pos = nl
        gap = "\n\n" if blank_line else "\n"
        return text[:pos] + gap + block + text[pos:]
    if before is not None:
        line_start = text.rfind("\n", 0, before.start) + 1
        gap = "\n\n" if blank_line else "\n"
        return text[:line_start] + block + gap + text[line_start:]
    close = scope.body_end
    inner = text[scope.body_start:close]
    if not inner.strip():
        return text[:scope.body_start] + "\n" + block + "\n" + scope.indent + text[close:]
    line_start = text.rfind("\n", 0, close) + 1
    gap = "\n" if not blank_line else ("\n" if inner.rstrip("\n").endswith("\n") else "\n\n")
    stripped = text[:line_start].rstrip("\n")
    return stripped + gap + block + "\n" + text[line_start:]


def _doc_snippet(doc: str | None, indent: str = "    ") -> str:
    if not doc:
        return ""
    words = doc.split()
    lines: list[str] = []
    line = ""
    for word in words:
        if len(line) + len(word) + 1 > 68 and line:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    if len(lines) == 1:
        return f"{indent}doc /* {lines[0]} */\n"
    body = "\n".join(f"{indent} * {l}" for l in lines)
    return f"{indent}doc /*\n{body}\n{indent} */\n"


def add_port_def(text: str, package: str, name: str, doc: str | None = None,
                 attributes: tuple[str, ...] = ()) -> str:
    """Add ``port def <name>`` to a package. Unchanged when it exists.

    It goes after the last ``port def`` in the package, so interfaces stay
    together, or else before the first ``part def``, or else at the end.
    """
    root = parse(text)
    scope = _require(root, package, ("package", "root"))
    if scope.child("port_def", name):
        return text
    lines = [_doc_snippet(doc)]
    lines += [f"    attribute {a};\n" for a in attributes]
    inner = "".join(lines)
    snippet = f"port def {name} {{\n{inner}}}" if inner else f"port def {name};"
    defs = scope.of_kind("port_def")
    if defs:
        return insert_into_body(text, scope, snippet, after=defs[-1])
    parts_ = scope.of_kind("part_def")
    if parts_:
        return insert_into_body(text, scope, snippet, before=parts_[0])
    return insert_into_body(text, scope, snippet)


def add_part_def(text: str, package: str, name: str, doc: str | None = None,
                 ports: tuple[tuple[str, str, bool], ...] = ()) -> str:
    """Add ``part def <name>`` with ``ports`` as ``(name, type, conjugated)``."""
    root = parse(text)
    scope = _require(root, package, ("package", "root"))
    if scope.child("part_def", name):
        return text
    inner = _doc_snippet(doc)
    inner += "".join(f"    port {p} : {'~' if c else ''}{t};\n" for p, t, c in ports)
    snippet = f"part def {name} {{\n{inner}}}"
    defs = scope.of_kind("part_def")
    if defs:
        return insert_into_body(text, scope, snippet, after=defs[-1])
    port_defs = scope.of_kind("port_def")
    if port_defs:
        return insert_into_body(text, scope, snippet, after=port_defs[-1])
    return insert_into_body(text, scope, snippet)


def add_port(text: str, part_def: str, port_name: str, port_def: str,
             conjugated: bool = False) -> str:
    """Add ``port <name> : [~]<type>;`` to a part def. Unchanged when it exists.

    A port of the same name but another type or side is an error, because a
    silent change there would break the assembly that uses it.
    """
    root = parse(text)
    scope = _require(root, part_def, ("part_def", "part"))
    existing = scope.child("port", port_name)
    if existing:
        if existing.type_name != port_def or existing.conjugated != conjugated:
            raise SysmlError(
                f"{part_def} already has port {port_name!r} as "
                f"{'~' if existing.conjugated else ''}{existing.type_name}"
            )
        return text
    snippet = f"port {port_name} : {'~' if conjugated else ''}{port_def};"
    ports_ = scope.of_kind("port")
    if ports_:
        return insert_into_body(text, scope, snippet, after=ports_[-1], blank_line=False)
    docs = scope.of_kind("doc", "attribute")
    if docs:
        return insert_into_body(text, scope, snippet, after=docs[-1], blank_line=False)
    return insert_into_body(text, scope, snippet, blank_line=False)


def add_part_usage(text: str, assembly: str, usage_name: str, part_def: str) -> str:
    """Add ``part <usage> : <PartDef>;`` to an assembly's part def."""
    root = parse(text)
    scope = _require(root, assembly, ("part_def", "part"))
    existing = scope.child("part", usage_name)
    if existing:
        if existing.type_name != part_def:
            raise SysmlError(f"{assembly} already has part {usage_name!r} : {existing.type_name}")
        return text
    snippet = f"part {usage_name} : {part_def};"
    usages = scope.of_kind("part")
    if usages:
        return insert_into_body(text, scope, snippet, after=usages[-1], blank_line=False)
    attrs = scope.of_kind("doc", "attribute")
    if attrs:
        return insert_into_body(text, scope, snippet, after=attrs[-1])
    return insert_into_body(text, scope, snippet, blank_line=False)


def _same_pair(value: str | None, a: str, b: str) -> bool:
    if not value or " to " not in value:
        return False
    x, y = value.split(" to ", 1)
    return {x.strip(), y.strip()} == {a, b}


def add_connect(text: str, assembly: str, a: str, b: str, comment: str | None = None) -> str:
    """Add ``connect a to b;`` at the end of an assembly. Unchanged when present."""
    root = parse(text)
    scope = _require(root, assembly, ("part_def", "part"))
    if any(_same_pair(c.value, a, b) for c in scope.of_kind("connect")):
        return text
    snippet = (f"// {comment}\n" if comment else "") + f"connect {a} to {b};"
    connects = scope.of_kind("connect")
    if connects:
        return insert_into_body(text, scope, snippet, after=connects[-1], blank_line=bool(comment))
    return insert_into_body(text, scope, snippet)


def add_requirement_def(text: str, package: str, short: str, name: str, doc: str,
                        subject: str | None = None, constraint: str | None = None) -> str:
    """Add ``requirement def <'short'> Name { ... }`` to a package."""
    root = parse(text)
    scope = _require(root, package, ("package", "root"))
    if any(r.short_name == short or r.name == name for r in scope.of_kind("requirement_def")):
        return text
    inner = _doc_snippet(doc)
    if subject:
        inner += f"    subject {subject};\n"
    if constraint:
        inner += f"    require constraint {{ {constraint} }}\n"
    snippet = f"requirement def <'{short}'> {name} {{\n{inner}}}"
    defs = scope.of_kind("requirement_def")
    if defs:
        return insert_into_body(text, scope, snippet, after=defs[-1])
    return insert_into_body(text, scope, snippet)


def add_requirement_member(text: str, spec: str, usage_name: str, requirement: str) -> str:
    """Add ``requirement <usage> : <Package::Name>;`` to a specification block."""
    root = parse(text)
    scope = _require(root, spec, ("requirement_def",))
    if scope.child("requirement", usage_name):
        return text
    snippet = f"requirement {usage_name} : {requirement};"
    members = scope.of_kind("requirement")
    if members:
        return insert_into_body(text, scope, snippet, after=members[-1], blank_line=False)
    return insert_into_body(text, scope, snippet)


def set_doc(text: str, path: str, doc: str) -> str:
    """Replace the ``doc`` of a node, or add one as its first statement."""
    root = parse(text)
    node = find(root, path)
    if node is None:
        raise SysmlError(f"nothing at {path!r}")
    if node.body_start is None:
        raise SysmlError(f"{path} has no body for a doc")
    indent = _indent_unit(text, node)
    snippet = _doc_snippet(doc, indent="").rstrip("\n")
    existing = next((c for c in node.children if c.kind == "doc"), None)
    if existing:
        return text[:existing.start] + _reindent(snippet, indent).lstrip() + text[existing.end:]
    if node.children:
        return insert_into_body(text, node, snippet, before=node.children[0], blank_line=False)
    return insert_into_body(text, node, snippet)


def add_import(text: str, package: str, target: str, private: bool = True) -> str:
    """Add ``private import <target>;`` to a package, after the last import."""
    root = parse(text)
    scope = _require(root, package, ("package", "root"))
    for imp in scope.of_kind("import"):
        if imp.name == target:
            return text
    snippet = f"{'private ' if private else ''}import {target};"
    imports = scope.of_kind("import")
    if imports:
        return insert_into_body(text, scope, snippet, after=imports[-1], blank_line=False)
    if scope.children:
        return insert_into_body(text, scope, snippet, before=scope.children[0])
    return insert_into_body(text, scope, snippet)


def new_module_text(package: str, part_def: str, doc: str, imports: tuple[str, ...] = ()) -> str:
    """The text of a fresh ``architecture/<module>.sysml``."""
    lines = [f"package {package} {{"]
    for target in imports:
        lines.append(f"    private import {target};")
    if imports:
        lines.append("")
    lines.append(f"    part def {part_def} {{")
    lines.append(_doc_snippet(doc, indent="        ").rstrip("\n"))
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines) + "\n"
