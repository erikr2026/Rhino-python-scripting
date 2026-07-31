"""PlanarizeCurve.py
Ported from PlanarizeCurve.rvb (Pascal Golay, RMA, 2007-09-06).

Target engine: Rhino 8 Script Editor, CPython3 mode (run via F5, NOT the
legacy `RunPythonScript` command).

Original behavior:
  Forces a curve's control points onto a best-fit plane.
    - If "Fix end points" = No: the fit plane is computed from ~100 sample
      points spread along the whole curve (a true least-squares best fit).
    - If "Fix end points" = Yes: the fit plane is instead forced through
      just 3 points so the curve's endpoints land exactly on the plane:
        * open curve:  start point, curve midpoint-ish average, end point
        * closed curve: start point, and the averages of the first/second
          half of the sampled points
      In both "Fix end points" cases, if the plane style is "Vertical",
      one of those 3 points is replaced by a point directly above (in the
      CURRENT VIEW's construction-plane Z direction) the relevant average
      point, forcing the fit plane to contain the vertical direction
      instead of being a free least-squares fit.
  Once the fit plane is found, every control point (grip) of the curve is
  projected onto that plane in place (via PlaneClosestPoint), so the curve
  becomes perfectly planar. Grips are temporarily turned on if they
  weren't already, and turned back off afterward if this script is what
  turned them on.

BUG carried forward unchanged (not silently fixed):
  In the CLOSED-curve + "Vertical" branch, the original .rvb computes
  `avPts` (average of the two half-averages) and its vertically-raised
  companion point, but then throws `avPts` itself away and only keeps
  `avHalf1 = avPts` / `avHalf2 = <vertical point>`. The original,
  non-vertical `avHalf1`/`avHalf2` values (each an actual local curve
  region average) are discarded and replaced -- meaning for a closed
  curve in "Vertical" mode, the "fit" plane is built from
  (curve start point, the combined average of the whole curve, a point
  vertically above that average) rather than from any true 3-region
  sampling. This may well be intentional (it does produce a plane
  containing the vertical direction), but it is NOT the same shape of
  computation as the open-curve vertical branch (which keeps the actual
  start/end points and only replaces the *middle* point). Reproduced
  exactly as in the .rvb below -- flagged here rather than "fixed".

  Separately: the "Fix end points" Yes/No and "Plane style" Auto/Vertical
  prompts in the original both silently ignore anything other than an
  exact (case-insensitive) "Yes"/"No" or "Auto"/"Vertical" typed answer --
  because `rs.GetString` is given those two strings as clickable options,
  the user can't actually type something else, so this is a non-issue in
  practice and is preserved via the same `strings=[...]` option list.

API notes verified live against the mcneel/rhinoscriptsyntax GitHub
source (raw.githubusercontent.com/mcneel/rhinoscriptsyntax/master/Scripts/
rhinoscript/*.py) on this date:
  - rs.PlaneClosestPoint(plane, point, return_point=True) returns the
    projected 3D point directly (not a parameter pair) when return_point
    is left at its default True -- matches the original's
    `Rhino.PlaneClosestPoint(plane, grip, True)` call.
  - rs.ViewCPlane(), rs.XformWorldToCPlane(pt, plane), and
    rs.XformCPlaneToWorld(pt, plane) all exist with this exact argument
    order.
  - rs.DivideCurve default returns points (return_points=True default),
    matching the original's 2-argument `Rhino.DivideCurve(curve, 100)` call.
"""

import rhinoscriptsyntax as rs


def average_points(pts):
    """Simple centroid of a list of 3D points."""
    n = len(pts)
    sx = sum(p.X for p in pts)
    sy = sum(p.Y for p in pts)
    sz = sum(p.Z for p in pts)
    return rs.CreatePoint(sx / n, sy / n, sz / n)


def planarize_curve():
    curve_id = rs.GetObject("Select curve to planarize", rs.filter.curve,
                             preselect=True, select=True)
    if curve_id is None:
        return

    fix_ends = rs.GetString("Fix end points", "Yes", ["Yes", "No"])
    if fix_ends is None:
        return
    fix_ends = fix_ends.strip().lower() == "yes"

    plane_style = rs.GetString("Plane style", "Auto", ["Auto", "Vertical"])
    if plane_style is None:
        return
    vertical = plane_style.strip().lower() == "vertical"

    rs.EnableRedraw(False)
    try:
        grips_were_on = rs.ObjectGripsOn(curve_id)
        turned_on_here = False
        if not grips_were_on:
            rs.EnableObjectGrips(curve_id)
            turned_on_here = True

        seed_pts = rs.DivideCurve(curve_id, 100)
        grip_count = rs.ObjectGripCount(curve_id)
        start_pt = rs.CurveStartPoint(curve_id)

        pts = None

        if fix_ends:
            if not rs.IsCurveClosed(curve_id):
                end_pt = rs.CurveEndPoint(curve_id)
                mid_pt = average_points(seed_pts)

                if vertical:
                    cplane = rs.ViewCPlane()
                    temp = average_points([start_pt, end_pt])
                    cplane_pt = rs.XformWorldToCPlane(temp, cplane)
                    cplane_pt = rs.CreatePoint(
                        cplane_pt.X, cplane_pt.Y, cplane_pt.Z + 1)
                    mid_pt = rs.XformCPlaneToWorld(cplane_pt, cplane)

                pts = [start_pt, mid_pt, end_pt]

            else:
                half = int(0.5 * (len(seed_pts) - 1))
                half1_pts = seed_pts[0:half + 1]
                half2_pts = seed_pts[half:half + half + 1]

                avg_half1 = average_points(half1_pts)
                avg_half2 = average_points(half2_pts)

                if vertical:
                    # Reproduces the original .rvb's closed-curve vertical
                    # branch exactly, including discarding avg_half1/2 in
                    # favor of the combined average -- see BUG note above.
                    avg_pts = average_points([avg_half1, avg_half2])
                    cplane = rs.ViewCPlane()
                    cplane_pt = rs.XformWorldToCPlane(avg_pts, cplane)
                    cplane_pt = rs.CreatePoint(
                        cplane_pt.X, cplane_pt.Y, cplane_pt.Z + 10)
                    avg_half1 = avg_pts
                    avg_half2 = rs.XformCPlaneToWorld(cplane_pt, cplane)

                pts = [start_pt, avg_half1, avg_half2]
        else:
            pts = seed_pts

        if pts:
            plane = rs.PlaneFitFromPoints(pts)
            if plane is None:
                print("PlanarizeCurve: could not fit a plane to the sample points -- aborted.")
            else:
                for i in range(grip_count):
                    grip_pt = rs.ObjectGripLocation(curve_id, i)
                    destination = rs.PlaneClosestPoint(plane, grip_pt, True)
                    rs.ObjectGripLocation(curve_id, i, destination)

        if turned_on_here:
            rs.EnableObjectGrips(curve_id, False)
    finally:
        rs.EnableRedraw(True)


if __name__ == "__main__":
    planarize_curve()
