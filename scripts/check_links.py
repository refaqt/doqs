"""Check SysML import paths and relative OKH file references."""
import re
from pathlib import Path


IMPORT_RE = re.compile(r"""import\s+['"]([^'"]+)['"]""")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def check_sysml(root: Path) -> list[str]:
    errors: list[str] = []
    for sysml in root.rglob("*.sysml"):
        if "doqs" in sysml.parts:
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
        if "doqs" in okh.parts:
            continue
        with open(okh, "rb") as f:
            data = tomllib.load(f)
        base = okh.parent
        for key in ("bom", "readme"):
            if key in data and not (base / data[key]).exists():
                errors.append(f"{okh.relative_to(root)}: missing {key} → {data[key]}")
    return errors


if __name__ == "__main__":
    root = repo_root()
    errors = check_sysml(root) + check_okh_relative(root)
    if errors:
        for e in errors:
            print(f"FAIL  {e}")
        raise SystemExit(1)
    print("ok    all SysML imports and OKH paths resolve")
    raise SystemExit(0)
