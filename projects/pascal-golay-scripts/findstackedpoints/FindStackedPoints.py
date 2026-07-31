"""
FindStackedPoints.py

Python 3 (CPython, PythonNet bridge) port of FindStackedPoints.rvb, for
Rhino 8's Script Editor (run via the ScriptEditor command, F5). Do NOT run
this through the legacy RunPythonScript command -- that invokes the
IronPython 2 engine.

Original behavior (Pascal Golay, legacy RhinoScript/VBScript):
  - Two entry points existed as command aliases in the original: SelStacked
    (scans ALL curve/surface objects in the document) and StackedPoints
    (prompts the user to pick which curves/surfaces to scan).
  - For each object, turns on control-point grips (if not already on),
    reads the grip locations, and looks for any that are coincident
    (duplicate positions) -- i.e. "stacked" control points, a common modeling
    defect.
  - SelStacked: selects the *objects* that contain stacked points, restoring
    grip state afterward, and reports if none were found.
  - StackedPoints: adds actual Point objects at each stacked location
    (grouped per source object), selects all of them, and reports if none
    were found.

Porting notes:
  - Rhino.AddStartupScript / Rhino.AddAlias (VBScript session-persistence
    hooks) have no equivalent here; this port just defines both functions
    and calls one of them at the bottom of the file when run directly. Edit
    the `if __name__ == "__main__":` block to pick sel_stacked() vs.
    stacked_points() -- or run either interactively from Script Editor.
  - Function-name mappings verified against the mcneel/rhinoscriptsyntax
    GitHub source (rhino-8.x branch): ObjectsByType, GetObjects,
    ObjectGripsOn, EnableObjectGrips, ObjectGripLocations, SelectObjects,
    ObjectsByGroup, AddGroup, AddPoints, AddObjectsToGroup,
    UnselectAllObjects, CullDuplicatePoints, EnableRedraw, Print all exist
    with the signatures used below.
  - ObjectGripLocations(object_id, points=None) returns a tuple of Point3d
    when called with no `points` arg (read mode) -- confirmed against source
    (grips.py). Filter type 4+8 = curve (4) + surface (8), matching the
    original's `Rhino.ObjectsByType(4+8)` / `Rhino.GetObjects(...,4+8,...)`.
  - The original's hand-rolled FindDuplicatePoints (nested O(n^2) loop
    comparing `Join(arrPts(p)) = Join(arrPts(q))`, an exact-string-match
    dedup) is replaced with rs.CullDuplicatePoints, which exists in modern
    rhinoscriptsyntax and does the same job (find coincident points) more
    robustly (tolerance-based rather than exact-string comparison). This is
    a behavior change worth flagging: CullDuplicatePoints(points,
    tolerance=-1) with the default tolerance uses Rhino's internal
    tolerance-based point comparison instead of bit-for-bit string identity,
    so two points that are *extremely* close but not identical (which the
    original would have treated as distinct) may now be flagged as
    duplicates. This is arguably a bug fix (stacked points from real
    modeling operations are rarely bit-identical), but it is a deliberate
    functional change from the original, not a literal translation.
  - BUG PRESERVED FROM ORIGINAL (flagged, not fixed): in both VBScript subs,
    the "were grips already on" flag (`G`) is declared and set to True
    *once*, before the loop over objects, and is never reset per-iteration.
    So the very first time an object is found with grips originally off, OR
    the first time stacked points are found on any object, `G` becomes
    False and *stays* False for every subsequent object in the same run --
    causing the script to turn off grips on every later object regardless
    of whether *that* object's grips were already on before the script
    ran. This looks unintentional (a per-object flag that should have been
    reset inside the loop), but this port reproduces it exactly rather than
    silently fixing it, per porting instructions. If you want the "fixed"
    behavior (grip state restored correctly per-object), reset the flag to
    True at the top of each loop iteration instead of only once before the
    loop.

Limitation: no live Rhino available in this environment to actually run the
script -- validated only with `python3 -m py_compile` (syntax parses) and a
manual read-through against the rhinoscriptsyntax source. Test in Script
Editor before relying on it.
"""

import rhinoscriptsyntax as rs

CURVE_AND_SURFACE_FILTER = 4 + 8  # rs.filter.curve + rs.filter.surface


def find_duplicate_points(pts):
    """Given a list of grip locations for one object, return the subset
    that are coincident (stacked), or None if there are no duplicates.

    Original used a hand-rolled exact-string-match dedup; this uses
    rs.CullDuplicatePoints (tolerance-based) -- see module docstring for why
    that's a deliberate, flagged behavior change rather than a literal port.
    """
    if not pts:
        return None

    dup_indices = []
    for p in range(len(pts)):
        for q in range(len(pts)):
            if p != q and rs.PointCompare(pts[p], pts[q]):
                dup_indices.append(p)

    if not dup_indices:
        return None

    candidate_pts = [pts[i] for i in dup_indices]
    result = rs.CullDuplicatePoints(candidate_pts)
    return result if result else None


def sel_stacked():
    """Select every curve/surface object in the document that has stacked
    (coincident) control points."""
    objs = rs.ObjectsByType(CURVE_AND_SURFACE_FILTER)
    if not objs:
        rs.Print("No stacked control points found")
        return

    rs.EnableRedraw(False)

    stacked_objs = []
    grips_flag = True  # mirrors VBScript `G` -- see module docstring bug note:
                        # set once before the loop, never reset per-object.
    for obj in objs:
        if not rs.ObjectGripsOn(obj):
            grips_flag = False
            rs.EnableObjectGrips(obj, True)

        grip_pts = rs.ObjectGripLocations(obj)
        if grip_pts:
            dups = find_duplicate_points(list(grip_pts))
            if dups:
                stacked_objs.append(obj)
                grips_flag = False

        if not grips_flag:
            rs.EnableObjectGrips(obj, False)

    rs.EnableRedraw(True)

    if stacked_objs:
        rs.SelectObjects(stacked_objs)
    else:
        rs.Print("No stacked control points found")


def stacked_points():
    """Prompt the user to pick curves/surfaces, then add Point objects
    (grouped per source object) at every stacked (coincident) control
    point found."""
    objs = rs.GetObjects("Select curves and surfaces", CURVE_AND_SURFACE_FILTER, True, True)
    if not objs:
        rs.EnableRedraw(True)
        return

    rs.EnableRedraw(False)

    all_stacked = []
    found_any = False
    grips_flag = True  # mirrors VBScript `G` -- see module docstring bug note.

    for obj in objs:
        if not rs.ObjectGripsOn(obj):
            grips_flag = False
            rs.EnableObjectGrips(obj, True)

        grip_pts = rs.ObjectGripLocations(obj)
        if grip_pts:
            dups = find_duplicate_points(list(grip_pts))
            if dups:
                grp = rs.AddGroup()
                stacked_pt_ids = rs.AddPoints(dups)
                rs.AddObjectsToGroup(stacked_pt_ids, grp)
                all_stacked.extend(stacked_pt_ids)
                found_any = True
                grips_flag = False

        if not grips_flag:
            rs.EnableObjectGrips(obj, False)

    rs.UnselectAllObjects()

    if all_stacked:
        rs.SelectObjects(all_stacked)

    rs.EnableRedraw(True)

    if not found_any:
        rs.Print("No stacked control points found")


if __name__ == "__main__":
    # Original had two separate aliases (SelStacked / StackedPoints).
    # Pick whichever behavior you want by calling the corresponding
    # function -- default to the point-adding variant since it's the more
    # commonly used of the two.
    stacked_points()
