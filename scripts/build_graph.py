"""Renamed to resolve_graph.py. This stub is removed after 2026-12-16.

Exits 2 rather than 0 on purpose. A stub that quietly succeeded is how a
repository stops running a gate, or stops regenerating a file, and nobody
notices for months.

See doqs/docs/migration-2026-09.md.
"""
import sys

print(
    "build_graph.py is now resolve_graph.py.\n"
    "Use: python doqs/doqs.py generate\n"
    "Or call the script directly: python doqs/scripts/resolve_graph.py",
    file=sys.stderr,
)
raise SystemExit(2)
