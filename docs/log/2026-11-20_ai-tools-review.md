# 2026-11-20 — What AI tools can add to our design work

**Role(s):** engineering, cad, simulation, software

## What happened

We compared our way of working with the best public use of AI agents in hardware design. Our way
of working is Claude Code with our own skills, doqs, FreeCAD 1.1 and SysML v2. Six research tracks
searched GitHub, YouTube, research papers and supplier pages on 20 November 2026. The tracks were:
CAD made by AI, FreeCAD, SysML v2, simulation and calculation, electronics and parts, and how
leading teams run their agents.

The short answer: we are close to the best public practice, not behind it. The leading systems
work the way we do. The model is written as code, a program measures the result, and git and
checks stop bad output. Our weak points are in what we check and in who checks it. They are not
in our choice of tools.

This entry is wider than the
[monthly review of CAD tools](2026-11-24_cad-tools-review.md). That review asks which CAD program
to use. This entry asks what to add around FreeCAD. Both say the same thing: keep FreeCAD as the
main tool.

A longer version with more tables is a private web page of the project owner. This entry keeps
everything that matters for a decision.

### Where we are ahead

- Every parameter says where its value comes from: a requirement, a catalogue, a standard, a
  simulation or a design choice. No public CAD agent setup that we found does this.
- Parameters link to SysML v2 requirement names, and a check confirms that the requirement exists.
  We found no other open link from SysML v2 to FreeCAD.
- The geometry fingerprint (volume, size box, centre of mass) is the same idea as the number checks
  in the best research system,
  [CADSmith](https://arxiv.org/abs/2603.26512) (March 2026).
- Assemblies join at named mounting frames, not at faces. Research shows that models fail exactly
  when they must pick the right face
  ([CADEngBench](https://arxiv.org/abs/2608.09296)).
- We found no public agent skill for SysML v2. Ours may be one of the first.

### Where we are behind

- **No second opinion.** The agent that designs a part also judges it. Leading systems use a
  separate reviewer with a fresh start, and often a judge that looks at pictures of the part.
- **The fingerprint measures totals, not features.** A missing hole or a pocket on the wrong face
  can keep a normal volume. Leading tools list holes, diameters and hole patterns.
- **No engineering checks after each change.** Nothing checks stress, stiffness, machining rules or
  parts that collide.
- **SysML is scanned, not parsed.** Our reader finds statements but does not resolve names or check
  types. No verification case links a requirement to its test result.
- **Few outputs are made by a script.** Drawings, exploded views, assembly guides, cable drawings
  and pictures are still made by hand.
- **We do not measure our own agent.** We do not know how often it gets a part right, so we cannot
  tell whether a change to a skill helped.

### Steps, in order of value for effort

The first five steps need no new CAD tool and no paid service.

1. **A feature list and a collision check.** Add the features of each part to the fingerprint:
   round faces (radius, axis, depth), hole patterns (count and spacing) and the positions of the
   `IF_` frames. Compare them with the parameter file, for example "4 × Ø6.6 on 50 mm spacing".
   Check each pair of parts in an assembly for overlap and for a minimum gap. Keep expected values
   for each part and each variant, and fail the check when a value drifts. Ideas to copy:
   `inspect_features` in [build123d-mcp](https://github.com/pzfreo/build123d-mcp) (Apache-2.0) and
   the step check in [cadpilot](https://github.com/LBurny/cadpilot) (MIT).
2. **A separate reviewer agent.** Make 6 to 8 standard pictures of the part without a window. Give
   them, with the requirement text, to a new agent that never saw the code. It answers yes or no
   questions, such as "Is there a pocket on the top face?". A second reviewer reads the changes of
   each pull request for standards, parts list and machining rules. Run it two or three times and
   keep only the findings that agree. CADSmith raised the overlap with the target shape from 0.81
   to 0.96 this way. A [study from Carnegie Mellon](https://arxiv.org/abs/2603.24768) found that a
   watching agent beats an agent that checks itself.
3. **Calculations as code.** Use [marimo](https://github.com/marimo-team/marimo) notebooks, which
   are plain Python files, with [handcalcs](https://github.com/connorferster/handcalcs) and
   [pint](https://github.com/hgrecco/pint) for units. Start with one axis: life of the ballscrew
   and the guides, critical shaft speed, buckling, motor inertia ratio and torque, and bearing life.
   Each calculation reads the parameter file, tests the SysML requirement, and writes a summary.
   Check each calculation once against a supplier tool (THK, Bosch Rexroth, Kollmorgen) and keep
   that as evidence.
4. **A real SysML parser, and a repair loop.** Read SysML with
   [tree-sitter-sysml](https://pypi.org/project/tree-sitter-sysml/) plus our own table of names and
   imports. Run the official
   [SysML v2 Pilot Implementation](https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation)
   once a night as a second check. The SysML skill then runs the parser after every edit and
   repairs until the file is clean. A
   [2026 study](https://arxiv.org/abs/2607.14162) raised valid output from 51% to 100% with this
   loop.
5. **Turn every mistake into a check.** For each new entry in `docs/mistakes/`, ask which check,
   test or hook would catch it next time. Count how many mistakes have such a check.
6. **One finite element pipeline.** Build one FreeCAD FEM and CalculiX case for the stiffness of
   the frame and the gantry, and for the first natural frequency. Use a fixed template with a test
   whose answer is known, such as a beam with one fixed end, and a mesh study. Do not let the agent
   write a case from nothing: every study we found shows that agents get the supports, the units or
   the mesh wrong.
7. **Verification cases in SysML.** Add a `verification def` with `verify` for each key
   requirement. Each simulation and each bench test writes a small result file. A check builds one
   table: requirement, what meets it, what tests it, last result, pass or fail.
8. **Drawings made by a script, and a parts list check.** Write `cad/build_drawing.py` with
   TechDraw views and dimensions, without a window. Compare the parts list that the FreeCAD assembly
   gives with `bom/*.csv`. A person still checks where the dimensions sit. Code to read:
   [AnkusDrive](https://github.com/gchen19/AnkusDrive) (Apache-2.0, very young). The CAD review of
   24 November also suggests [draftwright](https://github.com/pzfreo/draftwright-python).
9. **Measure our agent.** Make 10 to 20 fixed tasks, for example "a NEMA 23 motor mount for a
   16 mm ballscrew, with frames `IF_motor` and `IF_screw`". Pass each task by a result with a
   tolerance, not by an exact match. Run them after each change to a skill or a model. The public
   inputs of [CADGenBench](https://huggingface.co/spaces/HuggingAI4Engineering/CADGenBench) score
   STEP files, so FreeCAD output can take part.
10. **Circuit boards and cables as code.** Run [KiBot](https://github.com/INTI-CMNB/KiBot) in the
    checks for each KiCad board: parts list, fabrication files and STEP. Write each cable in
    [WireViz](https://github.com/wireviz/WireViz) and check wire colours and sizes against
    IEC 60204-1. [KiCad StepUp](https://github.com/easyw/kicadStepUpMod) brings the board into the
    FreeCAD assembly.
11. **A datasheet store and a stock store.** Take the values from supplier PDFs once per part
    number and keep them as JSON in the repository. Cite that file from the parameter file. A
    separate job writes price, stock and end of production (from Nexar/Octopart or LCSC) into a
    separate file, not into the design parts list, and warns about parts that will stop.
12. **Risk assessment as code before 20 January 2027.** That is the date from which the EU
    Machinery Regulation (EU) 2023/1230 applies. Keep `risk/hazards.yaml`. For each hazard, record
    the ISO 12100 type, the life phase, the zone (a SysML part), the risk before and after, the
    measures in the order the standard asks, and a link to the requirement and its evidence. The
    check fails on a hazard without a measure or without evidence. We found no open tool for this.
    A notified body (an official testing body) or a safety specialist must review the result.

### Our outputs, and the tools that can make them

| Output | Now | Best open option | Advice |
| --- | --- | --- | --- |
| Parts and assemblies | FreeCAD from `build_model.py` | Stay on FreeCAD. Use build123d only for hard shapes and as a second check on STEP files. | Keep |
| Geometry check | Fingerprint | Add features, collisions, expected values and a picture judge. [caddiff](https://github.com/angel291592/caddiff) lists STEP changes that a check can block on. | Extend |
| Mass properties | Own script | FreeCAD 26.3 adds a Mass Properties command. | When 26.3 is final |
| Drawings | By hand | TechDraw by script | Copy the pattern |
| Parts list | CSV per module | Assembly parts list in FreeCAD, checked against the CSV | Add a check |
| Exploded views, assembly guide | By hand | Exploded views and snapshots in 26.3, pictures with [F3D](https://f3d.app/viewer), pages in [GitBuilding](https://gitbuilding.io) | Try |
| Pictures and web viewer | On request | F3D, and glTF with [three-cad-viewer](https://github.com/bernhard-42/three-cad-viewer) | Try |
| Requirements | SysML v2 text, SysON | Keep. Add a parser, verification cases, rules for ports and a wording check. | Extend |
| Diagrams | SysON only | Make them in the checks from the Pilot Implementation or our own Mermaid. Keep SysON for editing. | Try |
| Calculations | Not organised | marimo, handcalcs and pint | Adopt |
| Stress and vibration | None | FreeCAD FEM and CalculiX without a window | Adopt |
| Shape optimisation | None | [BESO](https://github.com/calculix/beso). Bring results back as parameter changes, never as a mesh. | Later |
| Axis dynamics | None | python-control, OpenModelica, the LinuxCNC simulator | Later |
| Error budget, tolerance stack | None | No mature library. Write it in NumPy. | Build |
| CAM | By hand | FreeCAD CAM by script, or [ocp-freecad-cam](https://github.com/voneiden/ocp-freecad-cam) | Later |
| Circuit boards | KiCad | KiBot. Try [Zener](https://github.com/diodeinc/pcb) or [atopile](https://github.com/atopile/atopile) on one small board. | Adopt KiBot |
| Cables, control cabinet | By hand | WireViz, and a wire list in CSV | Adopt |
| Firmware settings | Own schema | [FluidNC](https://github.com/bdring/FluidNC) now ships a settings schema, a check and an MCP server. | Copy the pattern |
| OKH manifest | Own check | Also check against the [iop-alliance OKH schema](https://github.com/iop-alliance/OpenKnowHow) | Try |
| CE technical file | Compliance skill | Risk assessment as code (step 12) | Build |

### CAD

- Tools around the model matter more than the model. On CADGenBench, plain models score about
  35–41%. The same models with good tools score 60–92%. These numbers come from a summary site, not
  from the official board.
- On real industrial parts written as FreeCAD Python
  ([RealCADBench](https://arxiv.org/abs/2609.03773)), the best models make code that runs only
  56–81% of the time.
- Changing an existing model is much easier for a model than making one from nothing. Start each
  new part from a module template.
- Small features, such as chamfers and small holes, get lost most often.
- Two checks are needed. Exact numbers catch size errors. Pictures judged by a fresh agent catch
  wrong shapes.
- The most complete public example is the skills pack
  [text-to-cad](https://github.com/earthtojake/text-to-cad) (MIT). It covers parts, assemblies,
  machining rules, CalculiX checks, drawings and pictures, on build123d instead of FreeCAD.
- Agent connections to FreeCAD worth a look: the
  [robust MCP server by spkane](https://github.com/spkane/freecad-addon-robust-mcp-server)
  (Apache-2.0) next to our [neka-nat server](https://github.com/neka-nat/freecad-mcp). Our server
  now also runs CalculiX through its `run_fem_analysis` tool.
- FreeCAD 26.3, the version after 1.1, was at its second release candidate on 20 November. Run a
  26.3 job in the checks next to 1.1.4 now.

**Advice we did not take.** One research track said to use the `execute_code_headless` and
`reload_document` tools of the FreeCAD connection. We keep both blocked. Together they can write
over a file that is open in FreeCAD without a warning. See [agent-cad.md](../agent-cad.md).

### SysML v2

- SysML v2.0 has been a formal standard of the Object Management Group since 2025. Version 2.1 is
  a draft.
- [SysON](https://github.com/eclipse-syson/syson) releases about every two months. Its text import
  and export got much better in 2026. Keep the text in git as the master copy. The AI chat for
  SysON is only in a paid edition.
- Write requirements that a tool can test, with units:
  `require constraint { travel >= 300 [mm] }`. Then the parameter check can test the CAD value, and
  not only that the name exists.
- Add rules for ports: shaft against bore, voltage and current, thread, flow direction.
- Add a wording check for requirement text: vague words, "and/or", missing units, more than one
  "shall". Cite the INCOSE rule numbers, not their text, because the text is under copyright.
- Watch but do not depend on yet: Syside Automator by Sensmetry (paid licence key), sysmlpy (young,
  one author), Sysand (package manager for SysML, early preview).

### Simulation

- Agents for flow simulation are further along than agents for stress. In all studies, agents fail
  on supports, units and mesh. A fixed case template with a check works much better.
- A rule from a 2026 Modelica study fits us: the agent may stop only when simulation results
  support every requirement that applies, not when the model merely runs.
- AI shortcut models (NVIDIA PhysicsNeMo, PhysicsX, Neural Concept) pay off only when one run takes
  hours. Our frame runs take seconds to minutes in CalculiX.
- No open tool covers bolted joints to VDI 2230, chatter, or a full machine error budget. Supplier
  tools for guides, ballscrews and motors have no interface for programs. Write our own Python and
  check it once against the supplier tool.

### How leading teams run their agents

- [Anthropic and Diode](https://anthropic.com/research/claude-electronics-design) let Claude design
  three working devices in November 2026: circuit, board, enclosure, firmware and parts list. The
  agent wrote its own fit check and found that the board must tilt 25° to go into the case. People
  still built and tested the devices.
- Review on every pull request: [kicad-happy](https://github.com/aklofas/kicad-happy) (MIT) and
  AllSpice run several reviewer agents that use datasheets, and compare each review with the last
  one.
- Checks that the agent may not relax: every part number must exist at a distributor, and every
  relaxed tolerance needs a cited source.
- Each lesson ends with the question "would the system catch this next time?"
- One git worktree per agent. A hook stops the agent before its usage limit and makes it write a
  note to resume from.

### Not now

- Zoo, Onshape AI, Fusion, SolidWorks and Siemens agents: good, but they put a closed or cloud
  CAD core under an open design.
- Backflip, Spectral Labs, Leo AI: closed services.
- OpenSCAD and CADAM: they make meshes only, not exact solids.
- Flux, Quilter, DeepPCB: closed or paid.
- CAE-Agent-Hub: its licence does not allow commercial use.
- AI shortcut models for simulation: our runs are too cheap to need them.
- Instant price APIs for machined parts: only JLC has a public one.

### Videos worth watching

- [Text to CAD: How I designed a robot with LLMs and open source tools](https://www.youtube.com/watch?v=ajzFkkiyLMM),
  Ubuntu Summit 26.10.
- [I Connected Claude AI to FreeCAD](https://www.youtube.com/watch?v=6trAkQY5_kc), Make Form. Edits
  work best when the agent names faces and edges by number.
- [I Used 5 Different Agentic AI Tools for Same CAD Design](https://www.youtube.com/watch?v=hIVY_jWk_I8),
  Türkişi Engineering.
- [AI で 3DCADを動かす (FreeCAD + MCP)](https://www.youtube.com/watch?v=xp52dUrZfiM), JinSato 3D-CAD
  Lab. Useful for repeated work, too early to hand over everything.
- [SolidCraft using Claude Code](https://www.youtube.com/watch?v=1GggLcdKeGo), Joe's DIY Lab. Fixing
  the agent's shapes took longer than drawing by hand.
- [SysML v2 Simulation, 3D CAD Result Visualization and Report Generation using AI with MCP](https://www.youtube.com/watch?v=crSVoatZDxQ),
  MBSE Execution. The public demo closest to doqs.
- [Requirement Satisfaction and Verification](https://www.youtube.com/watch?v=hibccXv2TZg),
  Sensmetry.
- [FreeCAD v1.1 Assembly: Exploded View and TechDraw](https://www.youtube.com/watch?v=3vGaiArjKko),
  MangoJelly Solutions.
- [handcalcs, Python calculations in Jupyter](https://www.youtube.com/watch?v=FVfWnu0Pb28),
  Connor Ferster.
- [Is AI Text-to-CAD a Bad Idea?](https://www.youtube.com/watch?v=P_Q3asMhX5Q), Evan Reese.

### Limits of this review

- The GitHub interface was blocked during the research. Star counts come from web pages and are
  rounded. Upload dates of videos could not be read.
- Benchmark scores and supplier numbers are the authors' own claims. We did not test any tool by
  hand.
- Some young projects (AnkusDrive, sysmlpy, small MCP servers) have one maintainer. Fix their
  version before we rely on them.
- A specialist must check the compliance date and the class of machine.

## Next Steps

- Choose which of the twelve steps to start. Each chosen step gets a decision record and its own
  pull request. This entry changes no code and no check.
- Start with steps 1 to 5. They fit the current tools and cost little.
- Plan the risk assessment (step 12) now, because the date of 20 January 2027 is close.
