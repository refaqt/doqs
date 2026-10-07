"""One report shape for every command that changes a repository.

A command that adds a part, a module or an interface says what it wrote,
what it changed, what it left alone, and what a person must do next. The
same report prints as text for a person and as JSON (``--json``) for a tool
such as fabriq, which turns it into a commit message and a pull request.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Report:
    command: str
    root: str = ""
    written: list[str] = field(default_factory=list)
    edited: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    facts: dict = field(default_factory=dict)
    dry_run: bool = False

    def rel(self, path: Path) -> str:
        """A path as the report prints it: relative to the root when possible."""
        try:
            return Path(path).resolve().relative_to(Path(self.root).resolve()).as_posix()
        except (ValueError, OSError):
            return Path(path).as_posix()

    def wrote(self, path: Path) -> None:
        self.written.append(self.rel(path))

    def changed(self, path: Path) -> None:
        self.edited.append(self.rel(path))

    def kept(self, path: Path, why: str = "") -> None:
        self.unchanged.append(self.rel(path) + (f" ({why})" if why else ""))

    def warn(self, text: str) -> None:
        self.warnings.append(text)

    def fail(self, text: str) -> None:
        self.errors.append(text)

    def then(self, text: str) -> None:
        self.next_steps.append(text)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_json(self) -> str:
        data = {
            "command": self.command, "root": self.root, "ok": self.ok, "dry_run": self.dry_run,
            "written": self.written, "edited": self.edited, "unchanged": self.unchanged,
            "warnings": self.warnings, "errors": self.errors, "next_steps": self.next_steps,
            "facts": self.facts,
        }
        return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)

    def text(self) -> str:
        lines = []
        head = f"{self.command}" + (" (dry run: nothing written)" if self.dry_run else "")
        lines.append(head)
        for label, items in (("wrote", self.written), ("edited", self.edited),
                             ("kept", self.unchanged)):
            for item in items:
                lines.append(f"  {label:<6} {item}")
        for item in self.warnings:
            lines.append(f"WARN  {item}")
        for item in self.errors:
            lines.append(f"FAIL  {item}")
        if self.next_steps:
            lines.append("next:")
            for item in self.next_steps:
                lines.append(f"  - {item}")
        lines.append("ok    done" if self.ok else "FAILED")
        return "\n".join(lines)

    def emit(self, as_json: bool) -> int:
        """Print the report and return the exit code: 0 when ok, 1 otherwise."""
        print(self.to_json() if as_json else self.text(), file=sys.stdout)
        sys.stdout.flush()
        return 0 if self.ok else 1
