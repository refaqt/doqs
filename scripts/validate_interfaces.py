"""Check that SysML ports, okh.toml entries and FreeCAD frames agree.

An interface lives three times, and one rule names all three
(docs/decisions/2026-10-07_port-and-frame-share-a-name.md). This gate reads
all three and reports where they disagree:

- a `port def` without a version suffix (`_v1`);
- an outside interface in `okh.toml` with no `port def` of that name and
  major version, and the other way round for the ports the assembly binds;
- a port whose type is not defined or imported;
- a `connect` whose two ends are not one plain and one conjugate port of
  the same type;
- a `[[part]]` or `[[bought-part]]` whose `sysml` names no part def;
- a port on a part whose file has no frame `IF_<port>`, and a frame with no
  port.

Everything is a warning by default, so a machine's CI stays green when its
doqs pin moves. `--strict-interfaces` turns the findings into failures.
Reads only; never writes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import interface_rules as ir
import okh_rules
import sysml_rules
from cad_rules import FRAME_PREFIX, frames as read_frames
from naming_rules import is_under_parts_library, is_under_tooling_submodule, repo_root_from_script
from validate_variants import library_part, mounted_libraries


def module_dirs(root: Path) -> list[Path]:
    """Every module folder with an okh.toml and an architecture/ folder."""
    found = []
    for okh in sorted(root.rglob("okh.toml")):
        if is_under_tooling_submodule(okh, root) or is_under_parts_library(okh, root):
            continue
        if (okh.parent / "architecture").is_dir():
            found.append(okh.parent)
    return found


def _part_files(root: Path, module_dir: Path, data: dict) -> dict[str, Path | None]:
    """``{part def: file}`` from [[part]] and [[bought-part]] entries."""
    files: dict[str, Path | None] = {}
    for entry in data.get("part", []) or []:
        name = entry.get("sysml")
        if name:
            sources = entry.get("source") or []
            files[str(name)] = (module_dir / sources[0]) if sources else None
    mounts = mounted_libraries(root)
    for entry in data.get("bought-part", []) or []:
        name = entry.get("sysml")
        if not name:
            continue
        ref = str(entry.get("part", ""))
        lib, _, part = ref.partition(":")
        mount = next((m for m in mounts if Path(m).name == lib), None)
        file = None
        if mount:
            row, family = library_part(root, mount, part)
            if row and (row.get("cad") or "").strip():
                file = root / mount / family / row["cad"].strip()
        files[str(name)] = file
    return files


def check_module(root: Path, module_dir: Path) -> list[str]:
    """Findings for one module, as ``<path>: <problem>`` lines."""
    findings: list[str] = []
    okh = module_dir / "okh.toml"
    data = okh_rules.load(okh.read_text(encoding="utf-8"))
    rel_okh = okh.relative_to(root).as_posix()
    sysml_files = sorted((module_dir / "architecture").glob("*.sysml"))
    port_defs: dict[str, Path] = {}
    parts: dict[str, sysml_rules.Node] = {}
    trees = []
    for path in sysml_files:
        text = path.read_text(encoding="utf-8")
        tree = sysml_rules.parse(text)
        trees.append((path, tree))
        rel = path.relative_to(root).as_posix()
        for node in sysml_rules.walk(tree):
            if node.kind == "port_def" and node.name:
                port_defs[node.name] = path
                if sysml_rules.version_of(node.name) is None:
                    findings.append(f"{rel}: port def {node.name} has no version suffix like _v1")
            elif node.kind == "part_def" and node.name:
                parts[node.name] = node
    imported = set()
    for path, tree in trees:
        for node in sysml_rules.walk(tree):
            if node.kind == "import" and node.name:
                imported.add(node.name)
    # Only a file import ('../x.sysml'::Pkg::*) can bring port defs from
    # another module. The standard libraries (ScalarValues::*) never do.
    wildcard_imports = any(i.startswith("'") and i.endswith("::*") for i in imported)

    # Ports: type exists; frame exists.
    files = _part_files(root, module_dir, data)
    for name, node in parts.items():
        for port in node.of_kind("port"):
            type_name = (port.type_name or "").split("::")[-1]
            if type_name not in port_defs and not wildcard_imports and type_name not in imported:
                findings.append(f"{rel_okh}: part def {name} port {port.name} has type {type_name}, "
                                "which is not defined or imported")
    for entry_kind in ("part", "bought-part"):
        for entry in data.get(entry_kind, []) or []:
            name = entry.get("sysml")
            if name and str(name) not in parts:
                findings.append(f"{rel_okh}: [[{entry_kind}]] sysml = {name!r} names no part def")
    for name, file in files.items():
        node = parts.get(name)
        if node is None or file is None or not file.is_file():
            continue
        labels = {label for _, label in read_frames(file)}
        rel_file = file.relative_to(root).as_posix() if file.is_relative_to(root) else str(file)
        wanted = {ir.frame_label(p.name): p.name for p in node.of_kind("port") if p.name}
        for label, port in wanted.items():
            if label not in labels:
                findings.append(f"{rel_file}: port {port} of {name} has no frame {label}")
        for label in sorted(labels):
            if label.startswith(FRAME_PREFIX) and label not in wanted:
                findings.append(f"{rel_file}: frame {label} has no port {ir.port_name_of(label)} on {name}")

    # Connections: one plain, one conjugate, same type.
    for path, tree in trees:
        rel = path.relative_to(root).as_posix()
        for node in sysml_rules.walk(tree):
            if node.kind != "connect" or not node.value or node.parent is None:
                continue
            a, b = node.value.split(" to ", 1)
            ends = []
            for end in (a.strip(), b.strip()):
                usage, _, port_name = end.rpartition(".")
                usage_node = sysml_rules.find(tree, f"{sysml_rules.path_of(node.parent)}.{usage}") if usage else None
                part_def = parts.get((usage_node.type_name or "").split("::")[-1]) if usage_node else None
                port = part_def.child("port", port_name) if part_def else None
                if port is None:
                    findings.append(f"{rel}: connect {node.value}: {end} is not a port of a part usage here")
                    ends = []
                    break
                ends.append(port)
            if len(ends) == 2:
                if ends[0].type_name != ends[1].type_name:
                    findings.append(f"{rel}: connect {node.value} joins {ends[0].type_name} to {ends[1].type_name}")
                if ends[0].conjugated == ends[1].conjugated:
                    findings.append(f"{rel}: connect {node.value}: one side must be the plain port and the other the ~ port")

    # okh.toml mirrors the outside port defs.
    for key in ("provides-interface", "consumes-interface"):
        for name, version in okh_rules.interface_entries(okh.read_text(encoding="utf-8"), key):
            if not any(ir.okh_matches(pd, name, version) for pd in port_defs) and not wildcard_imports:
                findings.append(f"{rel_okh}: [[{key}]] {name} {version} has no port def {name}_v{version.split('.')[0]}")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--strict-interfaces", action="store_true", help="Fail on a finding")
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_script()
    findings: list[str] = []
    modules = module_dirs(root)
    for module_dir in modules:
        try:
            findings.extend(check_module(root, module_dir))
        except (okh_rules.OkhError, OSError) as exc:
            findings.append(f"{module_dir.relative_to(root).as_posix()}: {exc}")
    if not findings:
        print(f"ok    interfaces agree in {len(modules)} modules (SysML, okh.toml, frames)")
        return 0
    label = "FAIL" if args.strict_interfaces else "WARN"
    print(f"{label}  interfaces: {len(findings)} findings; see doqs/docs/architecture.md#one-name-for-a-port-a-frame-and-an-okh-entry")
    for line in findings:
        print(f"      {line}")
    return 1 if args.strict_interfaces else 0


if __name__ == "__main__":
    sys.exit(main())
