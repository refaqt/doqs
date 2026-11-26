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
import datetime
import re
import subprocess
import sys
from pathlib import Path

from license_rules import is_doqs_tools_repo
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

#: Checks that only warn until a repository opts in with a strict flag, so a
#: machine's CI stays green when its doqs pin moves. `doqs check` runs them
#: after the staleness checks; `validate_all.py` does not.
ADVISORY: tuple[Step, ...] = (
    ("validate_interfaces.py", ()),
)

#: Commands that pass every remaining argument straight to one script.
PASSTHROUGH: dict[str, str] = {
    "syson": "syson.py",
    "export": "export_variant.py",
    "bom": "resolve_bom.py",
    "restore-build": "restore_build.py",
    "restore-private": "restore_private.py",
    "unshare": "apply_unshare.py",
    "compare-own": "compare_own.py",
    "scaffold": "install_module.py",
    "add-part": "add_part.py",
    "wrap": "export_wrapper.py",
    "freecad": "freecad_session.py",
    "use-part": "use_part.py",
    "add-interface": "add_interface.py",
    "mirror": "validate_mirror.py",
}

#: Scripts that cannot become a subcommand: they run inside a FreeCAD
#: interpreter, which this process cannot reach. `list` prints them so nobody
#: goes looking for a subcommand that can never exist.
FREECAD_ONLY: tuple[tuple[str, str], ...] = (
    ("cad_sync_params.py", 'exec(open("doqs/scripts/cad_sync_params.py").read()) in the FreeCAD console'),
    ("cad_fingerprint.py", "called for you by build_model.py; write() inside FreeCAD"),
    ("cad_build.py", "imported by a module's cad/build_model.py"),
)


#: Scripts of the shared agent kit, under `.agents/scripts/` in the repository
#: root. An older kit does not have them yet, so every caller skips a missing one.
KIT_SCRIPTS = Path(".agents") / "scripts"

#: Kit checks that `doqs check` runs last. They only warn: a machine's CI must
#: not go red because the shared kit moved. A kit without the script, or a
#: repository without the file the check needs, skips the step without a word.
KIT_ADVISORY: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    # (script, arguments, file the check needs, the command that fixes it)
    ("mistakes_index.py", ("--check",), "docs/mistakes/README.md", "doqs mistakes"),
    ("sync_root.py", ("--check",), ".agents-local/profile.toml", "doqs setup"),
)

#: The file that proves each tooling folder is filled, not only present.
MARKERS: dict[str, str] = {
    ".agents": ".agents/rules/core.md",
    "doqs": "doqs/scripts/validate_all.py",
}


def repo_root(explicit: Path | None = None) -> Path:
    """The repository the command works on.

    `--root` wins. Otherwise it is the machine repository that mounts this
    doqs folder, or this doqs folder itself when it is a clone of its own.
    """
    if explicit is not None:
        return explicit.resolve()
    doqs_root = SCRIPTS_DIR.parent
    if (doqs_root.parent / ".git").exists():
        return doqs_root.parent
    return doqs_root


def update_command(root: Path) -> str:
    """The command that fills or updates the tooling folders in `root`."""
    if is_doqs_tools_repo(root):
        return "git submodule update --init --remote --checkout .agents"
    return "bash setup-tooling.sh"


def kit_script(root: Path, name: str) -> Path | None:
    """A script of the shared agent kit, or None when this kit has none."""
    path = root / KIT_SCRIPTS / name
    return path if path.is_file() else None


def run_kit(root: Path, name: str, args: list[str]) -> int:
    """Run one kit script with `--root`, or print one hint line and return 0."""
    script = kit_script(root, name)
    if script is None:
        print(f"skip  {KIT_SCRIPTS.as_posix()}/{name} is missing: the shared kit is empty or older. "
              f"Update it with: {update_command(root)}")
        return 0
    return subprocess.run([sys.executable, str(script), "--root", str(root), *args], cwd=root).returncode


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
    if args.strict_parametric:
        extra["validate_variants.py"] = ["--strict-parametric"]
        extra["validate_cad.py"] = ["--strict-parametric"]
    if args.strict_interfaces:
        extra["validate_interfaces.py"] = ["--strict-interfaces"]

    steps = GATES + STALENESS + ADVISORY
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
    failed = run_steps(steps, args.root, extra)
    if not args.only:
        run_kit_advisory(repo_root(args.root))
    return report(failed, "all gates passed")


def run_kit_advisory(root: Path) -> None:
    """Run the kit's own checks. They warn and never fail `doqs check`."""
    for name, fixed, needs, fix in KIT_ADVISORY:
        script = kit_script(root, name)
        if script is None or not (root / needs).is_file():
            continue
        print(f"--- {KIT_SCRIPTS.as_posix()}/{name} {' '.join(fixed)} (advisory) ---")
        cmd = [sys.executable, str(script), "--root", str(root), *fixed]
        if subprocess.run(cmd, cwd=root).returncode != 0:
            print(f"WARN  {name} found drift. This does not fail the check. Fix it with: {fix}")


def cmd_generate(args: argparse.Namespace) -> int:
    failed = run_steps(GENERATE, args.root)
    if not failed:
        print("      Review what changed with 'git diff' before you commit it.")
    return report(failed, "everything regenerated")


def cmd_setup(args: argparse.Namespace) -> int:
    return report(run_steps((("install_root_tools.py", ()),), args.root), "root tools installed")


def submodule_state(root: Path, name: str) -> str:
    """The short commit of a filled tooling folder, and where it sits against its pin."""
    def git(*args: str, cwd: Path) -> str | None:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
        return done.stdout.strip() if done.returncode == 0 else None

    folder = root / name
    head = git("rev-parse", "HEAD", cwd=folder)
    if not head:
        return "no git history here"
    short = head[:7]
    listing = git("ls-tree", "HEAD", "--", name, cwd=root) or ""
    parts = listing.split()
    pin = parts[2] if len(parts) >= 3 and parts[1] == "commit" else None
    if pin is None:
        return f"{short}, no pin recorded"
    if pin == head:
        return f"{short}, at its pin"
    ahead = git("rev-list", "--count", f"{pin}..HEAD", cwd=folder)
    if ahead and ahead != "0":
        return f"{short}, {ahead} commits ahead of its pin {pin[:7]}"
    return f"{short}, not at its pin {pin[:7]}"


def cmd_doctor(args: argparse.Namespace) -> int:
    """Are the tooling folders filled? Say exactly what to run when they are not."""
    root = repo_root(args.root)
    folders = (".agents",) if is_doqs_tools_repo(root) else (".agents", "doqs")
    fix = update_command(root)
    empty = []
    for name in folders:
        marker = MARKERS[name]
        if (root / marker).is_file():
            print(f"ok    {name:<8} {submodule_state(root, name)}")
        else:
            print(f"FAIL  {name:<8} is empty: {marker} is missing")
            empty.append(name)
    if empty:
        print(f"Run this in {root}, then run 'doqs doctor' again:")
        print(f"  {fix}")
        return 1
    print("ok    the tooling folders are filled")
    return 0


def cmd_pre_pr(args: argparse.Namespace) -> int:
    """Everything to do before a pull request, in order. Stops at the first failure."""
    root = repo_root(args.root)
    root_args = ["--root", str(args.root)] if args.root else []

    print("=== 1/4 save the open FreeCAD documents and rebuild them headless ===")
    if save_and_rebuild(root) != 0:
        print("\nSTOP  the FreeCAD step failed. Fix it, then run 'doqs pre-pr' again.")
        return 1
    print("\n=== 2/4 doqs generate ===")
    if cmd_generate(build_parser().parse_args(["generate", *root_args])) != 0:
        print("\nSTOP  'doqs generate' failed. Fix the error above, then run 'doqs pre-pr' again.")
        return 1
    print("\n=== 3/4 doqs check ===")
    if cmd_check(build_parser().parse_args(["check", *root_args])) != 0:
        print("\nSTOP  'doqs check' failed. Fix the error above, then run 'doqs pre-pr' again.")
        return 1
    print("\n=== 4/4 git status --short ===")
    subprocess.run(["git", "status", "--short"], cwd=root)
    print("\nok    ready for a pull request. Read 'git diff' before you commit.")
    return 0


def save_and_rebuild(root: Path) -> int:
    """Save the documents the open FreeCAD changed, then rebuild each one headless.

    Git only sees what is on disk, so an unsaved change never reaches a pull
    request. A save in the window changes the file, so its fingerprint no
    longer matches; the headless rebuild writes both again. This is the
    routine in docs/agent-cad.md, "Working with a file open".
    """
    import freecad_rules
    import freecad_session

    if not freecad_rules.rpc_available():
        if freecad_session.gui_running():
            print(f"FAIL  {freecad_session.ASK_USER}")
            print("      Or close FreeCAD, if it holds no work for this repository.")
            return 1
        print("skip  no FreeCAD window runs, so there is nothing to save")
        return 0
    result = freecad_session.save_documents(root=root)
    if result is None:
        print("FAIL  FreeCAD did not say what it saved. Save in FreeCAD yourself.")
        return 1
    if not freecad_session.print_saved(result):
        return 1
    saved = [Path(path) for path in result.get("saved", [])]
    if not saved:
        return 0
    binary = freecad_rules.find_freecad(gui=False)
    for fcstd in saved:
        script = fcstd.parent / "build_model.py"
        if not script.is_file():
            print(f"WARN  {fcstd.name} has no build_model.py beside it, so it was not rebuilt")
            continue
        if binary is None:
            print(f"FAIL  FreeCADCmd was not found. Rebuild by hand: FreeCADCmd {script}")
            return 1
        done = subprocess.run([binary, str(script)], cwd=root, capture_output=True, text=True)
        output = (done.stdout or "") + (done.stderr or "")
        if "Rebuilt and saved" not in output:
            print(f"FAIL  the headless rebuild of {script} built nothing. It said:")
            for line in output.strip().splitlines()[-8:]:
                print(f"      {line}")
            return 1
        print(f"rebuilt    {fcstd} (headless, fingerprint written)")
    print("      The FreeCAD window still holds the copy from before the rebuild.")
    print("      Close and open those documents again before you change them.")
    return 0


#: A log slug: lower-case words joined by hyphens.
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

LOG_TEMPLATE = """# {date} — {title}

**Role(s):** {roles}

## What changed

Two to four sentences. The result, in plain words.

## Why it matters

The problem this solves, in the reader's terms: time lost, risk, cost, confusion.

## What you need to do

What changes for the people who use the project. "Nothing" is a good answer.

## How it was checked

What you ran and what passed. Say clearly if something is untested, and why.

<details>
<summary>Technical notes</summary>

File names, commands, trade-offs. Delete this block if there is nothing to add.

</details>
"""


def cmd_log(args: argparse.Namespace) -> int:
    """`doqs log new <slug>`: start a log entry and add it to the index."""
    if not SLUG.match(args.slug):
        print(f"error: {args.slug!r} is not a slug. Use lower-case words joined by hyphens.",
              file=sys.stderr)
        return 2
    root = repo_root(args.root)
    date = args.date or datetime.date.today().isoformat()
    title = args.title or args.slug.replace("-", " ").capitalize()
    log_dir = root / "docs" / "log"
    entry = log_dir / f"{date}_{args.slug}.md"
    if entry.exists():
        print(f"error: {entry.relative_to(root).as_posix()} already exists. "
              "Pick another slug, or edit that file.", file=sys.stderr)
        return 1
    log_dir.mkdir(parents=True, exist_ok=True)
    entry.write_text(LOG_TEMPLATE.format(date=date, title=title, roles=args.roles), encoding="utf-8")
    print(f"created {entry.relative_to(root).as_posix()}")
    index = log_dir / "README.md"
    if add_index_row(index, date, title, entry.name, args.roles):
        print(f"updated {index.relative_to(root).as_posix()}")
    return 0


def add_index_row(index: Path, date: str, title: str, file_name: str, roles: str) -> bool:
    """Add a row for a new entry at the end of the first table in `index`.

    The cells follow the table's own header. False when there is no table.
    """
    if not index.is_file():
        return False
    lines = index.read_text(encoding="utf-8").splitlines()
    rule = next((i for i, line in enumerate(lines)
                 if i > 0 and lines[i - 1].startswith("|") and re.match(r"^\|[\s:|-]+\|\s*$", line)), None)
    if rule is None:
        return False
    end = rule + 1
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    header = [cell.strip().lower() for cell in lines[rule - 1].strip().strip("|").split("|")]
    cells = []
    for name in header:
        if name == "date":
            cells.append(date)
        elif name == "role(s)":
            cells.append(roles)
        elif name == "images":
            cells.append("0")
        elif name in ("topic", "entry", "title"):
            cells.append(f"[{title}]({file_name})")
        else:
            cells.append("")
    lines.insert(end, "| " + " | ".join(cells) + " |")
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def cmd_mistakes(args: argparse.Namespace) -> int:
    return run_kit(repo_root(args.root), "mistakes_index.py", ["--check"] if args.check else [])


def cmd_context(args: argparse.Namespace) -> int:
    extra = ["--budget", str(args.budget)] if args.budget is not None else []
    return run_kit(repo_root(args.root), "context_budget.py", extra)


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
        ("doctor", "Are the tooling folders filled? Says what to run if not"),
        ("pre-pr", "Save FreeCAD work, rebuild, generate, check, git status"),
        ("log new <slug>", "Start a log entry in docs/log/ and add it to the index"),
        ("mistakes", "Rebuild the index of docs/mistakes/ (--check: only compare)"),
        ("context", "How many bytes an agent reads at session start"),
        ("syson …", "Open or save architecture/*.sysml in SysON"),
        ("export …", "Export geometry for one composition and model"),
        ("bom …", "Resolve one module's BOM for one model"),
        ("restore-build …", "Fetch back the files a machine was built from"),
        ("restore-private …", "Copy non-shared supplier files from the private library"),
        ("unshare …", "Take files we may not share any more out of git, keep them on disk"),
        ("compare-own …", "Compare an own model with the brand's, writing only results"),
        ("scaffold …", "Create a module, an own part, a library brand or a family"),
        ("add-part …", "Take a supplier's part into the private and public libraries"),
        ("wrap …", "Build a library part's FreeCAD wrapper from its STEP, with colours and frames"),
        ("use-part …", "Put a library part into a machine module: BOM row, manifest, SysML"),
        ("add-interface …", "Add one interface: SysML port def and ports, okh entry, frames"),
        ("mirror …", "Compare the public and private libraries file by file"),
        ("freecad …", "Check, start or save in FreeCAD; say if headless or MCP is safe"),
        ("run <script> …", "Any script in doqs/scripts/, by name"),
        ("list", "This list"),
    )
    for name, purpose in rows:
        print(f"  {name:<16} {purpose}")

    print("\n'check' runs, in order:")
    for name, fixed in GATES + STALENESS + ADVISORY:
        print(f"  {name} {' '.join(fixed)}".rstrip())
    for name, fixed, _needs, _fix in KIT_ADVISORY:
        print(f"  {KIT_SCRIPTS.as_posix()}/{name} {' '.join(fixed)}  (warns only; skipped if missing)")

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
    check.add_argument("--strict-parametric", action="store_true",
                       help="Fail on a parameter with no source, a free sketch or a typed size")
    check.add_argument("--strict-interfaces", action="store_true",
                       help="Fail when SysML ports, okh.toml entries and FreeCAD frames disagree")

    generate = subs.add_parser("generate", help="Write every generated file")
    generate.add_argument("--root", type=Path, default=None, help="Machine repo root")

    setup = subs.add_parser("setup", help="Install root launchers and agent config")
    setup.add_argument("--root", type=Path, default=None, help="Machine repo root")

    doctor = subs.add_parser("doctor", help="Check that the tooling folders are filled")
    doctor.add_argument("--root", type=Path, default=None, help="Machine repo root")

    pre_pr = subs.add_parser("pre-pr", help="Save, rebuild, generate and check before a pull request")
    pre_pr.add_argument("--root", type=Path, default=None, help="Machine repo root")

    log = subs.add_parser("log", help="Work with docs/log/")
    log_subs = log.add_subparsers(dest="log_command", required=True)
    log_new = log_subs.add_parser("new", help="Start a log entry and add it to the index")
    log_new.add_argument("slug", help="Short name, for example lean-agent-context")
    log_new.add_argument("--title", default=None, help="The heading (default: from the slug)")
    log_new.add_argument("--roles", default="software", help="The Role(s) line (default: software)")
    log_new.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    log_new.add_argument("--root", type=Path, default=None, help="Machine repo root")

    mistakes = subs.add_parser("mistakes", help="Rebuild the docs/mistakes/ index (kit script)")
    mistakes.add_argument("--check", action="store_true", help="Only say if the index is stale")
    mistakes.add_argument("--root", type=Path, default=None, help="Machine repo root")

    context = subs.add_parser("context", help="Bytes an agent reads at session start (kit script)")
    context.add_argument("--budget", type=int, default=None, help="Fail above this many bytes")
    context.add_argument("--root", type=Path, default=None, help="Machine repo root")

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
    if command == "doctor":
        return cmd_doctor(args)
    if command == "pre-pr":
        return cmd_pre_pr(args)
    if command == "log":
        return cmd_log(args)
    if command == "mistakes":
        return cmd_mistakes(args)
    if command == "context":
        return cmd_context(args)

    build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
