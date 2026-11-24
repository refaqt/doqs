# 2026-11-24 — First monthly review of open-source CAD tools for AI agents

**Role(s):** cad

## What happened

We compared open-source CAD tools that AI agents can drive. The question was whether any tool can
work beside FreeCAD, or replace it. FreeCAD stays our main tool. It is still the only open-source
tool with mature CAM, finite element analysis (FEA), technical drawings and a wide ISO/DIN fastener
library together.

The most important change: SolidCraft now has technical drawings that stay linked to the model,
and an ISO fastener library. An agent can update and check a drawing after a design change with a
command. It does not have to draw it again. SolidCraft still has no CAM, no FEA and no GD&T
(geometric tolerancing). We have not tested its drawings by hand.

A scheduled task now runs this review on the 2nd of each month. Its session cannot see this
repository, so it reports in its own session. Someone copies the report here.

The full report is below. A separate cloud session wrote it on 24 November 2026. We checked a few
SolidCraft claims against its own documentation. We did not check most other claims by hand.

## Open Questions

- Do SolidCraft drawings really survive a small design change? How many dimensions need repair?
- Does MitCad really have linked drawings, GD&T frames and working CAM, as its user guide says?
- Which ISO standards does the SolidCraft fastener library cover? The list below comes from the
  report and is not checked.

## Next Steps

- Model one small part in SolidCraft through its agent connection. Make its drawing, change one
  size, update the drawing and count the broken dimensions.
- Try draftwright on STEP files from a machine's `build_model.py`, to get drawings that a script
  rebuilds.
- Copy the next monthly report into this log, as a new entry.

## The full report

The text below is the report as the review session wrote it. Small edits only: the title.

### 1. What changed since the baseline

The baseline is from earlier the same day, so the growth numbers cover almost no time. The real
month-to-month comparison starts with the December run.

1. **SolidCraft already ships drawings.** The drawing work reached the main branch on 28 October
   and first shipped in release v0.26.0. The baseline used roadmap numbers from 25 October, which
   were out of date.
   - What works: views, section and detail views, dimensions, sheets and templates. Export to PDF,
     SVG and DXF.
   - Model link: the commands `drawing.update`, `drawing.check` and `drawing.dimension.repair` keep
     the drawing linked to the model. An agent can call all of them. Not tested by hand.
   - Drawings are now saved inside the design file.
2. **SolidCraft has an ISO fastener library, since 8 October.** It covers ISO 4762, ISO 7380-1,
   ISO 10642, ISO 4014/4017, ISO 4032, ISO 7089, ISO 4026 and ISO 8734. Since v0.48.0 the Hole tool
   can make a countersink sized for an ISO 10642 screw.
3. **SolidCraft changed its geometry kernel on 2 November.** It now uses SolidCore, a Rust port of
   NVIDIA's SMLib (Apache-2.0). A new kernel can change the geometry of existing designs, so old
   designs need testing again. The design format number is now 66 and changes almost every day.
4. **SOMA names its fastener standards in its source code only.** The tables cover ISO 4762, 4014,
   4017, 4026, 4032, 4033, 4035, 7089, 7091, 7093, 7380 and 10642, and DIN 557, 931, 933 and 934.
   SOMA 1.0 (22 November) adds its own chat agent and promises that 1.0 models keep working until
   the next major version.
5. **MitCad, from its user guide.** Drawing views and dimensions follow design changes. Drawings
   have datum labels and feature control frames (GD&T). A CNC tab does 2D and 3D milling and lathe
   turning and writes G-code; the guide says to check every toolpath in a simulator first. The
   `.mitcad` file is JSON. Projects are git repositories with edit locks. Outside code changes are
   still not accepted. v0.72.0 (24 November) added weld symbols and mill-turn CAM.
6. **FreeCAD 26.3 is not out yet.** FreeCAD now uses calendar version numbers. Release candidate 2
   came out on 18 October. The stable version is still 1.1.4.
7. **No tool in the review has stopped.** cq_warehouse (fasteners for CadQuery) has had only 3
   commits in 3 months and no release since 2022. Fornjot, a Rust CAD kernel outside the review,
   was archived on 19 June 2026.

### 2. New tools found

| Tool | Licence | Verdict | Why |
| --- | --- | --- | --- |
| [text-to-cad](https://github.com/earthtojake/text-to-cad) | MIT | Add to the full review | 27.3k stars since April 2026. A plugin for many agent apps. Writes build123d scripts, makes PDF drawings from scripts and runs CalculiX FEA. |
| [draftwright-python](https://github.com/pzfreo/draftwright-python) | AGPL-3.0 | Watch, and try it | One command makes a dimensioned PDF, SVG or DXF drawing from a STEP file. FreeCAD scripts could feed it. |
| [vcad](https://github.com/muni-works/vcad) | Apache-2.0 | Watch | Own Rust kernel and MCP. Claims drawings with GD&T, 2.5D CAM and FEA. Runs only on macOS 15. Claims not checked. |
| [CADCraft](https://github.com/storytold/cadcraft) | MIT/Apache-2.0 | Watch | New Rust app with MCP for 2D drafting. Not 3D parametric design. |
| [FluidCAD](https://github.com/Fluid-CAD/FluidCAD) | MIT | Watch | Parametric CAD in JavaScript, fasteners as packages. No drawings or MCP mentioned. |
| [cadrs](https://github.com/rvdende/cadrs) | MIT/Apache-2.0 | Watch | Rust app that claims drawings and FEA. Only 2 months old. |
| [brepjs](https://github.com/andymai/brepjs) | Apache-2.0 | Watch | TypeScript CAD as code with an agent check loop. Drawings have no dimensions. |
| [ocp-freecad-cam](https://github.com/voneiden/ocp-freecad-cam) | Apache-2.0 | Watch | CAM for build123d and CadQuery, using FreeCAD's CAM code. Experimental. |

Rejected, to skip next month unless something changes:

- Not active: [Fornjot](https://github.com/hannobraun/fornjot) (archived),
  [partmode](https://github.com/BOMWiki/partmode) (last change 17 August).
- No agent interface, or not for machine design: [QymCAD](https://github.com/QymIs-Tech/QymCAD),
  [materializr](https://github.com/materializr-cad/materializr),
  [extrudo](https://github.com/zoltanf/extrudo), [shapecraft](https://github.com/jackharvest/shapecraft).
- Overlap with tools already in the review: [agentcad](https://github.com/jdilla1277/agentcad),
  [build123d-mcp](https://github.com/pzfreo/build123d-mcp),
  [cad-cae-copilot](https://github.com/armpro24-blip/cad-cae-copilot),
  [Studio](https://github.com/amywork777/studio).
- Text-to-model apps: [CADAM](https://github.com/Adam-CAD/CADAM),
  [SynapsCAD](https://github.com/timschmidt/synaps-cad) (no clear licence).
- Not checked in depth: [Chili3D](https://github.com/xiangechen/chili3d),
  [Dune 3D](https://github.com/dune3d/dune3d). No source code found for SindriCAD or 3BCAD.
- Unchanged: Zoo Design Studio (closed geometry engine), OpenSCAD, SolveSpace.

### 3. Comparison

| Question | FreeCAD | SolidCraft | SOMA | MitCad | build123d | CadQuery | text-to-cad |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Agent connection | Python, community MCP servers | Built-in MCP, command line, JSON commands | `soma` command line, own agent, no MCP | Built-in MCP, command line | Python, several MCP servers | Python, third-party MCP | Plugin for agent apps, command line, MCP |
| CAM | Yes, G-code | No | No | Yes, G-code (guide; not tested) | No | No | No |
| Drawings | TechDraw | PDF, SVG, DXF | PDF, DXF | PDF, SVG, DXF, DWG | Basic SVG, DXF | Basic SVG, DXF | PDF |
| GD&T | 2D symbols only | Planned | No | Datums and control frames (guide) | No | No | Text only |
| Drawing rebuilds after a change | Views yes, dimensions can break | Update, check and repair commands (not tested) | Yes, by script | Guide says yes | Yes, if you write the script | Yes, if you write the script | Yes, by script |
| Topological naming | Reduced, not solved | Names from kernel history, with warnings; new kernel | Code selectors | Names from kernel history | Code selectors | Code selectors | Code selectors |
| Assemblies | Assembly workbench, linked sub-assemblies; can break | Joints and motion; no linked sub-assemblies yet | Groups, exploded views | Joints, sub-assemblies | Joints in code | Constraints in code | In code, with interference check |
| ISO/DIN fasteners | Fasteners add-on: ISO, DIN, EN, ASME, GOST | Built in, ISO (list above) | ISO and DIN tables (list above) | Hole presets only | bd_warehouse: ISO, DIN, ASME | cq_warehouse (old) | None named |
| FEA | Built in | None | CalculiX included | None found | External | External | CalculiX, static loads |
| File format and git | `.FCStd` ZIP, binary | JSON text, or `.sc` ZIP with a git text view; lock file in shared folders | Python, plus a `.soma` bundle | JSON; git projects with edit locks | Python | Python | Python |
| Licence and maturity | LGPL-2.1; 1.1.4 stable | MIT/Apache-2.0; v0.48.1, daily releases | GPL-3.0 with model exception; v1.0.0 | MIT; v0.72.0, daily releases | Apache-2.0; v0.13.0 | Apache-2.0; v2.8.0 | MIT; v0.11.17; sends usage data unless turned off |

### 4. Growth

| Tool | Stars | Forks | Commits | Commits in last 30 days | Latest release |
| --- | ---: | ---: | ---: | ---: | --- |
| FreeCAD | 35,745 | 6,463 | 49,606 | 244 | 1.1.4 (28 September); 26.3 RC2 (18 October) |
| SolidCraft | 17,987 | 2,560 | 11,149 | 7,791 | v0.48.1 (24 November) |
| CadQuery | 6,164 | 576 | 2,251 | 8 | v2.8.0 (20 June) |
| build123d | 3,835 | 348 | 3,604 | 215 | v0.13.0 (19 September) |
| SOMA | 539 | 64 | 365 | 89 | v1.0.0 (22 November) |
| MitCad | 413 | 35 | 79 | 46 | v0.72.0 (24 November) |
| text-to-cad | 27,296 | 2,600 | 1,538 | not measured | v0.11.17 (23 November) |

SolidCraft grows fastest: 7,791 commits in 30 days and about 18k stars since its history started
on 7 October 2026. Most of its commits name an AI co-author. text-to-cad is the fastest new tool,
with 27.3k stars in 7 months. Stars measure attention, not quality.

### 5. Recommendation

1. Keep FreeCAD as the main tool.
2. Test SolidCraft beside FreeCAD on one small part, now that it has drawings and ISO fasteners.
   Keep in mind the new kernel, the frequent format changes, and the missing CAM, FEA and GD&T.
3. Try draftwright on STEP files from `build_model.py`, for script-built drawings without leaving
   FreeCAD.
4. Watch MitCad and text-to-cad. On paper MitCad covers the most questions, but nobody has tested
   it by hand.

### 6. Sources

- [FreeCAD on GitHub](https://github.com/FreeCAD/FreeCAD),
  [FreeCAD blog](https://blog.freecad.org/),
  [New FreeCAD version numbers](https://blog.freecad.org/2026/06/26/new-freecad-versioning-scheme-and-development-cycle/),
  [FreeCAD Fasteners add-on](https://github.com/shaise/FreeCAD_FastenersWB)
- [SolidCraft on GitHub](https://github.com/tangency-labs/solidcraft),
  [SolidCraft roadmap](https://github.com/tangency-labs/solidcraft/blob/main/ROADMAP.md),
  [SolidCraft command list](https://github.com/tangency-labs/solidcraft/blob/main/docs/features.md),
  [SolidCraft files guide](https://github.com/tangency-labs/solidcraft/blob/main/docs/book/src/guide/files.md),
  [SolidCraft releases](https://github.com/tangency-labs/solidcraft/releases),
  [Hackaday on SolidCraft](https://hackaday.com/2026/10/17/SolidCraft-is-parametric-automation-friendly-cad-for-desktop-and-browser/)
- [SOMA website](https://somacad.app/), [SOMA on GitHub](https://github.com/Kai-Jungsthoefel/SOMA)
- [MitCad on GitHub](https://github.com/mitcad/Mitcad),
  [MitCad user guide](https://github.com/mitcad/Mitcad/blob/main/docs/user-guide.md)
- [build123d](https://github.com/gumyr/build123d), [bd_warehouse](https://github.com/gumyr/bd_warehouse),
  [CadQuery](https://github.com/CadQuery/cadquery), [cq_warehouse](https://github.com/gumyr/cq_warehouse)
- [awesome-3d-skills list](https://github.com/zhuyansen/awesome-3d-skills),
  [AlternativeTo: open-source FreeCAD alternatives](https://alternativeto.net/software/freecad/?license=opensource),
  [Zoo Design Studio v1](https://docs.zoo.dev/blog/zoo-design-studio-v1)
- New tools: see the links in the table in section 2.
