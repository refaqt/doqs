# ADR — SysON as a local session over git SysML files

- **Date:** 2026-09-01
- **Status:** Accepted

## Context

DOQS machine repos store requirements and architecture as textual SysML v2 in
`architecture/*.sysml` so they stay diffable in git. Eclipse SysON is the
graphical editor contributors want, but it is a Sirius Web application: the
live model lives in PostgreSQL, `.sysml` is an import/export format, and the
documented local install is Docker. Homepage **Download** writes a JSON zip
(models + diagram layouts), not SysML text.

Turning SysON into a file-based desktop app would mean changing its
persistence. Contributors should not have to install Java, Node, Maven, or
build SysON from source.

## Decision

1. Keep `architecture/*.sysml` as the canonical model in git.
2. Ship a DOQS launcher (`scripts/syson.py` + `tools/syson/docker-compose.yml`)
   that runs the published SysON Docker image with a **persistent Postgres
   volume**, creates a SysON project named from `okh.toml`, and imports those
   files through SysON’s documented GraphQL/REST APIs.
3. `save` exports textual SysML back over the same files. Diagrams stay in the
   local Docker volume. `reload` re-imports from git and drops diagrams.
4. Docker Desktop is a one-time human install. Everything after that is the
   script. No extra Python dependencies (stdlib `urllib` only).
5. Do not vendor SysON into `doqs/` or treat the JSON project zip as git
   source of truth.

## Consequences

- Contributors install Docker Desktop once, then double-click `syson.bat`
  (or `python doqs/scripts/syson.py ui`) at the machine repo root.
- Round-trip fidelity depends on SysON’s textual importer/exporter; incomplete
  constructs may change on `save`. Review `git diff`.
- Diagram layouts are per-machine, not shared, unless someone separately
  commits SVGs or a SysON zip as a backup.
- The compose file pins `eclipsesyson/syson:v2026.7.0`; bump it in doqs when
  adopting a new SysON release.

## Related

- [docs/syson.md](../syson.md)
- SysON textual import/export:
  https://doc.mbse-syson.org/syson/v2026.7.0/user-manual/features/import-export-textual.html
