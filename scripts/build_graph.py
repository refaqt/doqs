"""Regenerate graph/usage-graph.json from okh.toml manifests and build lockfiles."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def module_path_from_url(url: str, root: Path) -> str | None:
    """Best-effort map hasComponent URL to local modules/ path."""
    marker = "/modules/"
    if marker not in url:
        return None
    tail = url.split(marker, 1)[1].split("/okh.toml")[0]
    local = root / "modules" / tail.replace("/", "/")
    if (local / "okh.toml").exists():
        return str(local.relative_to(root)).replace("\\", "/")
    return f"modules/{tail}" if tail else None


def collect_has_components(manifest_path: Path, root: Path) -> list[str]:
    data = load_toml(manifest_path)
    mod_dir = manifest_path.parent.relative_to(root)
    children: list[str] = []
    for comp in data.get("hasComponent", []):
        url = comp.get("component", "")
        local = module_path_from_url(url, root)
        if local:
            children.append(local)
    modules_dir = manifest_path.parent / "modules"
    if not modules_dir.is_dir():
        return children
    for sub in modules_dir.iterdir():
        if sub.is_dir() and (sub / "okh.toml").exists():
            rel = str(sub.relative_to(root)).replace("\\", "/")
            if rel not in children:
                children.append(rel)
    return children


def walk_parents(root: Path) -> dict[str, list[dict]]:
    used_by: dict[str, list[dict]] = {}

    for okh in root.rglob("okh.toml"):
        if "doqs" in okh.parts:
            continue
        parent = okh.parent.relative_to(root)
        parent_key = "." if str(parent) == "." else str(parent).replace("\\", "/")
        for child in collect_has_components(okh, root):
            used_by.setdefault(child, []).append({
                "path": parent_key,
                "version": load_toml(okh).get("version", "?"),
            })
    return used_by


def builds_using_module(root: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for build_file in (root / "builds").rglob("build.toml"):
        build_id = str(build_file.parent.relative_to(root)).replace("\\", "/")
        data = load_toml(build_file)
        for entry in data.get("module", []):
            path = entry.get("path", "")
            result.setdefault(path, []).append(build_id)
    return result


def main() -> None:
    root = repo_root()
    used_by_map = walk_parents(root)
    build_map = builds_using_module(root)
    graph: dict = {}

    for okh in sorted(root.rglob("okh.toml")):
        if "doqs" in okh.parts:
            continue
        rel = okh.parent.relative_to(root)
        key = "." if str(rel) == "." else str(rel).replace("\\", "/")
        data = load_toml(okh)
        graph[key] = {
            "current_version": data.get("version", "?"),
            "trl": data.get("technology-readiness-level"),
            "used_by": used_by_map.get(key, []),
            "used_by_builds": build_map.get(key, []),
        }

    out = root / "graph" / "usage-graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(graph)} modules)")


if __name__ == "__main__":
    main()
