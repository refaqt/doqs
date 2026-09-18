# ADR-005 — Role modules: a stable name for a changing part

- **Date:** 2026-09-18
- **Status:** Proposed
- **Extends:** [ADR-003 product families](2026-09-15_product-family-variants.md)
- **Works with:** [ADR-004 a shared library for parts we buy](2026-09-18_parts-library.md)

## Context

A machine has a job to fill: "the X-axis linear guide". That job carries
requirements that come down from the machine's top-level requirements. Which
brand fills it is a sourcing decision, and over the life of a machine it
changes. A HIWIN rail may become a THK rail.

Everything above that job must not move when the brand changes: the folder name,
the requirements, the interface, the identifiers in the bill of materials, and
the joints in the parent assembly.

DOQS already has the container. `docs/naming.md` says an instance module is
named after **the role in this machine, not the product bought** — `x-stage`,
never `linear-stage-500`. The rule exists and is barely used, and nothing checks
that the choice inside it still satisfies the job.

Two harder questions sat behind it.

**Where does the CAD break?** FreeCAD cannot link a `.step` file; it links to an
object inside an `.FCStd`. And when an imported solid is replaced, face and edge
names change, so a joint made directly to a supplier face breaks. That is the
topological naming problem, and it is why swapping brands normally hurts.

**What must be written down, and what must be generated?** An earlier draft had
the role commit a resolved purchase list copied from the library. That turned
out to be wrong, and understanding why produced the rule this record is really
about.

## Decision

### 1. A role module holds the job, not the product

```
machine-repo/modules/linear-guide-x/
├── okh.toml                            the role, its requirements, the part selected
├── architecture/linear-guide-x.sysml   the requirements and the interface it needs
├── cad/linear-guide-x.FCStd            reference geometry + a link to the chosen part
└── bom/bom.csv                         optional, only if the role adds something of its own
```

Every file is written by a person. Nothing is generated. The name
`linear-guide-x` never changes, and the machine assembly above it links
`linear-guide-x.FCStd` without learning which brand is inside.

### 2. Requirements live where DOQS already says they live

Formal requirements live only in SysML, in the module's `architecture/`. A role
is a module, so its `requirement def` blocks go there and trace up to the
machine-level requirements. Nothing new is needed. It has to be said clearly
because today nobody writes an `architecture/` folder for a bought part.

The role also declares the interface it needs, with the mechanism DOQS has:

```toml
[[consumes-interface]]
name    = "LinearGuide20MountInterface"
version = "1.0"
```

A library part that fits declares the matching `[[provides-interface]]`.

### 3. The selection, and what else was approved

```toml
[role]
library  = "modules/stoq"
selected = "modules/hiwin/modules/hgr-rail#HGR20R500"
approved = [
  "modules/hiwin/modules/hgr-rail#HGR20R500",
  "modules/thk/modules/shs-rail#SHS20R500",
]
```

`selected` is what you buy today. `approved` is optional and records engineering
judgement: parts checked against this role's requirements and found acceptable.
It turns "we looked at THK once and it was fine" from memory into something the
repository knows and validation can check.

### 4. Generate nothing. Check instead.

This is the part that changed after review, and the reasoning matters more than
the result.

**A library update cannot change what you buy.** The role names an exact part.
A newer library commit cannot turn `HGR20R500` into `HGR25R500`; it can only
change facts about that one part — a revised geometry file, a discontinued
status, a corrected mass. So there is nothing to copy into the machine to
protect against, and a copy would only be a duplicate that goes stale.

That gives the rule the whole design now follows:

> **Generate a file only when the value lives in someone else's repository and
> you have no other way to see it change. When the value is a human decision,
> give the person a template and check their entry.**

Five checks replace the file, and they catch more than it did:

| Check | Result |
| --- | --- |
| The selected part exists in the library | error, naming the part |
| The selected part is not discontinued | warning, naming the replacement if the row gives one |
| The selected part provides every interface the role consumes | error, naming the interface |
| Every `approved` alternative passes the same two checks | error |
| The FreeCAD document links the part the text says is selected | error, naming both |

The last one is worth more than any generated file. It catches the mistake that
actually happens — changing the selection in text and forgetting the model, or
the reverse. A generated file cannot catch it, because it is written from the
text and never looks at the CAD.

### 5. The CAD rule that makes a swap safe

The role document carries **its own reference geometry**, expressing the
requirement rather than the product: the mounting plane, the bolt pattern, the
travel line, the datum the parent needs.

- The parent machine assembly joins only to the role's reference geometry. It
  never touches an imported supplier face.
- Inside the role document, the chosen library part is placed against that same
  reference geometry, once.
- Switching brand re-places one object in one document. Everything above it is
  untouched.

This follows ADR-002, which already puts master sketches in a dedicated body so
other documents do not depend on unstable geometry.

`cad/parts/` in a machine repository stays for parts we manufacture. A role
document is an assembly of reference geometry plus a link, so it sits at
`cad/<role>.FCStd`, and no supplier geometry is ever copied into the machine.

### 6. Three kinds of change, three answers

| Case | What it means | What to do |
| --- | --- | --- |
| **Drop-in equal** | Same envelope, hole pattern and height | Not a design change. One row, an `equiv_class` tag naming the interchange group, and the buying system takes either. |
| **Different part, same role** | Mounting differs, the role still holds | Change `selected`, re-place the part against the role's datums. Nothing above the role moves. The interface check confirms it fits. |
| **Different role** | A profile rail becomes a round shaft | A real design change. The role module changes and its requirements are reviewed again. |

`equiv_class` and interfaces do not compete. `equiv_class` is a **buying**
statement about two part numbers: take either. An interface is a **design**
statement about a module: this fits here.

## Consequences

- Switching brand is one line of text plus re-placing one object in one FreeCAD
  document. The diff of `okh.toml` is the whole record of the decision.
- A role module has no generated files, so it cannot go stale and there is no
  `--check` step to forget.
- The interface check moves from build time to design time, so a part that does
  not fit fails before anyone orders it.
- Roles need `architecture/` folders, which bought parts do not have today.
  Writing the first ones is real work and it is the point: it is where the
  requirements finally get written down.
- The CAD rule depends on FreeCAD behaviour that has to be proven on real
  geometry before a project relies on it. See the open question below.

### Open question: our own families

Where the *family* picks the parts, a submodule bump really can change your
design without you choosing it. That is the case ADR-003 was written for, and
its resolved files stay for now. The asymmetry is deliberate. If our own
families also moved to explicit selection, those files could go too, and DOQS
would generate nothing at all outside the three cases listed in
[roles.md](../roles.md). That is worth deciding separately, not by accident.

### Open question: the FreeCAD spike

Build a small test with two brands of the same rail and a parent that joins only
to a role's datums. Swap the brand and confirm the parent holds. Record the
result here. If it does not hold, the fallback is one role document per brand
sharing one reference sketch, and nothing on the text side of this record
changes.

## Alternatives rejected

| Alternative | Why not |
| --- | --- |
| Name the folder after the product | The name would have to change when the brand changes, and every reference above it with it. |
| Commit a resolved purchase list in the role | Protects against a change an explicit selection makes impossible. A stale duplicate for no gain. |
| Join the parent assembly to the supplier solid | Face names change when the solid is replaced, so every joint breaks on a swap. |
| Copy the supplier geometry into `cad/parts/` | `cad/parts/` is for parts we manufacture, and a copy per project is the duplication ADR-004 exists to remove. |
| Machine-readable specifications compared against requirements | A parts database ontology is a large project. An interface name records the same judgement in one string, and an engineer makes that judgement once. |
