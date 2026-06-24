# ADR-002 — Master sketches live in a separate Body

- **Date:** 2026-06-24
- **Status:** Accepted

## Context

In FreeCAD 1.1 (built-in Assembly workbench), a part file with a `SubShapeBinder` referencing master sketches in an assembly document may fail to appear in the Assembly **Insert** panel — even when the part is correctly wrapped in an `App::Part` container and both files are saved.

The failure is easy to misdiagnose. Common red herrings include:

- The part not being in a `Part` container (it was).
- Unsaved changes on the part document.
- Master sketches living in a `Group` at document root rather than inside the `Assembly` object (organizational grouping alone does not fix the problem).

The actual mechanism is a **circular document dependency created at insertion time**:

1. The part's Binder links *into* the assembly file (part → assembly document).
2. Inserting the part adds a link from the assembly *to* the part (assembly → part).
3. FreeCAD detects the cycle (assembly → part → assembly) and refuses to insert.

This surfaced on the spindle-clamp module: `spindle-clamp-jaw.FCStd` bound to master sketches in `spindle-clamp.FCStd`. Deleting the Binder made the part insertable, confirming the cycle as root cause.

A further subtlety: the master sketches were constrained to the **Assembly object's origin planes**. `Assembly::AssemblyObject` owns its own origin; sketches tied to those planes create an object-level dependency on the Assembly, not merely on the document. A Binder in a child part that pulls those sketches therefore transitively depends on the Assembly object — the same object the workbench must link when composing the assembly.

## Decision

When using top-down design with master sketches in an assembly `.FCStd` file, **place the master sketches in a dedicated `PartDesign::Body`** (e.g. `Body_master`) inside a `Group` such as `Master sketches`. Sketches in that Body reference **the Body's origin planes**, never the Assembly object's origin planes.

Target document tree:

```
spindle-clamp.FCStd
├── Assembly                    ← joints and inserted part links only
├── Master sketches (Group)
│   └── Body_master             ← master sketches live here
│       ├── Origin              ← sketches constrain to these planes
│       ├── Sketch (Master)
│       └── Sketch001
└── (parameter spreadsheet link, etc.)
```

Child parts consume master geometry via `SubShapeBinder` pointing at sketches **inside `Body_master`**, not at the Assembly or at sketches constrained to Assembly origins.

**Rules:**

1. Master sketches for assembly-driven parts **must** live in a Body with its own origin.
2. Do **not** constrain master sketches to `Assembly` origin planes.
3. Do **not** place master sketches as loose objects at document root if they will be Binder-referenced by parts that the assembly inserts.
4. The assembly file inserts **parts**; parts link **down** to master-sketch geometry in the assembly document's Body — never the reverse (parts must not be referenced by objects the assembly itself depends on for layout).

For numeric-only driving dimensions, prefer the existing `params.csv` → Spreadsheet flow ([architecture.md](../architecture.md#linking-csv-parameters-to-freecad)) over geometric Binders where possible.

## Consequences

- Assembly `.FCStd` files that drive child parts top-down need a `Body_master` (or equivalent) as a standard structural element, not ad-hoc root-level sketches.
- When a part fails to appear in Insert, inspect **external links and Binders** in the part file before restructuring containers. A Binder back to the assembly document is the first thing to check.
- If master sketches must not live in the assembly file at all (e.g. shared across multiple assemblies), extract them to a dedicated skeleton document that both the assembly and parts link into — dependency flows one direction only. See [architecture.md — Top-down design](../architecture.md#top-down-design-and-master-sketches).
- Copy-paste migration of a Body between files breaks external links; fixing the Binder target or recreating the Body in place is safer than moving geometry across documents when assembly links already exist.
