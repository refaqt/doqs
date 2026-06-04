"""Validate that build.toml lockfiles represent interface-consistent compositions."""
from pathlib import Path
import tomllib


def load_module_manifest(root: Path, mod_entry: dict) -> dict:
    mod_path = root / mod_entry["path"] / "okh.toml"
    with open(mod_path, "rb") as f:
        return tomllib.load(f)


def collect_interfaces(modules: list[dict]) -> tuple[dict, list]:
    provided: dict = {}
    consumed: list = []
    for m in modules:
        manifest = m["manifest"]
        for iface in manifest.get("provides-interface", []):
            key = (iface["name"], iface["version"].split(".")[0])
            provided.setdefault(key, []).append(m["path"])
        for iface in manifest.get("consumes-interface", []):
            key = (iface["name"], iface["version"].split(".")[0])
            consumed.append({"interface": key, "by": m["path"]})
    return provided, consumed


def validate(build_path: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    with open(build_path, "rb") as f:
        build = tomllib.load(f)

    modules = []
    for entry in build.get("module", []):
        modules.append({
            "path": entry["path"],
            "version": entry["version"],
            "manifest": load_module_manifest(repo_root, entry),
        })
    for entry in build.get("module", []):
        if "adapter" not in entry:
            continue
        adapter_path = entry["adapter"].split("@")[0]
        modules.append({
            "path": adapter_path,
            "version": entry["adapter"].split("@")[1],
            "manifest": load_module_manifest(repo_root, {"path": adapter_path}),
        })

    provided, consumed = collect_interfaces(modules)
    for need in consumed:
        if need["interface"] not in provided:
            errors.append(
                f"Unsatisfied interface {need['interface']} required by "
                f"{need['by']} — no module in this build provides it"
            )
    return errors


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


if __name__ == "__main__":
    root = repo_root()
    all_ok = True
    for build_file in sorted((root / "builds").rglob("build.toml")):
        errs = validate(build_file, root)
        rel = build_file.relative_to(root)
        if errs:
            all_ok = False
            print(f"FAIL  {rel}")
            for e in errs:
                print(f"      {e}")
        else:
            print(f"ok    {rel}")
    if not list((root / "builds").rglob("build.toml")):
        print("No build.toml files found under builds/")
    raise SystemExit(0 if all_ok else 1)
