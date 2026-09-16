#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The one doqs command. Run it from your machine repository root:

    python doqs/doqs.py check

`doqs.sh` and `doqs.bat` in your repository root do the same thing.
The commands themselves live in `scripts/cli.py`.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from cli import main  # noqa: E402


def run() -> int:
    """Run the command, and stay quiet when the reader stops reading.

    `doqs list | head` closes stdout early. Without this, Python prints a
    BrokenPipeError traceback over the output the person asked for.
    """
    try:
        code = main()
        sys.stdout.flush()
        return code
    except BrokenPipeError:
        # Send the rest of our output to nowhere, so the interpreter's own
        # flush at exit cannot raise the same error again.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(run())
