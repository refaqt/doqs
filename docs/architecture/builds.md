# Builds and lockfiles

Part of the doqs specification. Start at the [overview](../architecture.md).

## Builds & Lockfiles

A `builds/` directory at the project root represents real machine instances. Each subdirectory is one physical build: a shipped customer machine, a prototype, a workshop instance. The lockfile inside pins the exact version of every constituent module.

This is analogous to `Cargo.lock` or `package-lock.json` in software, but with longer life expectancy — physical machines may outlive several major versions of the design.

### Directory Layout

```
builds/
  README.md                      # What this folder is, how to make a new build
  example-baseline.toml          # Template for new builds
  serial-0042/
    build.toml                   # Pins exact version of every module
    notes.md                     # History of changes, non-standard modifications
    photos/
      delivery-state.jpg
      2026-01-spindle-upgrade.jpg
  serial-0091/
    build.toml
    notes.md
```

### Lockfile Format

```toml
# builds/serial-0042/build.toml
schema       = "doqs-build-v1"
machine      = "cnc-mill"
built-date   = "2025-03-15"
owner        = "Workshop X"
location     = "Antwerp, BE"

# Pin the top-level machine version this build is based on. Three fields make
# it a record rather than a reference: where to fetch it, the readable tag, and
# the exact commit — because a tag can be moved or deleted and the file would
# still look unchanged. See decisions/2026-09-18_build-records.md.
[base]
repo    = "https://github.com/refaqt/qarve"
version = "v1.0.0"
commit  = "9f2c1ab4e7d05c8b3a6f1e2d4c7b8a9f0e1d2c3b"

# Pin every module individually — these can deviate from the base
[[module]]
path    = "modules/frame"
repo    = "https://github.com/refaqt/qarve"
version = "v1.0.0"
commit  = "4b1d8e02fa37c96d5e0a71b3c8d4f6902ea5c17b"

[[module]]
path    = "modules/x-axis"
repo    = "https://github.com/refaqt/x-axis"
version = "v1.2.1"           # upgraded from v1.0.0 in 2025-04
commit  = "7c3e9a15d84b206fe3719c05ab8d2f4361e0b9a8"
model   = "default"          # selects which parametric model

# A product family vendored as one submodule: composition + model say which
# variant of it this machine was built to. See variants.md.
[[module]]
path        = "modules/linear-stage"
version     = "v1.0.0"
composition = "modules/linear-stage-servo-linear"
model       = "500mm"
sku         = "ALS-SL-500"   # optional, joins the family's catalog.toml

[[module]]
path    = "modules/spindle"
version = "v2.3.0"           # upgraded across major version in 2026-01
adapter = "modules/adapters/spindle-mount-v1-to-v2@v1.0.0"

# Free-form modifications that don't fit the model system
[[modification]]
date        = "2025-08-22"
description = "Replaced X20 limit switch with X25 (X20 EOL)"
bom-impact  = "SW-01: brand_pn changed Omron X20-1 → Omron X25-1"

[[modification]]
date        = "2026-01-15"
description = "Spindle v1 → v2 upgrade; adapter installed"
```

The lockfile serves three purposes:

1. **Reproducibility** — `python doqs/doqs.py restore-build builds/serial-0042 --out <dir>`
   clones every pinned repository at its exact commit, so you get the editable
   design files that machine was built from. `--check` asks whether every pin is
   still reachable and fetches nothing; run it on a schedule and a record that
   has become unopenable turns up while somebody can still act. It exits `1` when
   a commit is gone and `2` when a repository could not be reached, because those
   are different problems. It is not one of the gates: it needs a network, and no
   machine's CI should depend on every module host being up.
2. **Support** — when serial-0042 reports a problem, the maintainer knows precisely what's installed.
3. **Validation** — the compatibility validator checks that the pinned combination is interface-consistent (and that any required adapters are present).

### Customer Builds

For users assembling their own machine, `builds/example-baseline.toml` is the starting template. They copy it to their own `builds/<their-id>/build.toml` and either keep it private or contribute it back. A contributed build expands the project's known install base and gives downstream maintainers visibility into what's deployed.

External organisations running their own forks should keep their lockfiles in their own repos. A `known-consumers.toml` at the project root is the agreed place to list them, but no generator reads it yet, so entries there do not appear in the usage graph.

### Validator (`doqs/scripts/validate_build.py`)

[`scripts/validate_build.py`](../../scripts/validate_build.py) reads every
`builds/**/build.toml`, opens the `okh.toml` each entry points at, and collects the interfaces
those modules provide and consume. It fails when an entry consumes an interface that no module
in the same build provides.

One detail matters for families: when a lockfile entry names a `composition`, the validator reads
that composition's manifest, not the family root's. A stepper SKU and a servo SKU provide different
interfaces, so the family root cannot answer for either.

Run this in CI on every commit. When a new module version is published, CI immediately identifies which historical builds remain consistent and which need attention (an adapter, a backport, or explicit documentation of incompatibility).
