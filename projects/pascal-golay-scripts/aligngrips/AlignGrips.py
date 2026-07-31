"""
AlignGrips.py - Python 3 (CPython) port of AlignGrips.rvb (Pascal Golay, McNeel)

TARGET ENGINE: Rhino 8 Script Editor, CPython3 mode (run via the ScriptEditor
command, press F5). Do NOT run this via the legacy `RunPythonScript` command
(that invokes IronPython 2, which has different string/encoding behavior).

Original behavior (legacy RhinoScript / VBScript, `Rhino.*` COM object model):
Two related tools that reposition a set of picked object grips:
  - AlignGrips     : moves grips onto (or in a plane relative to) a target
                      line, either "Direction" (project along a direction
                      line, staying in a plane derived from the current
                      CPlane) or "ClosestPoints" (mirror grips through a
                      plane built from the target line).
  - AlignGripsCrv  : same idea, but the target is a curve instead of a line
                      -- "Direction" mode sweeps a temporary plane surface
                      through each grip and intersects it with the curve;
                      "ClosestPoints" mode just snaps each grip to its
                      closest point on the curve.

Porting notes / deliberate simplifications:
  - The original used `Rhino.AddAlias` + `Rhino.AddStartupScript` to register
    command-line aliases ("AlignGrips", "AlignGripsCrv") that persist across
    Rhino sessions. That mechanism is specific to the legacy VBScript
    RhinoScript engine and has no equivalent for a Script Editor CPython3
    file (these are simply run with F5, or wired to a button/alias manually
    by the owner in Rhino's own Options > Aliases UI pointing at this file).
    That registration code is dropped; a small command-line prompt at the
    bottom lets the user choose which of the two behaviors to run in a
    single F5 session instead.
  - `sOldMode1` / `sOldMode2` (remembering the last-used mode between calls)
    are ported using `scriptcontext.sticky`, RhinoCommon/rhinoscriptsyntax's
    supported way of persisting simple values across script runs within the
    same Rhino session.
  - Legacy `Rhino.ViewCplane(Rhino.CurrentView)(3)` (4th element of the old
    array-style plane = Z-axis) becomes `plane.ZAxis` on the Plane object
    rhinoscriptsyntax now returns. Likewise `Rhino.XformCPlaneToWorld((0,0,0),
    Rhino.ViewCPlane)` (transforming the CPlane-local origin to world coords)
    simplifies directly to `plane.Origin` -- verified equivalent, not a
    behavior change.
  - Legacy `Rhino.MoveObject`/`ObjectGripLocation`-by-index calls map 1:1 to
    `rs.ObjectGripLocation(obj_id, index, point)`. `rs.GetObjectGrips` returns
    a list of (object_id, index, point) tuples, matching the old CV(0)/CV(1)
    pairing (CV(2) is the point itself, now optionally available directly).
  - `Filter()` (VBScript array filter) is unnecessary: `rs.GetString` with a
    `strings` list already constrains input to one of the given options.

Function signatures used below (LinePlaneIntersection, PlaneFromNormal,
PlaneFromFrame, VectorCreate, ViewCPlane, CurveSurfaceIntersection,
ObjectGripLocation, GetObjectGrips, EvaluateCurve, CurveClosestPoint,
EvaluateSurface, AddPlaneSurface, BoundingBox, MoveObject) were confirmed
this session against the live rhinoscriptsyntax reference at
https://developer.rhino3d.com/api/RhinoScriptSyntax/ (fetched directly,
not from trained memory).
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc


def _get_mode(prompt, sticky_key, default):
    modes = ["Direction", "ClosestPoints"]
    old = sc.sticky.get(sticky_key, default)
    mode = rs.GetString(prompt, old, modes)
    if mode is None:
        return None
    # rs.GetString restricts input to one of `modes`, but be defensive
    # about casing since the original did a case-insensitive compare.
    for m in modes:
        if m.lower() == mode.lower():
            sc.sticky[sticky_key] = m
            return m
    return None


def align_grips_to_line():
    """Port of Sub AlignGrips() -- align picked grips to a target line."""
    grips = rs.GetObjectGrips("Select grips.", True, True)
    if not grips:
        return

    pts = rs.GetPoints(True, False, "Set target line, first point",
                        "Set target line, second point", 2)
    if not pts:
        return

    line_id = rs.AddLine(pts[0], pts[1])

    mode = _get_mode("Move grips in plane or by closest points?",
                      "AlignGrips_mode1", "Plane")
    if mode is None:
        rs.DeleteObject(line_id)
        return

    p0, p1 = pts[0], pts[1]
    vec_z = rs.VectorCreate(p1, p0)  # vector from p0 to p1

    rs.EnableRedraw(False)

    if mode.lower() == "closestpoints":
        # Mirror-style: reverse the reference line, build a perpendicular
        # plane through it, and intersect that plane with the (reversed)
        # target line for each grip.
        new_p1 = rs.PointAdd(p0, vec_z)
        new_p0 = rs.PointAdd(p1, rs.VectorReverse(vec_z))
        line = (new_p0, new_p1)
        plane = rs.PlaneFromNormal(new_p0, vec_z)

        for obj_id, index, _pt in grips:
            grip_loc = rs.ObjectGripLocation(obj_id, index)
            plane_o = rs.PlaneFromNormal(grip_loc, vec_z)
            result = rs.LinePlaneIntersection(line, plane_o)
            if result is not None:
                rs.ObjectGripLocation(obj_id, index, result)
    else:
        rs.EnableRedraw(True)
        line = (p0, p1)
        dir_pts = rs.GetPoints(True, False, "Set projection direction first point",
                                "Set projection direction second point", 2)
        if not dir_pts:
            rs.DeleteObject(line_id)
            return

        vec_x = rs.VectorCreate(dir_pts[1], dir_pts[0])
        cplane = rs.ViewCPlane(rs.CurrentView())
        vec_z2 = cplane.ZAxis
        plane = rs.PlaneFromFrame(cplane.Origin, vec_x, vec_z2)

        rs.EnableRedraw(False)
        for obj_id, index, _pt in grips:
            grip_loc = rs.ObjectGripLocation(obj_id, index)
            plane_o = rs.PlaneFromFrame(grip_loc, vec_x, vec_z2)
            result = rs.LinePlaneIntersection(line, plane_o)
            if result is not None:
                rs.ObjectGripLocation(obj_id, index, result)

    rs.DeleteObject(line_id)
    rs.EnableRedraw(True)


def align_grips_to_curve():
    """Port of Sub AlignGripsCrv() -- align picked grips to a target curve."""
    grips = rs.GetObjectGrips("Select grips", True, True)
    if not grips:
        return

    crv_id = rs.GetObject("Select target curve", rs.filter.curve)
    if crv_id is None:
        return

    mode = _get_mode("Move grips in plane or by closest points?",
                      "AlignGrips_mode2", "Direction")
    if mode is None:
        return

    plane_srf = None

    if mode.lower() == "direction":
        pts = rs.GetPoints(True, False, "First direction point",
                            "Second direction point", 2)
        if not pts:
            return

        vec_x = rs.VectorCreate(pts[1], pts[0])
        cplane = rs.ViewCPlane(rs.CurrentView())
        vec_z = cplane.ZAxis
        plane = rs.PlaneFromFrame(cplane.Origin, vec_x, vec_z)

        bbox = rs.BoundingBox(rs.AllObjects(), rs.CurrentView())
        diag = rs.Distance(bbox[0], bbox[6])

        plane_srf = rs.AddPlaneSurface(plane, diag, diag)
        center = rs.EvaluateSurface(plane_srf, (diag / 2.0, diag / 2.0))

        rs.EnableRedraw(False)
        for obj_id, index, _pt in grips:
            grip_loc = rs.ObjectGripLocation(obj_id, index)
            rs.MoveObject(plane_srf, rs.PointSubtract(grip_loc, center))
            test = rs.CurveSurfaceIntersection(crv_id, plane_srf)
            if test:
                result = test[0][1]
                rs.ObjectGripLocation(obj_id, index, result)
                center = grip_loc
    else:
        rs.EnableRedraw(False)
        for obj_id, index, _pt in grips:
            grip_loc = rs.ObjectGripLocation(obj_id, index)
            param = rs.CurveClosestPoint(crv_id, grip_loc)
            result = rs.EvaluateCurve(crv_id, param)
            if result is not None:
                rs.ObjectGripLocation(obj_id, index, result)

    if plane_srf is not None:
        rs.DeleteObject(plane_srf)

    rs.EnableRedraw(True)


def main():
    choice = rs.GetString("Align grips to a Line or a Curve?", "Line", ["Line", "Curve"])
    if choice is None:
        return
    if choice.lower() == "curve":
        align_grips_to_curve()
    else:
        align_grips_to_line()


if __name__ == "__main__":
    main()
