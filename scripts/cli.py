"""One entry point for every doqs command.

Why this exists: `scripts/` holds nineteen files you can run. A person had to
know which one, and in which order, before they could check or regenerate
anything. Now there is one name:

    bash doqs.sh check              # from the machine repository root
    python doqs/doqs.py check       # the same thing, without the launcher

`doqs list` prints every command, and names the three scripts that stay
manual because they run inside FreeCAD.

Each step runs as its own process, the way `validate_all.py` has always run the
gates. One failing gate then cannot stop the rest of the run, and a crash in one
script cannot take the whole command down with it.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from naming_rules import repo_root_from_script

SCRIPTS_DIR = Path(__file__).resolve().parent

#: A step is (script name, fixed arguments). `--root` is added by the runner.
Step = tuple[str, tuple[str, ...]]

#: The read-only gates, in the order they run.
#:
#: `validate_all.py` runs exactly this list and keeps doing so. A machine repo
#: that bumps its doqs pin must not suddenly find new gates in its CI: the new
#: gates below arrive only when someone changes their workflow to `doqs check`.
GATES: tuple[Step, ...] = (
    ("validate_okh.py", ()),
    ("validate_licenses.py", ()),
    ("validate_names.py", ()),
    ("validate_links.py", ()),
    ("validate_build.py", ()),
    ("validate_variants.py", ()),
    ("validate_cad.py", ()),
)

#: Gates that answer "are the committed generated files current?".
#: `doqs check` runs these after the read-only gates; `validate_all.py` does not.
STALENESS: tuple[Step, ...] = (
    ("resolve_params.py", ("--table", "--check")),
    ("resolve_instance.py", ("--check",)),
    ("apply_licenses.py", ("--check",)),
)

#: Generators, in dependency order: parameters feed instances, instances feed
#: the BOM, and the graph reads the manifests the others leave behind.
GENERATE: tuple[Step, ...] = (
    ("resolve_params.py", ("--table",)),
    ("resolve_instance.py", ()),
    ("apply_licenses.py", ()),
    ("aggregate_bom.py", ()),
    ("resolve_graph.py", ()),
)

#: Commands that pass every remaining argument straight to one script.
PASSTHROUGH: dict[str, str] = {
    "syson": "syson.py",
    "export": "export_variant.py",
    "bom": "resolve_bom.py",
    "restore-build": "restore_build.py",
}

#: Scripts that cannot become a subcommand: they run inside a FreeCAD
#: interpreter, which this process cannot reach. `list` prints them so nobody
#: goes looking for a subcommand that can never exist.
FREECAD_ONLY: tuple[tuple[str, str], ...] = (
    ("cad_sync_params.py", 'exec(open("doqs/scripts/cad_sync_params.py").read()) in the FreeCAD console'),
    ("cad_fingerprint.py", "called for you by build_model.py; write() inside FreeCAD"),
    ("cad_build.py", "imported by a module's cad/build_model.py"),
)


def run_steps(steps: tuple[Step, ...], root: Path | None, extra: dict[str, list[str]] | None = None) -> list[str]:
    """Run each step in its own process. Returns the names that failed."""
    root_args = ["--root", str(root.resolve())] if root else []
    cwd = root.resolve() if root else repo_root_from_script()
    failed: list[str] = []
    for name, fixed in steps:
        cmd = [sys.executable, str(SCRIPTS_DIR / name), *root_args, *fixed]
        if extra and name in extra:
            cmd.extend(extra[name])
        print(f"--- {name} {' '.join(fixed)}".rstrip() + " ---")
        if subprocess.run(cmd, cwd=cwd).returncode != 0:
            failed.append(name)
    return failed


def report(failed: list[str], done: str) -> int:
    if failed:
        print(f"\nFAILED: {', '.join(failed)}")
        return 1
    print(f"\nok    {done}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    extra: dict[str, list[str]] = {}
    if args.expected_version:
        extra["validate_okh.py"] = ["--expected-version", args.expected_version]
    if args.strict_lexicon:
        extra["validate_names.py"] = ["--strict-lexicon"]

    steps = GATES + STALENESS
    if args.only:
        wanted = args.only if args.only.endswith(".py") else f"{args.only}.py"
        matched = tuple(
            s for s in steps
            if s[0] in (wanted, f"validate_{wanted}", f"resolve_{wanted}")
        )
        if not matched:
            print(f"error: no gate called {args.only!r}. Run 'doqs list' to see them.", file=sys.stderr)
            return 2
        steps = matched
    return report(run_steps(steps, args.root, extra), "all gates passed")


def cmd_generate(args: argparse.Namespace) -> int:
    failed = run_steps(GENERATE, args.root)
    if not failed:
        print("      Review what changed with 'git diff' before you commit it.")
    return report(failed, "everything regenerated")


def cmd_setup(args: argparse.Namespace) -> int:
    return report(run_steps((("install_root_tools.py", ()),), args.root), "root tools installed")


def cmd_passthrough(name: str, rest: list[str]) -> int:
    cmd = [sys.executable, str(SCRIPTS_DIR / PASSTHROUGH[name]), *rest]
    return subprocess.run(cmd).returncode


def cmd_run(rest: list[str]) -> int:
    if not rest:
        print("error: which script? Run 'doqs list' to see them.", file=sys.stderr)
        return 2
    name = rest[0] if rest[0].endswith(".py") else f"{rest[0]}.py"
    script = SCRIPTS_DIR / name
    if not script.is_file():
        print(f"error: no script called {name} in doqs/scripts/.", file=sys.stderr)
        return 2
    return subprocess.run([sys.executable, str(script), *rest[1:]]).returncode


def cmd_list() -> int:
    print("doqs commands — run them from your machine repository root.\n")
    rows = (
        ("check", "Every gate, plus 'are the generated files current?'"),
        ("generate", "Write every generated file, in the right order"),
        ("setup", "Install the root launchers and agent config"),
        ("syson …", "Open or save architecture/*.sysml in SysON"),
        ("export …", "Export geometry for one composition and model"),
        ("bom …", "Resolve one module's BOM for one model"),
        ("restore-build …", "Fetch back the files a machine was built from"),
        ("run <script> …", "Any script in doqs/scripts/, by name"),
        ("list", "This list"),
    )
    for name, purpose in rows:
        print(f"  {name:<16} {purpose}")

    print("\n'check' runs, in order:")
    for name, fixed in GATES + STALENESS:
        print(f"  {name} {' '.join(fixed)}".rstrip())

    print("\n'generate' runs, in order:")
    for name, fixed in GENERATE:
        print(f"  {name} {' '.join(fixed)}".rstrip())

    print("\nThese are not subcommands. They run inside FreeCAD, which this")
    print("process cannot reach:")
    for name, how in FREECAD_ONLY:
        print(f"  {name:<22} {how}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doqs",
        description="One entry point for the doqs tools. Run from your machine repository root.",
    )
    subs = parser.add_subparsers(dest="command")

    check = subs.add_parser("check", help="Run every gate on this repository")
    check.add_argument("--root", type=Path, default=None, help="Machine repo root")
    check.add_argument("--only", default=None, help="Run one gate, by name (see 'doqs list')")
    check.add_argument("--expected-version", default=None, help="Passed to validate_okh.py")
    check.add_argument("--strict-lexicon", action="store_true", help="Passed to validate_names.py")

    generate = subs.add_parser("generate", help="Write every generated file")
    generate.add_argument("--root", type=Path, default=None, help="Machine repo root")

    setup = subs.add_parser("setup", help="Install root launchers and agent config")
    setup.add_argument("--root", type=Path, default=None, help="Machine repo root")

    for name in PASSTHROUGH:
        subs.add_parser(name, add_help=False, help=f"Pass every argument to {PASSTHROUGH[name]}")
    subs.add_parser("run", add_help=False, help="Run any script in doqs/scripts/ by name")
    subs.add_parser("list", help="Print every command")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        build_parser().print_help()
        print("\nRun 'doqs list' to see what each command runs.")
        return 0

    command, rest = argv[0], argv[1:]
    if command in PASSTHROUGH:
        return cmd_passthrough(command, rest)
    if command == "run":
        return cmd_run(rest)
    if command == "list":
        return cmd_list()

    args = build_parser().parse_args(argv)
    if command == "check":
        return cmd_check(args)
    if command == "generate":
        return cmd_generate(args)
    if command == "setup":
        return cmd_setup(args)

    build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
