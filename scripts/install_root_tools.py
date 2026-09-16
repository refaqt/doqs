"""Install consumer-root launchers and agent config from doqs/templates/.

Walks doqs/templates/<tool>/ and copies every *.bat and *.sh to the machine
repository root (same filename). Skips templates/setup-tooling/ (the bootstrap
helpers themselves). Does not copy READMEs.

Identical destination bytes are left untouched. If the template changed, the
root file is overwritten (same idea as apply_licenses.py).

Agent configuration in CONFIG_TEMPLATES is different: it is installed **once**
and never overwritten, because those files are the user's to edit. Removing the
agent-CAD guard from `.claude/settings.json` is caught by validate_cad.py rather
than silently restored here.

No-op when --root is the DOQS tools repo.

    python doqs/scripts/install_root_tools.py
    python doqs/scripts/install_root_tools.py --root PATH
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from license_rules import is_doqs_tools_repo

_DOQS_ROOT = Path(__file__).resolve().parent.parent
SKIP_TEMPLATE_DIRS = frozenset({"setup-tooling"})
LAUNCHER_GLOBS = ("*.bat", "*.sh")

#: (template path under doqs/templates/, destination under the machine root).
#: Copy-once: user-editable configuration, never overwritten on a later update.
CONFIG_TEMPLATES = (
    ("agent-cad/mcp.json", ".mcp.json"),
    ("agent-cad/claude-settings.json", ".claude/settings.json"),
)


def default_root() -> Path:
    """Machine repo root (parent of this submodule) when setup-tooling lives there.

    A standalone doqs clone has no setup-tooling helper in the parent folder,
    so this returns the tools repo itself and install() no-ops.
    """
    parent = _DOQS_ROOT.parent
    if (parent / "setup-tooling.sh").is_file() or (parent / "setup-tooling.bat").is_file():
        return parent
    return _DOQS_ROOT


def iter_root_launchers(templates: Path) -> list[Path]:
    """Return launcher files under templates/<tool>/, excluding setup-tooling."""
    if not templates.is_dir():
        return []
    found: list[Path] = []
    for group in sorted(p for p in templates.iterdir() if p.is_dir()):
        if group.name in SKIP_TEMPLATE_DIRS:
            continue
        for pattern in LAUNCHER_GLOBS:
            found.extend(sorted(group.glob(pattern)))
    return found


def install_configs(root: Path, templates: Path) -> list[str]:
    """Create missing agent config files. Existing ones are left alone."""
    actions: list[str] = []
    for rel_src, rel_dest in CONFIG_TEMPLATES:
        src = templates / rel_src
        if not src.is_file():
            continue
        dest = root / rel_dest
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        actions.append(f"created {rel_dest}")
    return actions


def install_root_tools(
    root: Path, templates: Path | None = None
) -> list[str]:
    """Copy missing or stale root launchers and agent config.

    Returns human-readable actions.
    """
    if is_doqs_tools_repo(root):
        return []
    templates = templates if templates is not None else (root / "doqs" / "templates")
    if not templates.is_dir():
        raise FileNotFoundError(f"templates not found: {templates}")
    actions: list[str] = []
    for src in iter_root_launchers(templates):
        dest = root / src.name
        data = src.read_bytes()
        existed = dest.is_file()
        if existed and dest.read_bytes() == data:
            continue
        dest.write_bytes(data)
        actions.append(f"{'updated' if existed else 'created'} {src.name}")
    actions.extend(install_configs(root, templates))
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy doqs/templates/<tool>/*.bat and *.sh to the machine repo "
            "root (except setup-tooling), and install agent config once."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Machine repo root (default: parent of this doqs/ submodule).",
    )
    args = parser.parse_args()
    root = args.root.resolve() if args.root else default_root()

    if is_doqs_tools_repo(root):
        print("ok    doqs tools repo (no root launchers or agent config)")
        return 0

    try:
        actions = install_root_tools(root)
    except FileNotFoundError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    if actions:
        print(f"updated {root}")
        for line in actions:
            print(f"      {line}")
    else:
        print(f"ok    {root} (root launchers and agent config already current)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
