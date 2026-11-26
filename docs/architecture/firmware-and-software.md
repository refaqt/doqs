# Firmware and software

Part of the doqs specification. Start at the [overview](../architecture.md).

## Firmware

Firmware is a software project and follows a software project structure. Each target (motion controller board, pendant display, etc.) is its own sub-project. Firmware will eventually be extracted into its own repo, following the same submodule pattern as hardware modules.

```
firmware/
│
├── README.md                    # Overview: what boards, how to build, how to flash
│
└── motion-controller/           # One folder per firmware target
    ├── README.md                # Target-specific: board, toolchain, flashing
    ├── platformio.ini           # Build system config (PlatformIO)
    │   # -- or CMakeLists.txt for CMake-based projects
    ├── src/
    │   └── main.cpp             # Entry point
    ├── include/
    │   └── config.h             # Compile-time constants
    ├── lib/                     # Local libraries / vendor code
    ├── tests/                   # Unit tests (e.g. Unity, GoogleTest)
    │   └── test_kinematics.cpp
    ├── config/
    │   └── machine.json         # Runtime machine config: speeds, limits, steps/mm
    └── docs/
        ├── log/
        └── decisions/
```

**Config vs. compile-time constants:**

- `config/machine.json` — machine-specific runtime parameters (steps per mm, max speed, homing offsets). Committed to Git; differs between machines. AI-editable.
- `include/config.h` — compile-time constants that don't change between machines.

**When to extract firmware to its own repo:**
Apply the same test as hardware modules: when the firmware is stable enough to reuse in another machine project. Use `git subtree split --prefix=firmware/motion-controller` and the same submodule pattern.

## Software

`firmware/` covers code that runs *on the machine*. `software/` covers code that runs *beside* it -
host-side applications, analysis libraries, calibration and identification tooling, GUIs. Both are
software projects and follow the same shape; they are separated because their build, test and
deployment stories have nothing in common, and conflating them makes the root confusing.

Use `software/` when the code needs a PC to run: a desktop control application, a library that
post-processes `measurement/` data, a script that generates excitation signals. Use `firmware/` when
the code is flashed to a target board.

```
software/
|
|-- README.md                    # Overview: what these projects are, how to install
|
`-- identification/              # One folder per application or library
    |-- README.md                # Purpose, install, how to run
    |-- pyproject.toml           # Build system config (or package.json, Cargo.toml, ...)
    |-- src/
    |   `-- <package>/           # Importable package - not a flat pile of scripts
    |-- tests/
    |-- config/                  # Runtime config, committed
    `-- docs/
        |-- log/
        `-- decisions/
```

**Make it a package, not loose scripts.** A folder of sibling scripts that import each other by bare
name only works when run from exactly one directory, and breaks the moment anything moves. Declare a
real package with a build config from the start.

**Analysis code belongs here, its outputs do not.** A script that turns raw captures into an FRF lives
in `software/`; the FRF it produced is a `derived` row in a `measurement/data-index.csv`, and the
conclusion drawn from it is a `measurement/results/<case>/summary.md`.

**When to extract to its own repo:** the same test as hardware modules and firmware - when it is stable
enough to reuse in another machine project. Use `git subtree split --prefix=software/<name>` and the
same submodule pattern.
