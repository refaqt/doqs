# 2026-10-07 — Tools can now edit SysML files, manifests and library tables

**Role(s):** software

## What happened

The second step of the fabriq work: the text files that describe a design can now be read
and changed by a program, without a person opening them. Before, every port, part usage,
connection and manifest entry was typed by hand, and the architecture fell behind the CAD.

Work done:

- A SysML reader and editor for the subset of SysML v2 in use: packages, imports, port
  definitions, part definitions and usages, ports, attributes, connections, binds,
  requirements and their documentation. It works on the text and keeps every comment and
  every line it does not add. A rerun changes nothing. It round-trips the three real
  architecture files of the compact stage.
- A manifest editor that adds a table such as `[[provides-interface]]` or `[[part]]` to an
  `okh.toml`, or sets one key, and keeps the comments. Python reads TOML but does not write
  it, so this works on lines.
- Row helpers for a parts library: a `parts.csv` row, a `vendor-index.csv` row with its
  checksum, size and time, append-only writing that refuses to overwrite a row, one cell
  that may fill in later (the `cad` path), the terms a row gets from a brand's decision, and
  a comparison of the public and private libraries file by file.
- One naming rule that ties a SysML port to its FreeCAD frame and its OKH entry. See
  [ADR-015](../decisions/2026-10-07_port-and-frame-share-a-name.md).

## Decisions

- [ADR-015 — A port and a mounting frame share one name](../decisions/2026-10-07_port-and-frame-share-a-name.md)

## Next Steps

- Commands built on these modules: take a supplier part into the libraries, wrap its STEP
  file, scaffold a module or part, use a library part in a machine, add an interface.
- Validators for interfaces and frames, warning first.

<details>
<summary>Technical notes</summary>

- `scripts/sysml_rules.py`: `parse()`, `find()`, `walk()`, readers `interfaces()`,
  `parts()`, `connections()`, `requirements()`; editors `add_port_def()`, `add_part_def()`,
  `add_port()`, `add_part_usage()`, `add_connect()`, `add_requirement_def()`,
  `add_requirement_member()`, `set_doc()`, `add_import()`, `new_module_text()`. A
  statement scanner with comment and string masking; `doc /* */` is its own statement.
- `scripts/okh_rules.py`: `append_table()`, `set_key()`, `get_key()`, `has_table()`,
  `find_table()`, `interface_entries()`, `render_manifest()`, `RawValue` for dates.
- `scripts/library_rules.py`: `vendor_row()`, `parts_row()`, `append_row()`, `set_cell()`,
  `read_rows()`, `terms_for()`, `sha256_and_size()`, `template_text()`, `mirror_diff()`.
- `scripts/interface_rules.py`: `frame_label()`, `port_name_of()`, `port_def_name()`,
  `split_port_def()`, `okh_entry()`, `okh_matches()`.
- Tests: `tests/test_sysml_rules.py` (fixture `tests/fixtures/sysml/stage.sysml`),
  `tests/test_okh_rules.py`, `tests/test_library_rules.py`, `tests/test_interface_rules.py`.

</details>
