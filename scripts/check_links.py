"""Check SysML import paths and relative OKH file references."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from naming_rules import is_under_doqs_submodule, repo_root_from_script


IMPORT_RE = re.compile(r"""import\s+['"]([^'"]+)['"]""")


def check_sysml(root: Path) -> list[str]:
    errors: list[str] = []
    for sysml in root.rglob("*.sysml"):
        if is_under_doqs_submodule(sysml, root):
            continue
        text = sysml.read_text(encoding="utf-8")
        for match in IMPORT_RE.finditer(text):
            rel_import = match.group(1)
            target = (sysml.parent / rel_import).resolve()
            if not target.exists():
                errors.append(f"{sysml.relative_to(root)}: import not found: {rel_import}")
    return errors


def check_okh_relative(root: Path) -> list[str]:
    import tomllib

    errors: list[str] = []
    for okh in root.rglob("okh.toml"):
        if is_under_doqs_submodule(okh, root):
            continue
        with open(okh, "rb") as f:
            data = tomllib.load(f)
        base = okh.parent
        for key in ("bom", "readme"):
            if key in data and not (base / data[key]).exists():
                errors.append(f"{okh.relative_to(root)}: missing {key} → {data[key]}")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check SysML imports and OKH paths.")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve() if args.root else repo_root_from_script()
    errors = check_sysml(root) + check_okh_relative(root)
    if errors:
        for e in errors:
            print(f"FAIL  {e}")
        raise SystemExit(1)
    print("ok    all SysML imports and OKH paths resolve")
    raise SystemExit(0)
