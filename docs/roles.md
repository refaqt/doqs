# Role modules

How to buy a part without letting the brand's name leak into your design.

Read [architecture.md](architecture.md) first for the module layout this builds
on, and [parts-library.md](parts-library.md) for where the parts come from. The
decision behind this page is
[ADR-005: role modules](decisions/2026-09-18_role-modules.md).

---

## The problem in one paragraph

Your machine needs an X-axis linear guide. Today you buy a HIWIN rail. In three
years HIWIN discontinues it, or THK becomes cheaper, or a customer in another
country cannot get the HIWIN part. The job has not changed. Only the product
has. So the job needs a name and a home of its own, and the product needs to be
one line inside it that you can change.

---

## The shape

```
machine-repo/modules/linear-guide-x/
├── okh.toml                            the role, its requirements, the part selected
├── architecture/linear-guide-x.sysml   the requirements and the interface it needs
├── cad/linear-guide-x.FCStd            reference geometry + a link to the chosen part
└── bom/bom.csv                         optional, only if the role adds something of its own
```

**Every file here is written by a person. Nothing is generated.** There is no
resolver to run and no generated file that can go stale.

Name the role after the job, never the product: `linear-guide-x`, not
`hgr20-rail`. This is the rule [naming.md](naming.md) already states for
instance modules.

---

## The manifest

```toml
# modules/linear-guide-x/okh.toml
okhv     = "OKH-LOSHv1.0"
name     = "X Linear Guide"
repo     = "https://github.com/refaqt/qarve/tree/main/modules/linear-guide-x"
version  = "1.0.0"
license  = "CERN-OHL-S-2.0"
licensor = "REFAQT"
function = "Guides the X carriage over 500 mm of travel."

[role]
library  = "modules/stoq"
selected = "hiwin/hgr-rail#HGR20R500"
approved = [
  "hiwin/hgr-rail#HGR20R500",
  "thk/shs-rail#SHS20R500",
]

[[consumes-interface]]
name    = "LinearGuide20MountInterface"
version = "1.0"
```

| Key | Meaning |
| --- | --- |
| `library` | Repository-root-relative path of the mounted parts library |
| `selected` | The part you buy today: `<brand>/<family>`, then `#`, then the brand's own part number. It must also appear in `approved`. |
| `approved` | Optional. Parts you checked against this role's requirements and would accept |

`approved` is where engineering judgement gets written down. Without it, "we
evaluated THK once and it was fine" lives in somebody's memory and dies when
they leave. Validation holds every entry to the same rules as the selected part,
so the record cannot rot into a wrong claim, and it refuses a `selected` that is
not among them: what you buy today must be something you decided is acceptable.

**A reference names the brand and the family**, not the folders between them:
`hiwin/hgr-rail#HGR20R500`. That keeps it short enough to read in a table cell,
and it stays valid if the library changes how it nests its own modules.

---

## The requirements

Formal requirements live only in SysML, in the module's `architecture/` folder.
That rule already applies to every module; a role is a module.

```sysml
// modules/linear-guide-x/architecture/linear-guide-x.sysml
package LinearGuideX {
    import '../../../architecture/machine.sysml'::MachineRequirements::*;

    requirement def XGuideStiffness {
        doc /* Deflection under 200 N side load stays below 0.02 mm. */
    }

    port def LinearGuide20MountInterface;
}
```

The role's `[[consumes-interface]]` names the interface it needs. A library part
that fits declares the matching `[[provides-interface]]`, and validation refuses
a selection that does not.

Writing the first few of these is real work. It is also the point: this is where
the reason for a purchase finally gets recorded.

---

## What is checked

Five checks replace the generated file an earlier design would have written.

| Check | Result |
| --- | --- |
| The selected part exists in the library | error, naming the part |
| The selected part is not discontinued | warning, naming the replacement where the row gives one |
| The selected part provides every interface the role consumes | error, naming the interface |
| Every `approved` alternative passes the same two checks | error |
| The FreeCAD document links the part the text selects | error, naming both |

The last check is the valuable one. It catches the mistake that actually
happens: you change the selection in text and forget the model, or change the
model and forget the text.

### Why there is nothing to generate

A library update **cannot change what you buy**. The role names an exact part
number. A newer library commit can only change facts about that one part — a
revised geometry file, a discontinued status, a corrected mass. There is no
silent substitution to protect against, so a copy in your repository would be a
duplicate that goes stale and nothing else.

The rule, in general:

> Generate a file only when the value lives in someone else's repository and you
> have no other way to see it change. When the value is a human decision, give
> the person a template and check their entry.

Three things in all of DOQS still meet that test:

| Generated file | Why it cannot be a source file |
| --- | --- |
| `cad/params-table.csv` | A FreeCAD Configuration Table holds literal numbers only. It cannot evaluate `carriage_travel = rail_length - 180`, so the arithmetic must be done first. |
| `graph/usage-graph.json` | A reverse index over every manifest. Nobody can maintain it by hand. |
| the machine-wide purchase list | Gathered across every module. Gitignored, rebuilt on demand. |

---

## The CAD rules

Two facts decide everything here. FreeCAD cannot link a `.step` file — it links
to an object inside an `.FCStd`. And replacing an imported solid changes face
and edge names, so a joint made to a supplier face breaks.

So the role document carries **its own reference geometry**, expressing the
requirement rather than the product: the mounting plane, the bolt pattern, the
travel line, the datum the parent needs.

1. The parent machine assembly joins **only** to the role's reference geometry.
   It never touches an imported supplier face.
2. Inside the role document, the chosen library part is placed against that same
   reference geometry, once.
3. Switching brand re-places one object in one document. Everything above is
   untouched.

This is ADR-002's reasoning applied one level out: depend on geometry you
control, not on geometry that will be replaced.

> **Prove it before you rely on it.** Build a two-brand test on real geometry,
> swap the brand, and confirm the parent holds. If it does not, keep one role
> document per brand sharing one reference sketch and link the right one.
> Nothing on the text side of this page changes either way.

**Do not** put supplier geometry in `cad/parts/`. That folder is for parts we
manufacture. The role links the library document; it copies nothing.

Switch on *Use relative paths when saving external links* in FreeCAD, or the
link breaks for everyone who clones the repository.

---

## Three kinds of change

Not every brand change is a design change, and treating them the same wastes
work.

| Case | What it means | What to do |
| --- | --- | --- |
| **Drop-in equal** | Same envelope, hole pattern and height | Not a design change. One row, an `equiv_class` tag naming the interchange group, and the buying system takes either. |
| **Different part, same role** | Mounting differs, the role still holds | Change `selected`, re-place the part against the role's datums. Nothing above the role moves. |
| **Different role** | A profile rail becomes a round shaft | A real design change. The role module changes and its requirements are reviewed again. |

`equiv_class` and interfaces do not compete:

- `equiv_class` is a **buying** statement about two part numbers: take either.
- An interface is a **design** statement about a module: this fits here.

---

## When you do not need a role

A washer does not carry requirements. For an ordinary bought part, one extra
cell on the row you already write does the whole job:

```csv
id,name,spec,category,qty,unit,unit_mass_g,equiv_class,brand,brand_pn,part,notes
STD-004,Cap Screw,DIN912 M4x10 A2-70,fastener,24,pc,2,M4X10-SHCS,DIN,M4X10,stoq:din/din-912#M4X10,
```

Use a role module when the part has requirements, an interface, or a place in
the assembly that a different brand would disturb. Use a row for everything
else.

---

## Recipes

### Add a role

1. `modules/<role>/okh.toml` with `[role]` and any `[[consumes-interface]]`.
2. `modules/<role>/architecture/<role>.sysml` with the requirements, traced up.
3. `modules/<role>/cad/<role>.FCStd`: the reference geometry, then a link to the
   selected library document, placed against it.
4. Point `[[hasComponent]]` in the parent's `okh.toml` at the role.
5. `python doqs/doqs.py check`.

### Swap the brand

1. Change `selected` in `okh.toml`.
2. Open the role document, re-place the new part against the reference geometry,
   save.
3. `python doqs/doqs.py check`. The link check fails if you did step 1 without
   step 2.

The parent assembly is not opened and not edited.

### Record an alternative you evaluated

Add it to `approved`. Validation then holds it to the same interface rules as
the selected part, so the record cannot rot into a wrong claim.

---

## Related

- [Parts library](parts-library.md) — where the parts come from
- [Architecture](architecture.md) — folder layout and interfaces
- [Naming](naming.md) — why a role is named after its job
- [Variants](variants.md) — our own product families, which work differently
