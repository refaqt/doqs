# FreeCAD reference — URLs and search templates

Read this file when you need specific links or search patterns. The main workflow is in [SKILL.md](SKILL.md).

## Official documentation

| Resource | URL |
|----------|-----|
| Wiki home | https://wiki.freecad.org/Main_Page |
| Online Help TOC | https://wiki.freecad.org/Online_Help_Toc |
| User hub | https://wiki.freecad.org/User_hub |
| Power users hub (macros, Python) | https://wiki.freecad.org/Power_users_hub |
| FreeCAD Manual | https://wiki.freecad.org/Manual:Introduction |
| Feature list / release notes index | https://wiki.freecad.org/Feature_list |
| Python API | https://www.freecadweb.org/api/ |
| Download / install | https://wiki.freecad.org/Download |
| Bug reporting guide (wiki) | https://wiki.freecad.org/Tracker |

## Version and releases

| Resource | URL |
|----------|-----|
| GitHub releases (stable + notes) | https://github.com/FreeCAD/FreeCAD/releases |
| Weekly/dev builds | https://github.com/FreeCAD/FreeCAD-Bundle/releases/tag/weekly-builds |
| CalVer scheme announcement (2026) | https://blog.freecad.org/2026/06/26/new-freecad-versioning-scheme-and-development-cycle/ |
| FreeCAD blog (release news) | https://blog.freecad.org/ |

When answering, state which release line applies (e.g. 1.1 stable vs 26.3dev weekly).

## Forum

Base: https://forum.freecad.org/

| Section | URL | Use for |
|---------|-----|---------|
| Help on using FreeCAD | https://forum.freecad.org/viewforum.php?f=3 | Usage questions, "am I doing this wrong?" |
| Open discussion | https://forum.freecad.org/viewforum.php?f=8 | Feature requests, general topics |
| Issues (forum mirror) | https://forum.freecad.org/viewforum.php?f=49 | Bug discussion; often links to GitHub |
| How to submit issues | https://forum.freecad.org/viewtopic.php?t=5236 | Bug report quality guidelines |
| Forum guidelines | https://forum.freecad.org/viewtopic.php?f=3&t=2264 | Before posting |

Search the forum with its built-in search or:

```
site:forum.freecad.org "<error text>" <workbench>
```

## GitHub (core FreeCAD)

| Target | URL |
|--------|-----|
| Issues | https://github.com/FreeCAD/FreeCAD/issues |
| Discussions | https://github.com/FreeCAD/FreeCAD/discussions |
| Pull requests | https://github.com/FreeCAD/FreeCAD/pulls |
| Documentation repo | https://github.com/FreeCAD/FreeCAD-documentation |
| CONTRIBUTING | https://github.com/FreeCAD/FreeCAD/blob/main/CONTRIBUTING.md |

**Addon/workbench bugs** belong on the addon's GitHub repo, not `FreeCAD/FreeCAD`. Examples: A2plus, Fasteners, Assembly4, etc. Search `site:github.com <addon-name> <error>`.

## Search query templates

Use these with web search or forum/GitHub search:

```
site:wiki.freecad.org <workbench> <tool name>
site:wiki.freecad.org <error message fragment>
site:forum.freecad.org <workbench> <symptom>
site:github.com/FreeCAD/FreeCAD <error message>
site:github.com/FreeCAD/FreeCAD/issues <feature name> closed
```

Combine with version when relevant:

```
FreeCAD 1.1 Assembly Insert Binder
FreeCAD "SubShapeBinder" circular dependency
```

## Common failures → where to look

| Topic | Wiki | Also search |
|-------|------|-------------|
| Assembly Insert / joints | [Assembly Workbench](https://wiki.freecad.org/Assembly_Workbench) | forum f=3 + GitHub issues "Assembly Insert" |
| SubShapeBinder / external refs | [FeatureSubShapeBinder](https://wiki.freecad.org/FeatureSubShapeBinder) | DOQS ADR-002; forum "Binder" + "circular" |
| PartDesign Body / Tip | [PartDesign Workbench](https://wiki.freecad.org/PartDesign_Workbench) | wiki "Tip"; forum "tip not set" |
| Links between documents | [Std LinkMake](https://wiki.freecad.org/Std_LinkMake) | wiki "Link"; broken path after move |
| TechDraw views | [TechDraw Workbench](https://wiki.freecad.org/TechDraw_Workbench) | forum workbench-specific section |
| FEM meshing / solver | [FEM Workbench](https://wiki.freecad.org/FEM_Workbench) | forum + GitHub; version-specific regressions |
| Spreadsheet / expressions | [Spreadsheet Workbench](https://wiki.freecad.org/Spreadsheet_Workbench) | wiki "Expression" |
| Safe Mode | Help → Safe Mode in app | forum "safe mode" for isolating addon issues |
| Macro errors | [Power users hub](https://wiki.freecad.org/Power_users_hub) | forum Macros section; addon repo if macro is third-party |

## DOQS cross-references

| Doc | Path | When |
|-----|------|------|
| Master sketches in Body | `doqs/docs/decisions/2026-06-24_freecad-master-sketches-body.md` | Assembly Insert failures, Binder cycles |
| Architecture (top-down) | `doqs/docs/architecture.md` | Module layout, params.csv → Spreadsheet |
| Agent workflow | `doqs/docs/agent-guide.md` | Installing this skill in machine repos |

## Reporting bugs (for the user)

If the issue is a confirmed bug after research:

1. Reproduce in latest stable or agreed dev build
2. Reproduce in Safe Mode when possible
3. File on the correct tracker (core vs addon)
4. Include: FreeCAD version, OS, step-by-step reproduction, minimal `.FCStd` if possible

Guides:

- https://forum.freecad.org/viewtopic.php?t=5236
- https://wiki.freecad.org/Tracker
- https://github.com/FreeCAD/FreeCAD/issues/new/choose
