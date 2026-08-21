# <case-slug> — Campaign Definition

## Purpose

What question this campaign answers, and which SysML requirement it verifies.

## Setup

- **Machine configuration:** which `[[model]]` / `cad/params/` set the hardware was built to
- **Firmware version:** tag or commit flashed to the target
- **Instrument:** make, model, software version
- **Sampling:** rate per channel, duration, trigger

## Channel map

| Channel | Signal | Sensor | Sensitivity | Units |
| ------- | ------ | ------ | ----------- | ----- |
| 0       |        |        |             |       |

## Protocol

Ordered, repeatable steps. Anyone should be able to re-run this campaign from here alone.

1.

## Run naming

`YYYY-MM-DD_NNN[_variant]/` — variant names the configuration under test, not the conditions.

## Data location

Files are recorded to the storage root declared in `../../README.md` and indexed in
`../../data-index.csv`. Nothing from this campaign is committed to Git except summaries.
