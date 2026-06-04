# DOQS naming examples

## Module paths

```
modules/x-axis/
modules/x-axis/modules/drive-belt/
modules/x-axis-belt/
modules/adapters/spindle-mount-v1-to-v2/
```

## BOM row

```csv
SW-001,Limit Switch,"SPDT 5A lever",electrical,4,pc,3.20,18,SPDT-5A-LEVER,Omron,X20-1,,,,
```

## OKH fragment

```toml
version = "1.2.0"
release = "https://github.com/org/qarve/releases/tag/v1.2.0"

[[model]]
name = "500mm"

[[part]]
name = "Carriage Plate"
```

## Interface

```toml
[[provides-interface]]
name = "XAxisOutputInterface"
version = "1.0"
```

## Lockfile pin

```toml
[[module]]
path = "modules/x-axis"
version = "v1.2.0"
```
