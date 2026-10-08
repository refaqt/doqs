# Decisions

Why a choice was made, and what it rules out. One file per decision:
`YYYY-MM-DD_topic.md`. **Read these before larger work, and say which ones apply.**
Write entries in B2 English. Follow `.agents/rules/communication.md`.

A decision record is not a guide. It states the problem, the choice, and what
follows from it. The guide that explains how to use the result lives in `docs/`.

| Date | Decision | Status |
| ---- | -------- | ------ |
| 2026-06-04 | [ADR-001 — Naming and versioning conventions](2026-06-04_naming-and-versioning.md) | Accepted |
| 2026-06-24 | [ADR-002 — Master sketches live in a separate Body](2026-06-24_freecad-master-sketches-body.md) | Accepted |
| 2026-09-01 | [Root launchers installed by setup-tooling](2026-09-01_root-launcher-install.md) | Accepted |
| 2026-09-01 | [SysON as a local session over git SysML files](2026-09-01_syson-session-adapter.md) | Accepted |
| 2026-09-15 | [ADR-003 — Product families: parameters, compositions, and instance modules](2026-09-15_product-family-variants.md) | Accepted |
| 2026-09-16 | [A session hook downloads the shared agent kit](2026-09-16_agent-kit-session-hook.md) | Accepted |
| 2026-09-16 | [CAD tools live in doqs, not as per-module copies](2026-09-16_cad-tools-in-doqs.md) | Accepted |
| 2026-09-16 | [What `export_variant.py` promises](2026-09-16_export-variant-contract.md) | Accepted |
| 2026-09-18 | [ADR-004 — A shared library for parts we buy](2026-09-18_parts-library.md) | Accepted |
| 2026-09-18 | [ADR-005 — Role modules: a stable name for a changing part](2026-09-18_role-modules.md) | Accepted |
| 2026-09-18 | [ADR-006 — Money leaves the bill of materials](2026-09-18_money-out-of-the-bom.md) | Accepted |
| 2026-09-18 | [ADR-007 — A build record you can open](2026-09-18_build-records.md) | Accepted |
| 2026-09-22 | [The session hook finds its own repository](2026-09-22_hook-finds-its-own-root.md) | Accepted |
| 2026-09-29 | [ADR-008 — A private parts library](2026-09-29_private-parts-library.md) | Accepted |
| 2026-09-29 | [ADR-009 — A fixed method for taking in a supplier's files](2026-09-29_component-intake.md) | Accepted |
| 2026-10-01 | [ADR-010 — A part has a Part container on top, not a Body](2026-10-01_part-container-on-top.md) | Accepted |
| 2026-10-02 | [ADR-011 — An own model in a parts library is our design, and is checked like one](2026-10-02_own-models-are-our-designs.md) | Accepted |
| 2026-10-06 | [ADR-012 — Every dimension has a reason, and the model links to it](2026-10-06_every-dimension-has-a-source.md) | Accepted |
| 2026-10-06 | [ADR-013 — Assembly joints attach to named mounting frames](2026-10-06_joints-attach-to-frames.md) | Accepted |
| 2026-10-07 | [ADR-014 — An imported solid and a mounting frame open visible](2026-10-07_imported-solids-and-frames-visible.md) | Accepted |
| 2026-10-07 | [ADR-015 — A port and a mounting frame share one name](2026-10-07_port-and-frame-share-a-name.md) | Accepted |
| 2026-10-07 | [ADR-016 — Two new script verbs: `add_` and `use_`](2026-10-07_add-and-use-verbs.md) | Accepted |
| 2026-10-07 | [ADR-017 — A STEP file is imported in the FreeCAD window, never headless](2026-10-07_step-import-in-the-gui.md) | Accepted |
| 2026-10-07 | [ADR-018 — A new check warns first](2026-10-07_new-checks-warn-first.md) | Accepted |
| 2026-10-08 | [ADR-019 — The agent saves open FreeCAD documents before a pull request](2026-10-08_agent-saves-before-a-pull-request.md) | Accepted |
