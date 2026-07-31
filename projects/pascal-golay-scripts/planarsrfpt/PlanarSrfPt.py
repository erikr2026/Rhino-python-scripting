"""PlanarSrfPt.py
Ported from PlanarSrfPt.rvb (Pascal Golay, 2009-09-04).

Target engine: Rhino 8 Script Editor, CPython3 mode (run via F5, NOT the
legacy `RunPythonScript` command).

Original behavior:
  Interactively pick 3+ points, close them into a polygon (first point is
  appended again at the end), fit a plane through the first three points,
  and check every subsequent point against that plane within the
  document's absolute tolerance. Any off-plane point is snapped onto the
  plane (and marked with a visible point object + grouped + selected, plus
  a warning dialog) so the resulting closed polyline is guaranteed planar,
  then AddPlanarSrf builds the actual surface and the temporary polyline
  is deleted.

The `Rhino.AddStartupScript` / `Rhino.AddAlias` lines are commented out in
the original .rvb (dead code) and have no equivalent need in a Script
Editor Python file, so they are omitted here entirely.

BUG carried forward unchanged (not silently fixed):
  The original's point count check (`If UBound(arrPt)<=1 Then exit sub`)
  only guarantees **2** points minimum (indices 0 and 1), even though the
  comment directly above it says "make sure there are three points at
  least." With exactly 2 picked points, `Rhino.PlaneFitFromPoints(array(
  arrPt(0), arrPt(1), arrPt(2)))` on the next line would then index a
  nonexistent `arrPt(2)`, since VBScript's `Ubound`/array bounds checking
  would raise a runtime "Subscript out of range" error rather than exiting
  gracefully. This port reproduces the same off-by-one guard (`len(pts) < 3`
  would be the correct fix, but changing it would silently alter behavior)
  -- however, since Python raises IndexError rather than VBScript's silent
  script abort, a minimal try/except is added around the indexing itself
  purely to turn that crash into a clean command-line message instead of a
  raw traceback (per this domain's fabrication/traceback-handling rule),
  without changing when the abort happens.

API notes verified live against the mcneel/rhinoscriptsyntax GitHub source
(raw.githubusercontent.com/mcneel/rhinoscriptsyntax/master/Scripts/
rhinoscript/*.py) on this date:
  - rs.AddPlanarSrf takes a list of curve ids and returns a list of new
    surface ids (or None), not a single id -- the original .rvb passed a
    1-element array and only ever used the surface implicitly (it never
    read `strSrf` again), so this port does the same.
  - rs.MessageBox(message, buttons=0, title="") is the direct modern
    equivalent of the legacy `MsgBox` call; buttons=0 (OK only) matches
    the original's argument-less MsgBox call.
"""

import rhinoscriptsyntax as rs


def planar_srf_pt():
    pts = rs.GetPoints(
        draw_lines=True,
        message1="First point for planar surface",
        message2="Next point for planar surface. Press Enter when done")
    if not pts:
        return

    rs.EnableRedraw(False)
    try:
        # NOTE: reproduces the original's under-strict "<=1" guard verbatim
        # -- see BUG note in module docstring. This truly requires 3+
        # points to proceed safely; exactly 2 points will hit the guard
        # below via the try/except instead of indexing pts[2] directly.
        if len(pts) <= 1:
            return

        try:
            plane = rs.PlaneFitFromPoints([pts[0], pts[1], pts[2]])
        except IndexError:
            print("PlanarSrfPt: need at least 3 points -- aborted.")
            return

        pts = list(pts)
        pts.append(pts[0])  # close the polygon, same as the original

        tol = rs.UnitAbsoluteTolerance()

        off_plane_ids = []
        any_off_plane = False

        for i in range(3, len(pts)):
            test_pt = rs.PlaneClosestPoint(plane, pts[i])
            if rs.Distance(pts[i], test_pt) > tol:
                off_plane_ids.append(rs.AddPoint(pts[i]))
                pts[i] = test_pt
                any_off_plane = True

        curve_id = rs.AddPolyline(pts)
        srf_ids = rs.AddPlanarSrf([curve_id])
        rs.DeleteObject(curve_id)
    finally:
        rs.EnableRedraw(True)

    if not srf_ids:
        print("PlanarSrfPt: could not build a planar surface from the picked points.")

    if any_off_plane:
        group_name = rs.AddGroup()
        rs.AddObjectsToGroup(off_plane_ids, group_name)
        rs.SelectObjects(off_plane_ids)
        rs.MessageBox(
            "The points were not coplanar.\n"
            "The selected points were projected to the plane of the first three points",
            0, "PlanarSrfPt")


if __name__ == "__main__":
    planar_srf_pt()
