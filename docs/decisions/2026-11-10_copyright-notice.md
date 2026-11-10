# ADR-021 — Our licence files name Refaqt as the copyright owner

- **Date:** 2026-11-10
- **Status:** Accepted

Write this file in B2 English. Follow `.agents/rules/communication.md`. Keep official names, file paths, and numbers exact.

## Context

No Refaqt repository said who owns the copyright. The licence files said which licence applies,
but not who gives it. Copyright exists without a notice, but a notice is evidence, and every
licence we use makes people keep the notices when they copy our files. Refaqt also needs to
show that it owns its work, so that it can defend CERN-OHL-S and sell an OEM licence.

At the same time, Refaqt started a contributor agreement. Contributors keep their copyright and
give Refaqt a licence. The agreement lives in `refaqt/.github`.

## Decision

- Every licence file that describes our own work carries this notice:

  ```
  Copyright © 2025–<this year> Refaqt (BE 0804.145.539) and contributors.
  Contributions are accepted under the Refaqt Contributor Licence Agreement:
  https://github.com/refaqt/.github/blob/main/CLA.md
  ```

- The notice is part of the templates in `templates/licensing/`, so `apply_licenses.py` writes
  it into new files. For existing files, `apply_licenses.py` adds it without changing the rest
  of the text.
- Supplier folders (`cad/vendor/`, library `cad/` and `docs/datasheets/`), the upstream `spec/`
  folder, and private parts libraries never get the notice. Those files are not ours.
- The check follows ADR-018: `validate_licenses.py` prints `WARN` for a missing notice and exits
  0. `--strict-copyright` turns the warning into a failure.
- New text files of our own carry `SPDX-FileCopyrightText` next to `SPDX-License-Identifier`.
- `templates/contributing/` holds the small workflow that runs the shared contributor agreement
  check, and a short `CONTRIBUTING.md` that links to the central manual.

## Consequences

- A machine that bumps its doqs pin sees warnings until it runs `bash doqs.sh generate` (or
  `python doqs/scripts/apply_licenses.py`). Then it can turn on `--strict-copyright` in its CI.
- The holder name and first year are constants in `scripts/license_rules.py`
  (`COPYRIGHT_HOLDER`, `COPYRIGHT_FIRST_YEAR`). The last year follows the calendar, so the text of
  a newly written file changes each January. Existing files are not rewritten, because the check
  looks for the holder, not for the years.
