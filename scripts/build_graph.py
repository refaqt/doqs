"""Regenerate graph/usage-graph.json from okh.toml manifests and build lockfiles."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

from naming_rules import family_root, is_under_tooling_submodule


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


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def collect_has_components(manifest_path: Path, root: Path) -> list[dict]:
    """Child edges of one manifest, each carrying its variant selection.

    Three kinds of edge exist, and the variant keys are what make the graph
    able to answer "who uses the 500 mm servo-linear?" rather than only
    "who uses the linear stage?":

    * ``[[hasComponent]]`` — the classic edge, optionally pinning a
      ``composition`` and ``model`` for the zero-override shortcut.
    * ``[composition]`` — a thin composition module's core and options,
      resolved against the family root.
    * ``[instance]`` — a consumer's choice of family variant.
    """
    data = load_toml(manifest_path)
    children: list[dict] = []
    seen: set[tuple] = set()

    def add(path: str, **variant: str) -> None:
        if not path:
            return
        key = (path, variant.get("composition", ""), variant.get("model", ""))
        if key in seen:
            return
        seen.add(key)
        children.append({"path": path, **{k: v for k, v in variant.items() if v}})

    for comp in data.get("hasComponent", []):
        add(
            module_path_from_url(comp.get("component", ""), root) or "",
            composition=str(comp.get("composition", "")),
            model=str(comp.get("model", "")),
        )

    composition = data.get("composition")
    if composition:
        family = family_root(manifest_path) or manifest_path.parent.parent
        for target in [composition.get("core", ""), *composition.get("options", [])]:
            if target and (family / target / "okh.toml").exists():
                add(_rel(family / target, root))

    instance = data.get("instance", {})
    if instance.get("family") and instance.get("composition"):
        target = root / instance["family"] / instance["composition"]
        if (target / "okh.toml").exists():
            add(
                _rel(target, root),
                model=str(instance.get("model", "")),
                sku=str(instance.get("sku", "")),
            )

    modules_dir = manifest_path.parent / "modules"
    if modules_dir.is_dir():
        for sub in sorted(modules_dir.iterdir()):
            if sub.is_dir() and (sub / "okh.toml").exists():
                add(_rel(sub, root))
    return children


def walk_parents(root: Path) -> dict[str, list[dict]]:
    used_by: dict[str, list[dict]] = {}

    for okh in sorted(root.rglob("okh.toml")):
        if is_under_tooling_submodule(okh, root):
            continue
        parent = okh.parent.relative_to(root)
        parent_key = "." if str(parent) == "." else parent.as_posix()
        version = load_toml(okh).get("version", "?")
        for child in collect_has_components(okh, root):
            entry = {"path": parent_key, "version": version}
            for key in ("composition", "model", "sku"):
                if child.get(key):
                    entry[key] = child[key]
            used_by.setdefault(child["path"], []).append(entry)
    return used_by


def builds_using_module(root: Path) -> dict[str, list[dict]]:
    """Builds that pin each module, carrying the model and SKU they pinned."""
    result: dict[str, list[dict]] = {}
    for build_file in (root / "builds").rglob("build.toml"):
        build_id = str(build_file.parent.relative_to(root)).replace("\\", "/")
        data = load_toml(build_file)
        for entry in data.get("module", []):
            path = entry.get("path", "")
            if entry.get("composition"):
                path = f"{path}/{entry['composition']}"
            record: dict = {"build": build_id}
            for key in ("model", "sku"):
                if entry.get(key):
                    record[key] = entry[key]
            result.setdefault(path, []).append(record)
    return result


def main(root: Path | None = None) -> None:
    root = root or repo_root()
    used_by_map = walk_parents(root)
    build_map = builds_using_module(root)
    graph: dict = {}

    for okh in sorted(root.rglob("okh.toml")):
        if is_under_tooling_submodule(okh, root):
            continue
        rel = okh.parent.relative_to(root)
        key = "." if str(rel) == "." else str(rel).replace("\\", "/")
        data = load_toml(okh)
        node: dict = {
            "current_version": data.get("version", "?"),
            "trl": data.get("technology-readiness-level"),
            "used_by": used_by_map.get(key, []),
            "used_by_builds": build_map.get(key, []),
        }
        models = [m.get("name") for m in data.get("model", []) if m.get("name")]
        if models:
            node["models"] = models
        graph[key] = node

    out = root / "graph" / "usage-graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(graph)} modules)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Regenerate graph/usage-graph.json.")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()
    main(args.root.resolve() if args.root else None)
