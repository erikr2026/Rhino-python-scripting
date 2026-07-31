"""Orient2ptCrv.py
Ported from Orient2ptCrv.rvb (Pascal Golay, RMA, 2007-10-24).

Target engine: Rhino 8 Script Editor, CPython3 mode (run via F5, NOT the
legacy `RunPythonScript` command).

Original behavior:
  1. Pick objects to orient.
  2. Ask Yes/No whether to copy (kept only as a UI cue in the original --
     see BUG note below, it was never actually used to control the copy).
  3. Pick two "base" points defining a base direction vector.
  4. Pick a target curve.
  5. Pick a reference point on that curve, and a second point on the curve
     near the desired true target point.
  6. Build a sphere centered at the reference point with radius equal to
     the base-point distance, intersect it with the target curve, and of
     all the intersection points pick the one closest to the second picked
     point -- this is the real target point.
  7. Build a plane at the reference point (curve frame) and a plane at the
     base start point (normal = base direction), remap the picked objects
     from the base plane to a "target" plane built from the vector between
     the two curve points, producing a *copy*.
  8. Run the interactive `_Rotate3D` command on that copy, pre-feeding the
     "rotate from" / "rotate to" points as literal world-coordinate
     command-line arguments (the rotation AXIS itself is still picked
     interactively by the user when this command runs) -- this lets the
     user twist the pre-oriented copy about a hinge line while the script
     supplies the twist angle via the reference/target points.

BUG carried forward unchanged (per instructions -- not silently fixed):
  The "Copy?" Yes/No prompt (sCopy) is read and remembered between runs,
  but its value is NEVER read again anywhere in the routine -- the
  `TransformObjects(..., copy=True)` call is hard-coded to always copy,
  regardless of what the user answered. The prompt is therefore inert in
  the original .rvb. This port reproduces that behavior exactly (prompt
  shown, answer stored, but ignored) rather than silently "fixing" it.
  If you actually want a non-copy in-place orient, remove the hard-coded
  `True` below and wire `copy_answer` in.

The `Rhino.AddAlias` / `Rhino.AddStartupScript` lines at the end of the
.rvb only make sense for the legacy RVB alias-loading mechanism and have
no equivalent need in a Script Editor Python file (you just open and run
it directly), so they are omitted here.

API notes verified live against the mcneel/rhinoscriptsyntax GitHub
source (raw.githubusercontent.com/mcneel/rhinoscriptsyntax/master/Scripts/
rhinoscript/*.py) on this date, not from memory:
  - rs.VectorCreate, rs.VectorUnitize, rs.PointArrayClosestPoint and
    rs.XformRotation1(plane_from, plane_to) all exist in rhinoscriptsyntax
    with the same argument order as their old Rhino.* COM equivalents.
  - rs.CurveSurfaceIntersection returns a list of tuples where index [1]
    is the point on the *first* curve argument for a Point-type event --
    this matches the original VBScript's use of `aInt(i, 1)`.
  - There is no `Pt2Str` in modern rhinoscriptsyntax (it was dropped), so
    the "W<x>,<y>,<z>" world-coordinate command-line point syntax needed
    for feeding `_Rotate3D` is built manually here with full float
    precision (repr-based) instead.
"""

import rhinoscriptsyntax as rs


def _pt_to_world_string(pt):
    """Format a 3D point as a Rhino command-line world-coordinate token,
    e.g. 'W1.23456789,2,0'. Equivalent to the old Rhino.Pt2Str(pt, , True)
    call used with the 'W' prefix in the original script."""
    return "W{0!r},{1!r},{2!r}".format(pt.X, pt.Y, pt.Z)


def remap_to_plane(object_ids, plane1, plane2):
    """Copy-transform object_ids from plane1 to plane2. Returns new ids."""
    xform = rs.XformRotation1(plane1, plane2)
    if xform is None:
        return None
    return rs.TransformObjects(object_ids, xform, True)  # True = copy


def orient_crv_2pt():
    obj_ids = rs.GetObjects("Select objects to orient", preselect=True, select=True)
    if not obj_ids:
        return

    # Kept for parity with the original prompt; see BUG note in module
    # docstring -- this answer is intentionally unused below, exactly as
    # in the original .rvb.
    copy_answer = rs.GetString("Copy?", "Yes", ["Yes", "No"])
    if copy_answer is None:
        return

    base_pts = rs.GetPoints(draw_lines=True, message1="Set first base point",
                             message2="Set second base point", max_points=2)
    if not base_pts or len(base_pts) < 2:
        return

    target_curve = rs.GetObject("Select target curve", rs.filter.curve)
    if target_curve is None:
        return

    ref_pt = rs.GetPointOnCurve(target_curve, "Set first target point")
    if ref_pt is None:
        return

    near_pt = rs.GetPointOnCurve(
        target_curve, "Set a point on the curve near the desired target point")
    if near_pt is None:
        return

    rs.EnableRedraw(False)
    try:
        dist = rs.Distance(base_pts[0], base_pts[1])

        param = rs.CurveClosestPoint(target_curve, ref_pt)
        curve_plane = rs.CurveFrame(target_curve, param)  # noqa: F841 (kept for parity; unused downstream, same as original)

        sphere_id = rs.AddSphere(ref_pt, dist)
        intersections = rs.CurveSurfaceIntersection(target_curve, sphere_id)
        rs.DeleteObject(sphere_id)

        candidates = []
        if intersections:
            for event in intersections:
                candidates.append(event[1])

        if not candidates:
            print("Orient2ptCrv: sphere did not intersect the target curve -- aborted.")
            return

        idx = rs.PointArrayClosestPoint(candidates, near_pt)
        target_pt = candidates[idx]

        target_pt_str = _pt_to_world_string(target_pt)
        ref_pt_str = _pt_to_world_string(ref_pt)

        vec_base = rs.VectorUnitize(rs.VectorCreate(base_pts[1], base_pts[0]))
        vec_targ = rs.VectorUnitize(rs.VectorCreate(target_pt, ref_pt))
        if vec_base is None or vec_targ is None:
            print("Orient2ptCrv: base or target points are coincident -- aborted.")
            return

        base_plane = rs.PlaneFromNormal(base_pts[0], vec_base)
        targ_plane = rs.PlaneFromNormal(target_pt, vec_targ)

        new_ids = remap_to_plane(obj_ids, base_plane, targ_plane)
    finally:
        rs.EnableRedraw(True)

    if new_ids:
        rs.UnselectAllObjects()
        rs.SelectObjects(new_ids)
        cmd = "_Rotate3D {0} {1}".format(ref_pt_str, target_pt_str)
        rs.Command(cmd, False)


if __name__ == "__main__":
    orient_crv_2pt()
