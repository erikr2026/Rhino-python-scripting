# shell-bisector-t-surface

Standalone Rhino Python script (raw `RhinoCommon` + `rhinoscriptsyntax` for a
few utility calls, CPython 3 via Rhino 8's PythonNet bridge). Run via Rhino 8's
**ScriptEditor** command (type `ScriptEditor`, open this file, press F5) —
**not** `RunPythonScript`, which invokes the legacy IronPython 2 engine
instead and will fail (confirmed 2026-07-22: `RunPythonScript` choked on a
non-ASCII docstring character with a Python-2-only encoding-declaration
error). Also **not** a Grasshopper component (this script gathers its own
input interactively; GH components get inputs injected as globals instead).

**Status (2026-07-22): working, first successful full run on the real hull.**
Confirmed end-to-end on real geometry (not just a trivial test shape) —
console log showed every stage succeeding through the final loft.

## History

The first implementation (rhinoscriptsyntax-based, fixed module-level
parameters, no interactive input) went through several real-Rhino bug fixes
in this session — see the project's Lessons for the full list (invented API
calls, wrong keyword names, `BeginUndoRecord`/`EndUndoRecord` argument
mistakes, offsetting the whole hull instead of just the two needed panels,
a missing `Intersection` import). That version never got past the second
"compute bisector surface" stage before the owner needed interactive offset
distance/direction and sub-object face picking on a real polysurface -
capabilities the rhinoscriptsyntax approach couldn't provide (`rs.GetObject`
with a surface filter can't pick individual faces off a joined polysurface).

The owner worked with a different tool in parallel to add that interactively,
which required moving to raw `RhinoCommon` calls (`Rhino.Input.Custom.GetObject`
with `SubObjectSelect = True`, `Rhino.Geometry.Brep.CreateOffsetBrep`,
`Rhino.Geometry.Intersect.Intersection.BrepBrep`, `Rhino.Geometry.Brep.CreateFromLoft`).
That surfaced a second wave of Rhino-8/9-CPython-specific gotchas along the
way (see Lessons) before landing on the version below, which the owner
confirmed runs cleanly on the real hull.

## What it does

1. Select the original shell polysurface.
2. Enter offset distance and direction (outward/inward) interactively, plus
   bisector/fin parameters - once, for the whole run.
3. Offsets the whole shell (`Brep.CreateOffsetBrep`, with a face-by-face
   fallback if that fails) and bakes it.
4. Loops over junctions: pick two faces directly off the baked offset
   polysurface via sub-object (face) selection (not two separate top-level
   objects), process that junction fully, then prompt for the next pair.
   Cancel ("Esc") on a junction's first-surface prompt to stop - one script
   run handles every seam on the hull, not just one.
5. Per junction: maps each selected offset face back to its corresponding
   face on the *original* (unoffset) shell, by topological index first,
   falling back to closest-point spatial matching.
6. Computes a bisector surface between the two selected offset faces: finds
   their shared intersection edge, averages face normals along it, projects
   outward by the entered length, and extends the resulting curves at both
   open ends by the entered side-extension distance before lofting.
7. Builds a perpendicular T-fin surface along the bisector's primary edge.
8. Offsets the bisector surface both directions (positive/negative).
9. Intersects each offset bisector against the *original* (unoffset,
   mapped-back) faces - not the whole original shell.
10. Lofts a connecting surface between each T-fin edge and its closest
    matching intersection curve, aligning curve directions first
    (`Curve.DoDirectionsMatch`) to avoid twisted lofts.
11. Groups each junction's final loft outputs under its own group name
    (`ShellBisector_Junction_01`, `_02`, ...) so multiple junctions' results
    stay distinguishable.

Every stage bakes its result to a dedicated color-coded layer (`02` through
`07`, shared across all junctions) regardless of downstream success, and
prints a `debug_log(...)` line to the command history - this is the
debugging convention to preserve in any further revision.

## Fixed since first working run

**Duplicate `intersect_with_shell` definition (2026-07-22).** Two functions
shared this name: one taking a *list* of original faces (iterates and
intersects against each), and one taking a *single* original brep (no
iteration). Python kept only the second - the first was dead code, and
`main()` was calling the survivor with a list. It happened to work on the
very first real-hull run (log read "Found 1 intersection curves") because
`target_orig_faces` had exactly one element that run; the very next run
mapped both selected faces to two distinct original panels and hit
`ERROR | expected Brep, got list` at Step 8, exactly as predicted. Fixed by
deleting the shadowing single-brep duplicate, leaving only the
list-iterating version `main()` actually needs.

**Final lofts not grouping (2026-07-22).** `rs.AddObjectsToGroup(ids, name)`
only adds to a group that *already exists* - it does not create one. The
script called it directly with a group name that had never been created via
`rs.AddGroup(name)`, so the call silently did nothing. Fixed by calling
`rs.AddGroup(group_name)` first. Folded into the multiple-junction change
above - each junction now creates and populates its own group.

## Testing plan

1. Confirm the bisector's side-extension length and the two independent
   T-fin offset distances against real fabrication tolerances - defaults
   (12", 1.0, 1.0) were chosen as placeholders during development, not
   verified against the actual part.
2. Check whether `get_corresponding_original_face`'s topological-index-first
   matching is reliable across the whole hull, or whether it's silently
   falling back to spatial matching more often than expected (both paths log
   distinctly via `debug_log("Face Mapping", ...)`).
