"""Check SysML import paths, relative OKH file references, and markdown links."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote

from naming_rules import is_under_tooling_submodule, repo_root_from_script


IMPORT_RE = re.compile(r"""import\s+['"]([^'"]+)['"]""")

MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

#: Files whose links resolve from a repository root, not from their own folder,
#: because they are meant to be pasted into a root README. Checking them where
#: they sit reports failures that are not failures.
MARKDOWN_SKIP = ("templates/licensing/tools/README-licence-section.md",)


def check_sysml(root: Path) -> list[str]:
    errors: list[str] = []
    for sysml in root.rglob("*.sysml"):
        if is_under_tooling_submodule(sysml, root):
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
        if is_under_tooling_submodule(okh, root):
            continue
        with open(okh, "rb") as f:
            data = tomllib.load(f)
        base = okh.parent
        for key in ("bom", "readme"):
            if key in data and not (base / data[key]).exists():
                errors.append(f"{okh.relative_to(root)}: missing {key} → {data[key]}")
    return errors


def check_markdown(root: Path) -> list[str]:
    """Relative markdown links that point at something which is not there.

    Off by default: a machine repository should not go red on a doqs pin bump
    because of a link it has carried for months. Turn it on with --markdown once
    the repository is clean.
    """
    errors: list[str] = []
    for md in sorted(root.rglob("*.md")):
        if is_under_tooling_submodule(md, root):
            continue
        rel = md.relative_to(root).as_posix()
        if rel in MARKDOWN_SKIP:
            continue
        for target in MARKDOWN_LINK_RE.findall(md.read_text(encoding="utf-8")):
            link = target.strip()
            if link.startswith(("http://", "https://", "mailto:", "#", "<")):
                continue
            path = unquote(link.split("#")[0].split("?")[0])
            if not path:
                continue
            target = md.parent / path
            # A link into `doqs/` or `.agents/` points at another repository.
            # Those folders are empty until someone checks the submodules out,
            # and CI here does not, so the link is not ours to verify. Every
            # other gate skips that content for the same reason.
            if is_under_tooling_submodule(target, root):
                continue
            if not target.exists():
                errors.append(f"{rel}: link not found: {link}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check SysML imports, OKH paths, and (with --markdown) markdown links.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Also check relative markdown links (off by default)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_script()
    errors = check_sysml(root) + check_okh_relative(root)
    if args.markdown:
        errors += check_markdown(root)
    if errors:
        for e in errors:
            print(f"FAIL  {e}")
        return 1
    what = "SysML imports, OKH paths and markdown links" if args.markdown else "SysML imports and OKH paths"
    print(f"ok    all {what} resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
