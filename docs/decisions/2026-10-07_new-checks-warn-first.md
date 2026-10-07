# ADR-018 — A new check warns first, and a machine opts in to failing

- **Date:** 2026-10-07
- **Status:** Accepted

Write this file in B2 English. Follow `.agents/rules/communication.md`. Keep official names, file paths, and numbers exact.

## Context

Four times in two weeks a change to a doqs check forced a repair pull request in a machine
or a library: the Part container rule, the own-model file names, the linked-dimension
findings, the joint findings. Each time the doqs pin moved, CI went red for a reason the
person bumping the pin had not caused. A pin bump should be boring.

`validate_all.py` already promises to run exactly seven gates, so a repository that uses it
never sees a new gate. `doqs check` had no such promise.

## Decision

- A new check joins `doqs check` as an **advisory** step (`cli.ADVISORY`). It prints
  `WARN` and exits 0 until the repository passes the strict flag (`--strict-interfaces` for
  the interface check). `validate_all.py` keeps its seven gates.
- A new finding inside an existing gate follows the same pattern that joints and
  dimensions already use: a warning by default, a failure with `--strict-parametric`.
  The frame findings in `validate_cad.py` follow it.
- A check that must fail from day one, because it protects data (the checksum of a
  supplier file, the save guard), says so in its decision record.

## Consequences

- A machine bumps its doqs pin, reads the new warnings, fixes them in its own time, and
  then turns the flag on in its CI.
- The strict flags are the place where a repository records which rules it holds itself
  to. aqtuator and stoq can turn `--strict-interfaces` on once their frames follow the
  naming rule.
