# ADR-007 — A build record you can open

- **Date:** 2026-09-18
- **Status:** Accepted
- **Extends:** [ADR-001 naming and versioning](2026-06-04_naming-and-versioning.md)

## Context

`builds/<id>/build.toml` records one physical machine: which version of every
module went into it. The specification gives it three jobs — reproducibility,
support, and validation — and it does the third well.

It does not do the first two, and nobody had noticed because nobody had tried.

An entry names a path and a version tag:

```toml
[[module]]
path    = "modules/x-axis"
version = "v1.2.1"
```

Three things are missing from that.

**A tag is not a pin.** It can be moved to a different commit or deleted
outright, and nothing in the record would change. The record would still read
`v1.2.1` and would now describe something else, or nothing.

**There is no address.** Only `[base]` says which repository it came from. For
an extracted module you have to work it out from the `.gitmodules` of the base
repository at that version — which you can only read once you have fetched it.

**There is no command.** "Anyone can rebuild this exact machine by checking out
the pinned versions" was true only for somebody willing to do it by hand, for
every module, having first worked out where each one lives.

A machine in a workshop outlives several versions of its design. The record is
what somebody reaches for years later, usually because something broke. That is
the worst moment to discover the record is a reference rather than a record.

## Decision

### 1. Pin the commit, and say where it came from

Every entry, including `[base]`, names three things:

```toml
[[module]]
path    = "modules/x-axis"
repo    = "https://github.com/refaqt/x-axis"
version = "v1.2.1"
commit  = "9f2c1ab4e7d05c8b3a6f1e2d4c7b8a9f0e1d2c3b"
```

`version` stays, because a person reads it. `commit` is what makes the record
true: it cannot be moved and it cannot be pointed somewhere else.

### 2. Check it

`validate_build.py` gains three checks: `repo` is present, `version` is a
well-formed tag, and `commit` is a full forty-character identifier. A short
identifier is refused because it can become ambiguous as a repository grows.

This finally uses `GIT_TAG` in `scripts/naming_rules.py`, which had been defined
and used by nothing since the naming decision.

### 3. Give the files back

`restore_build.py` reads a record and fetches every pinned repository at its
exact commit:

```bash
python doqs/doqs.py restore-build builds/serial-0042 --out /tmp/serial-0042
python doqs/doqs.py restore-build builds/serial-0042 --check
```

`--check` is the valuable half. It asks whether every commit is still reachable
and fetches nothing, so a record that has gone unreachable is discovered while
somebody can still act — rather than on the day a customer needs the drawing.

### 4. "Gone" and "could not ask" are different answers

A commit that has been removed needs somebody to act. A server that could not be
reached needs a network. Reporting the second as the first sends people hunting
through a history that is perfectly intact.

`--check` therefore exits `1` when a commit is gone and `2` when a repository
could not be reached. A check that goes red whenever the network hiccups is a
check people learn to ignore.

### 5. No stored copy of the files

Deliberately not in this decision. A stored archive per build would answer the
case where a repository disappears entirely, and it costs storage and a place to
put large files.

The manifest pattern this project already uses for measurement data and supplier
files is the right shape for it if the need appears. Until then, `--check` turns
"the record might be unopenable" into something you find out on a schedule.

## Consequences

- Every existing `build.toml` must gain `repo` and `commit` per entry.
  Validation names what is missing and why a tag alone is not enough.
- A record can be opened years later with one command, by somebody who was not
  there when the machine was built.
- CI can answer "are all our build records still openable?" — a question that
  could not previously be asked at all.
- `restore-build` needs a network, so it is **not** one of the gates.
  `validate_all.py` still runs seven and no more, and a repository can bump its
  doqs pin without its CI suddenly needing to reach every module's host.
- `restore_` joins the script naming contract as a seventh verb.

## Alternatives rejected

| Alternative | Why not |
| --- | --- |
| Keep pinning tags only | A tag can be moved or deleted, so the record can quietly become false while looking unchanged. |
| Record a short commit identifier | Unambiguous today, ambiguous once the repository grows. The full identifier costs nothing. |
| Resolve the repository from `.gitmodules` instead of recording it | You can only read that file after fetching the base repository, which you can only do if you know where it is. |
| Add `--check` to the gates | It needs a network. Every machine repository's CI would then depend on every module host being up. |
| Fail `--check` on a network error | A check that goes red whenever the network hiccups gets ignored, and then it protects nothing. |
| Store an archive of every build | Real, but a different problem with a storage cost. Recorded above so it can be picked up deliberately. |
