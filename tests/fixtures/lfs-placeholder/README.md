# Git LFS placeholder

`pointer.txt` is what Git leaves in place of a CAD file when a clone has no
LFS content, for example a cloud session. Tests copy it over a `.FCStd` or a
`.step` to check that the checks warn and do not fail.

It is named `.txt` so that Git never treats it as an LFS file in this
repository.
