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
2. Enter offset distance and direction (outward/inward) interactively.
3. Offsets the whole shell (`Brep.CreateOffsetBrep`, with a face-by-face
   fallback if that fails) and bakes it.
4. Pick two faces directly off the baked offset polysurface via sub-object
   (face) selection - not two separate top-level objects.
5. Maps each selected offset face back to its corresponding face on the
   *original* (unoffset) shell, by topological index first, falling back to
   closest-point spatial matching.
6. Computes a bisector surface between the two selected offset faces: finds
   their shared intersection edge, averages face normals along it, projects
   outward by a user-entered length, and extends the resulting curves at
   both open ends by a user-entered side-extension distance (default 12
   units) before lofting.
7. Builds a perpendicular T-fin surface along the bisector's primary edge,
   offset by two independently-configurable distances.
8. Offsets the bisector surface both directions (positive/negative,
   independently configurable).
9. Intersects each offset bisector against the *original* (unoffset,
   mapped-back) faces - not the whole original shell.
10. Lofts a connecting surface between each T-fin edge and its closest
    matching intersection curve, aligning curve directions first
    (`Curve.DoDirectionsMatch`) to avoid twisted lofts.

Every stage bakes its result to a dedicated color-coded layer (`02` through
`07`) regardless of downstream success, and prints a `debug_log(...)` line to
the command history - this is the debugging convention to preserve in any
further revision.

## Known issue - not yet fixed

**Duplicate `intersect_with_shell` definition.** Two functions share this
name: an earlier one taking a *list* of original faces (iterates and
intersects against each), and a later one taking a *single* original brep
(no iteration). Python keeps only the second definition - the first is dead
code. `main()` calls it with a list (`target_orig_faces`), which the active
(single-brep) definition receives as its `original_shell_brep` parameter and
passes directly to `Intersection.BrepBrep`. This worked in the confirmed run
(log read "Found 1 intersection curves", matching the second definition's
message text), most likely because `target_orig_faces` happened to contain
exactly one element that run. If a future run maps both selected faces to
two distinct original panels (the more typical case), this is likely to
throw or misbehave. Flagged, not fixed yet - watch for this if intersection
counts look wrong or the script errors at Step 8.

## Testing plan

1. Re-run on the real hull with both selected faces mapping to two *distinct*
   original panels, to specifically exercise the known issue above.
2. Confirm the bisector's side-extension length and the two independent
   T-fin offset distances against real fabrication tolerances - defaults
   (12", 1.0, 1.0) were chosen as placeholders during development, not
   verified against the actual part.
3. Check whether `get_corresponding_original_face`'s topological-index-first
   matching is reliable across the whole hull, or whether it's silently
   falling back to spatial matching more often than expected (both paths log
   distinctly via `debug_log("Face Mapping", ...)`).
