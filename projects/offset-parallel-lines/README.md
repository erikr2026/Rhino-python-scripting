# offset-parallel-lines

**Status: WIP** — the owner is testing/tweaking this in Rhino on their PC. The version here may lag behind local changes; check with the owner before assuming this copy is current.

Moves two selected parallel lines apart from each other by a settable distance.

## What it does

1. Select two straight lines (they should already be parallel; the script warns — but doesn't stop — if they're more than 1° off).
2. Enter the offset distance either by:
   - **Typing a number** at the command prompt and pressing Enter, or
   - **Clicking a point**, then either clicking a second point (the distance is measured between them) or typing a number for the second prompt.
3. Each line is translated perpendicular to its own direction, away from the other line, by that distance. So a distance of `1.0` increases the gap between the two lines by `2.0` total — each line moves `1.0` away from where it started (this matches the standard Rhino "offset distance" convention: the distance is what each curve moves, not the resulting gap).

## How to run

Paste `offset_parallel_lines.py` into Rhino's `RunPythonScript` command, or load it via the ScriptEditor and run.
