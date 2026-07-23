# shell-bisector-lines

Standalone Rhino Python script (raw `RhinoCommon` + a few `rhinoscriptsyntax`
utility calls, CPython 3 via Rhino 8/9's PythonNet bridge). Run via Rhino's
**ScriptEditor** command (type `ScriptEditor`, open this file, press F5) —
**not** `RunPythonScript`, which invokes the legacy IronPython 2 engine
instead and will fail (see the sibling `shell-bisector-t-surface` project's
README for the confirmed 2026-07-22 incident this convention comes from).
Also not a Grasshopper component — this script gathers its own input
interactively.

A leaner companion to `projects/shell-bisector-t-surface/shell_bisector_t_surface.py`
in this same repo — see that project first for the full T-fin/loft/
grouping/multi-junction pipeline and its debugging history. This script
reuses that project's working patterns (sub-object face picking, seam +
averaged-normals bisector algorithm, `out`-parameter tuple handling, the
multi-junction Esc-to-finish loop, and per-junction grouping) but drops the
T-fin/loft/face-mapping parts of that pipeline — see Scope below.

**Status (2026-07-23): corrected after a real Rhino run.** First draft had
two issues the owner caught by actually running it — see "Fixed since
first draft" below. Not re-tested in Rhino since the fix; see Testing plan.

## What it does

1. Enter a reach/extent distance and an offset distance, once for the
   whole run (applied to every junction below). No whole-shell selection —
   this script only ever touches the two faces picked per junction.
2. Loops over junctions: pick two faces via sub-object (face) selection
   (`Rhino.Input.Custom.GetObject` with `SubObjectSelect = True` — a plain
   `rs.GetObject` surface filter can't pick individual faces off a joined
   polysurface), process that junction fully, then prompt for the next
   pair. Cancel ("Esc") on a junction's first-face prompt to stop — one
   script run can handle every seam that needs a bisector, not just one.
3. Per junction:
   - computes the **bisector surface** between the two selected faces
     (shared seam curve, averaged face normals, projected outward by the
     reach distance, lofted);
   - offsets it both directions (+ and -) by the offset distance, producing
     two **offset surfaces**;
   - intersects each offset surface against **only the two faces this
     junction's bisector was built from** (face1 and face2 — not the whole
     shell, not the offsets against each other), producing **intersection
     curves**;
   - groups all of that junction's baked outputs together so multiple
     junctions in one run stay distinguishable (see Grouping below).

No T-fin construction, no final connecting loft, no per-face topological-
index mapping-back to the original shell — see Scope below for why.

## Layer scheme

| Layer | Color | Contents |
|---|---|---|
| `01_Bisector` | Yellow | Bisecting surface, one per junction |
| `02_Offset_Pos` | Orange | Bisector offset by `+offset_distance`, one per junction |
| `02_Offset_Neg` | Purple | Bisector offset by `-offset_distance`, one per junction |
| `03_Intersections` | Red | Intersection curves, both offset surfaces vs. the junction's own two reference faces |

Layers are shared across all junctions in a run, same as the sibling
project's convention — grouping (below), not separate layers, is what
keeps different junctions' outputs distinguishable. Every stage prints a
`debug_log(...)` line to the command history.

## Grouping

Each junction's baked outputs (bisector surface, both offset surfaces, and
all intersection curves from that junction) are grouped together under
`ShellBisectorLines_Junction_01`, `_02`, etc. — reusing
`shell_bisector_t_surface.py`'s create-group-before-populate pattern.
`rs.AddObjectsToGroup` only adds to a group that already exists — it does
not create one — so the group is created with `rs.AddGroup(name)` first;
the sibling project's own README documents hitting this exact silent
no-op bug before landing on that fix.

## Fixed since first draft (2026-07-23, real-Rhino run)

The owner ran the first draft and caught two real problems:

1. **Duplicate shell surface.** The first draft baked an unmodified copy of
   the whole input shell as a QA reference layer (`01_Original_Shell`).
   The owner does not want that. Fixed by removing the whole-shell
   selection/extraction/baking step entirely — this script no longer
   touches anything but the two faces picked per junction.
2. **Wrong intersection target.** The first draft intersected each offset
   surface against the whole original shell — explicitly flagged at the
   time as an unconfirmed guess (the source request only said "intersect
   the offset surfaces" without saying against what). Owner corrected:
   each offset surface must intersect **only** against the two faces the
   bisector surface for that junction was built from. Fixed — `main()`'s
   junction loop now cross-intersects both offset surfaces against both
   reference faces (up to 4 curve sets per junction, 0 if none of the 4
   pairs actually touch).

## Scope: multi-junction looping kept; T-fin/loft/face-mapping still dropped

Per explicit correction from the owner (relayed mid-task, after an initial
single-junction draft), this script loops over as many face-pair junctions
as needed in one run — same Esc-to-finish pattern as
`shell_bisector_t_surface.py`'s Step 4 — rather than handling only one
junction per run. Reach and offset distances are prompted once and applied
to every junction in the run.

Still dropped, unchanged from the original leaner-scope request: T-fin
construction, the final connecting loft, and per-face topological-index
mapping-back to the original shell (not applicable here regardless — this
script never offsets the whole shell, so there's no offset-copy face that
would need mapping back). Opinion, unchanged: this is still the right call
for a lean companion script rather than a duplicate of the full pipeline —
if T-fin/loft turns out to be needed here too, port it from the sibling
project rather than rebuilding it from scratch.

## Testing plan

1. **Load-test on a trivial shape first** (two planar faces meeting at a
   simple angle) before the real hull — per the sibling project's own
   lesson, a script that works on a trivial case can still hide a
   design-level flaw that only complex real geometry exposes.
2. Test with at least **two junctions in one run** to confirm shared-layer
   baking and per-junction grouping both work as expected, and that the
   Esc-to-finish loop exit behaves correctly.
3. Confirm the reach/extent distance and offset distance defaults (5.0,
   0.5) against real fabrication tolerances — both are development
   placeholders, not verified against an actual part.
4. Confirm the corrected intersection behavior actually produces the
   expected reference/cut lines against the two selected faces — not yet
   re-tested in Rhino since the fix.
5. Verify the "same face picked twice" guard actually stops a bad pick
   before it reaches `compute_bisector_surface` (rather than relying on
   that function's own "no shared seam edge" failure path), and that the
   junction retry doesn't advance `junction_count`.
