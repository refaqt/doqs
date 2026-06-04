# Naming lexicon

Approved vocabulary for **module slugs**, **BOM display names**, and **`[[part]].name`** fields. The validator (`doqs/scripts/check_names.py`) tokenizes names on spaces and hyphens and warns when a token is not listed here.

Add words via pull request when a new functional term is needed. Prefer existing words over synonyms (e.g. `mount` not `bracket-mount` unless both words are meaningful).

## Motion

- axis
- carriage
- gantry
- slide
- travel

## Drive

- belt
- ballscrew
- leadscrew
- pulley
- coupler
- drive

## Structure

- frame
- plate
- bracket
- mount
- spacer
- shim

## Guidance

- rail
- block
- bearing
- bushing

## Actuation

- motor
- stepper
- servo
- spindle

## Sensing

- switch
- endstop
- probe
- encoder
- limit

## Fastening

- screw
- bolt
- nut
- washer
- insert

## Other

- adapter
- default

Machine-readable copy: [data/naming-lexicon.txt](../data/naming-lexicon.txt) (one word per line, used by validators).
