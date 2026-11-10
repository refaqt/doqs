# 2026-11-10 — Licence files now say that Refaqt owns the copyright

**Role(s):** legal, software

## What happened

Every licence file that doqs writes now starts with a copyright notice for Refaqt
(BE 0804.145.539) and a link to the Refaqt Contributor Licence Agreement. Running
`bash doqs.sh generate` adds the notice to the licence files that a repository already has. The
rest of their text stays the same. Supplier folders and private parts libraries never get the
notice, because those files are not ours.

A missing notice is only a warning for now. A repository can make it a failure with
`validate_licenses.py --strict-copyright`. The reasons are in
[ADR-021](../decisions/2026-11-10_copyright-notice.md).

doqs also has two new templates in `templates/contributing/`: the small workflow that asks
contributors to accept the agreement, and a short `CONTRIBUTING.md`.

## Next Steps

- Move each machine repository's `doqs/` submodule to this change and run
  `bash doqs.sh generate`.
- Turn on `--strict-copyright` in CI once a repository has no warnings.
