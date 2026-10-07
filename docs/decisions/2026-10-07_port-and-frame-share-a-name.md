# ADR-015 — A port and a mounting frame share one name

- **Date:** 2026-10-07
- **Status:** Accepted

Write this file in B2 English. Follow `.agents/rules/communication.md`. Keep official names, file paths, and numbers exact.

## Context

An interface between two parts is written three times. SysML holds a `port def` and a port
on each part ([Interfaces](../architecture.md#interfaces)). Each part's FreeCAD file holds a
mounting frame that an assembly joint attaches to ([ADR-013](2026-10-06_joints-attach-to-frames.md)).
When the interface faces outside the module, `okh.toml` lists it too.

Nothing tied the three together. In the compact stage, the port `referenceRailMount` on the
base matched the frame `IF_rail_reference` by meaning only. A person had to remember all
three names, and no check could say that a port had no frame, or that a frame had no port.
That is one reason a new part took days: every name was a decision, and every decision
could be wrong.

The tools planned for fabriq must create all three from one request, and the validators must
compare them. That needs one rule, not three names.

## Decision

- A port `fooBar` on a part means the frame `IF_foo_bar` in that part's file: the port name
  in lowercase with underscores, after `IF_`. The rule works both ways.
- An interface `RailMount` at major version 1 is the SysML `port def RailMountInterface_v1`
  and the OKH entry `name = "RailMountInterface"`, `version = "1.0"`. Only the major version
  must match between the two.
- The helpers in `scripts/interface_rules.py` are the one place the rule lives. A tool that
  adds an interface writes all three names through them. A validator reads all three and
  reports a name that does not fit.
- The existing frames `IF_rail_reference` and `IF_rail_second` in the aqtuator base are
  renamed once to `IF_reference_rail_mount` and `IF_second_rail_mount`, which their ports
  already say. The module is below version 1.0, so no major version is needed.

## Consequences

- A designer chooses a port name once. The frame label and the OKH entry follow.
- A port with a frame that does not fit, or a frame with no port, becomes a finding of the
  interface validator. It warns first and fails only with a strict flag, so no consumer's
  CI goes red on a pin bump.
- Frame labels get longer than the hand-written ones. That is the price of one rule.
