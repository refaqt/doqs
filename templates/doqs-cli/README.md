# The doqs command

`doqs.sh` and `doqs.bat` are the one command a machine repository runs. Both call
`python doqs/doqs.py`, which dispatches to the scripts in `doqs/scripts/`.

`install_root_tools.py` copies both files to the consumer repository root and
overwrites them when the template changes, exactly as it does for `syson.sh` and
`syson.bat`. Nobody copies them by hand.

```bash
bash doqs.sh check       # every gate, plus "are the generated files current?"
bash doqs.sh generate    # write every generated file, in the right order
bash doqs.sh list        # every command, and what it runs
```

`doqs.sh` falls back to `python` when `python3` is missing, so it works on
Windows shells that ship only `python`.

`validate_all.py` still exists and still runs the same seven gates. A repository
that bumps its doqs pin therefore sees no change in CI until it chooses to call
`doqs check`, which adds three checks on generated files.
