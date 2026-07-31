"""
CurveSymmetryAuto.py

Port of CurveSymmetryAuto.rvb (Pascal Golay, McNeel — legacy RhinoScript/
VBScript, version Sunday, March 23, 2008) to Python 3 for Rhino 8's
Script Editor (CPython3 mode). Run via ScriptEditor -> open this file ->
F5. NOT for RunPythonScript (that invokes the IronPython 2 engine).

What it does (unchanged from the original): pick an open, non-polycurve
curve near the end you want to KEEP, choose (or auto-detect) a symmetry
plane, and the script rebuilds the curve so it is exactly symmetric about
that plane, discarding/mirroring control points on the far side. Arcs and
lines are handled as a simple point-reflection special case; all other
curve types are rebuilt control-point-by-control-point as a new NURBS (or
polyline) curve. The original curve is deleted and the new curve inherits
its color/layer/linetype/print settings and group membership.

This is the largest and most algorithmically dense of the 5 ported
scripts. Every rhinoscriptsyntax function name below was checked against
the source (github.com/mcneel/rhinoscriptsyntax, rhino-8.x branch,
2026-07-31) rather than assumed; anything genuinely uncertain is flagged
with a TODO.

Porting notes / deliberate simplifications:
- rs.GetCurveObject(message, preselect, select) returns a 6-tuple
  (id, was_preselected, selection_method, selection_point,
  curve_parameter, view_name) — confirmed against
  Scripts/rhinoscript/selection.py. This maps directly onto the
  original's aCrv(0)/aCrv(2)/aCrv(4) array indexing (curve id / selection
  method / pick parameter).
- rs.XformWorldToCPlane / rs.XformCPlaneToWorld both exist in
  rhinoscriptsyntax (Scripts/rhinoscript/transformation.py) and are used
  directly, matching the original 1:1.
- Plane objects returned by rhinoscriptsyntax (rs.ViewCPlane, etc.) are
  real Rhino.Geometry.Plane objects with .Origin/.XAxis/.YAxis/.ZAxis
  properties, NOT 4-element indexable arrays like VBScript's RhinoScript
  plane representation. Every `SymPlane(3)` (the plane's normal/Z-axis in
  the original) below is `sym_plane.ZAxis`.
- rs.AddNurbsCurve (lowercase "urbs") is the correct rhinoscriptsyntax
  name for what the original calls `Rhino.AddNURBSCurve` — confirmed
  against Scripts/rhinoscript/curve.py.
- Sticky default symmetry-location choice (sOldSymPlane in the original)
  reproduced via `scriptcontext.sticky`.
- Three helper subs in the original — `DrawVector`, `DrawPlaneFrame`, and
  `CplaneToWorldPts` — are test/debug-only utilities never called from
  any live code path in the script (DrawVector and DrawPlaneFrame are
  only referenced from commented-out `'TEST` lines; CplaneToWorldPts is
  never referenced at all). None are ported; omitting them has no effect
  on behavior.
- `lenDiag` (a bounding-box diagonal length) is computed in the original
  right after the bounding-box call but is never subsequently used
  anywhere in the script — genuinely dead code. Not ported.
- TODO: unverified — RhinoCommon/pythonnet operator overloads are not
  relied on here (all point/vector math below goes through explicit
  rs.VectorCreate/VectorAdd/PointAdd/VectorScale/VectorReverse calls,
  matching the original), so this script does not depend on that
  assumption the way Distribute.py's port does.
"""

import math

import rhinoscriptsyntax as rs
import scriptcontext as sc


def average_points(pts):
    x = sum(p[0] for p in pts) / len(pts)
    y = sum(p[1] for p in pts) / len(pts)
    z = sum(p[2] for p in pts) / len(pts)
    return (x, y, z)


def is_string_in_array(item, arr):
    item_l = item.lower()
    for s in arr:
        if s.lower() == item_l:
            return True
    return False


def is_integer_even(value):
    return value % 2 == 0


def get_curve_end(crv, param):
    domain = rs.CurveDomain(crv)
    len1 = rs.CurveLength(crv, sub_domain=(domain[0], param))
    len2 = rs.CurveLength(crv, sub_domain=(param, domain[1]))
    return 0 if len1 < len2 else 1


def get_auto_sym_plane_dir(crv, s_dir):
    crnt_plane = rs.ViewCPlane()

    start = rs.CurveStartPoint(crv)
    end = rs.CurveEndPoint(crv)
    mid = average_points([start, end])

    mid_plane = rs.XformWorldToCPlane(mid, crnt_plane)
    end_plane = rs.XformWorldToCPlane(end, crnt_plane)

    pt1 = rs.XformCPlaneToWorld((mid_plane[0], mid_plane[1], 0), crnt_plane)

    if s_dir == "Y":
        pt2 = rs.XformCPlaneToWorld((mid_plane[0] + 1, mid_plane[1], 0), crnt_plane)
    elif s_dir == "X":
        pt2 = rs.XformCPlaneToWorld((mid_plane[0], mid_plane[1] + 1, 0), crnt_plane)
    else:
        pt1 = rs.XformCPlaneToWorld((mid_plane[0], mid_plane[1], 0), crnt_plane)
        pt2 = rs.XformCPlaneToWorld((end_plane[0], end_plane[1], 0), crnt_plane)

    vec = rs.VectorCreate(pt2, pt1)
    result = rs.PlaneFromNormal(mid, vec)

    rs.AddPlaneSurface(result, 10, 10)

    return result


def get_sym_cv(crv, sym_plane, crv_end, cv_weights):
    cv = list(rs.CurvePoints(crv))
    cv_weights = list(cv_weights)

    even = is_integer_even(len(cv))

    if not even:
        int_mid = (len(cv) - 1) // 2 - 1
    else:
        int_mid = (len(cv) - 2) // 2

    tol = 10 * rs.UnitAbsoluteTolerance()

    if crv_end == 1:  # curve pick was at the end point: work from the other end
        cv.reverse()
        cv_weights.reverse()

    normal = sym_plane.ZAxis

    test_pt = cv[0]
    targ_pt = rs.PlaneClosestPoint(sym_plane, test_pt)
    test_vec = rs.VectorCreate(test_pt, targ_pt)
    int_dir = rs.IsVectorParallelTo(test_vec, normal)

    base_cv = [(cv[0], cv_weights[0], False)]

    # the fixed end point, mirrored across the symmetry plane
    anchor = base_cv[0]
    targ_pt = rs.PlaneClosestPoint(sym_plane, anchor[0])
    reflect_vec = rs.VectorScale(
        rs.VectorReverse(rs.VectorCreate(anchor[0], targ_pt)), 2
    )
    end_pt_loc = rs.PointAdd(anchor[0], reflect_vec)
    end_pt = (end_pt_loc, cv_weights[0], False)

    sym_cv = []
    loop_gate = len(cv) - 3  # curve has more than 3 control points

    if loop_gate > 0:
        for i in range(1, int_mid + 1):
            k = False
            test_pt = cv[i]

            if abs(rs.DistanceToPlane(sym_plane, test_pt)) < tol:
                k = True  # this CV is essentially on the mirror plane

            targ_pt = rs.PlaneClosestPoint(sym_plane, test_pt)
            test_vec = rs.VectorCreate(test_pt, targ_pt)

            same_side = rs.IsVectorParallelTo(test_vec, normal) == int_dir

            if same_side and not k:
                base_cv.append((cv[i], cv_weights[i], k))
            elif (not same_side) and not k:
                temp_vec = rs.VectorReverse(test_vec)
                temp_pt = rs.PointAdd(targ_pt, temp_vec)
                base_cv.append((temp_pt, cv_weights[i], k))
                test_vec = temp_vec
            # if k is True, the point is dropped from base_cv entirely,
            # matching the original (both branches above require k=False).

            if not k:
                temp_vec = rs.VectorReverse(test_vec)
                sym_cv.append((rs.PointAdd(targ_pt, temp_vec), cv_weights[i], k))

    mid_pt = None
    if not even:
        idx = int_mid + 1
        temp = cv[idx]
        targ_pt = rs.PlaneClosestPoint(sym_plane, temp)
        mid_pt = (targ_pt, cv_weights[idx], False)

    if len(sym_cv) > 1:
        sym_cv.reverse()

    if not even:
        if len(cv) > 3:
            result = base_cv + [mid_pt] + sym_cv + [end_pt]
        else:
            result = base_cv + [mid_pt] + [end_pt]
    else:
        result = base_cv + sym_cv + [end_pt]

    return result


def curve_symmetry():
    while True:
        pick = rs.GetCurveObject("Select curve near the end to keep", False, True)
        if not pick:
            return

        crv = pick[0]

        if rs.IsPolycurve(crv) or rs.IsCurveClosed(crv):
            rs.MessageBox(
                "Polycurves and closed curves are not supported.\n"
                "Please select another curve or Esc to cancel."
            )
            continue
        break

    selection_method = pick[2]
    param = pick[4]

    # If the curve was not selected by a direct mouse click (e.g. window
    # or crossing selection, or SelAll), assume the start point is the
    # end to keep.
    if selection_method != 1:
        crv_end = 0
    else:
        crv_end = get_curve_end(crv, param)

    crnt_plane = rs.ViewCPlane()

    if not rs.IsArc(crv) and not rs.IsLine(crv):

        sym_planes = ("Auto", "XAuto", "YAuto", "User", "3pt")
        weights = rs.CurveWeights(crv)
        old_sym_plane = sc.sticky.get("CurveSymmetryAuto_OldSymPlane", "Auto")
        sym_plane_choice = rs.GetString("Symmetry location", old_sym_plane, sym_planes)

        if sym_plane_choice is None:
            return
        if is_string_in_array(sym_plane_choice, sym_planes):
            sc.sticky["CurveSymmetryAuto_OldSymPlane"] = (
                sym_plane_choice[0].upper() + sym_plane_choice[1:].lower()
            )

        choice = sym_plane_choice.upper()
        sym_plane = None

        if choice == "AUTO":
            sym_plane = get_auto_sym_plane_dir(crv, "NONE")
            if not sym_plane:
                return
        elif choice == "XAUTO":
            sym_plane = get_auto_sym_plane_dir(crv, "X")
            if not sym_plane:
                return
        elif choice == "YAUTO":
            sym_plane = get_auto_sym_plane_dir(crv, "Y")
            if not sym_plane:
                return
        elif choice == "USER":
            rs.EnableRedraw(True)
            axis_pts = rs.GetPoints(True, True, "First point", "Second point", 2)
            if not axis_pts or len(axis_pts) != 2:
                rs.EnableRedraw(True)
                return
            rs.EnableRedraw(False)

            axis1_plane = rs.XformWorldToCPlane(axis_pts[0], crnt_plane)
            z_axis_plane_pt = (axis1_plane[0], axis1_plane[1], axis1_plane[2] + 1)
            z_axis_pt = rs.XformCPlaneToWorld(z_axis_plane_pt, crnt_plane)

            sym_plane = rs.PlaneFromPoints(axis_pts[0], axis_pts[1], z_axis_pt)
            if not sym_plane:
                return
        elif choice == "3PT":
            rs.EnableRedraw(True)
            two_pts = rs.GetPoints(True, False, "Plane origin", "Plane X axis", 2)
            if not two_pts:
                return

            temp_line = rs.AddLine(two_pts[0], two_pts[1])
            y_pt = None
            if len(two_pts) == 2:
                y_pt = rs.GetPoint("Plane Y axis", two_pts[0])
                rs.DeleteObject(temp_line)
                if not y_pt:
                    return

            sym_plane = rs.PlaneFromPoints(two_pts[0], two_pts[1], y_pt)
            if not sym_plane:
                return
        else:
            rs.EnableRedraw(True)
            return

        cv_data = get_sym_cv(crv, sym_plane, crv_end, weights)

        if not cv_data:
            rs.MessageBox("Error encountered, the curve was not changed.")
            rs.EnableRedraw(True)
            return

        cv_loc = [item[0] for item in cv_data]
        cv_weights_out = [item[1] for item in cv_data]

        degree = rs.CurveDegree(crv)
        new_crv = None

        if rs.IsPolyline(crv):
            new_crv = rs.AddPolyline(cv_loc)
        else:
            if degree > len(cv_loc) - 1:
                degree = len(cv_loc) - 1

            ub = len(cv_loc) - 1
            num = (ub + degree) - 1

            knots = [0.0] * (num + 1)
            for n in range(degree):
                knots[n] = 0

            r = 1
            for n in range(degree, num - degree + 1):
                knots[n] = r
                r += 1

            for n in range(num - degree + 1, num + 1):
                knots[n] = r

            new_crv = rs.AddNurbsCurve(cv_loc, knots, degree, cv_weights_out)

    else:  # arc or line: simple point-reflection about the curve midpoint
        rs.EnableRedraw(True)
        sym_pt = rs.GetPointOnCurve(crv, "Curve midpoint")
        rs.EnableRedraw(False)

        if not sym_pt:
            rs.EnableRedraw(True)
            return

        new_crv = None

        if rs.IsLine(crv):
            if crv_end == 0:
                vec1 = rs.VectorReverse(rs.VectorCreate(rs.CurveStartPoint(crv), sym_pt))
                pt2 = rs.PointAdd(sym_pt, vec1)
                new_crv = rs.AddLine(rs.CurveStartPoint(crv), pt2)
            else:
                vec1 = rs.VectorReverse(rs.VectorCreate(rs.CurveEndPoint(crv), sym_pt))
                pt2 = rs.PointAdd(sym_pt, vec1)
                new_crv = rs.AddLine(rs.CurveEndPoint(crv), pt2)

        elif rs.IsArc(crv):
            cen = rs.ArcCenterPoint(crv)
            radius = rs.ArcRadius(crv)

            vec1 = rs.VectorCreate(rs.CurveStartPoint(crv), cen)
            vec2 = rs.VectorCreate(rs.CurveMidPoint(crv), cen)

            if crv_end == 0:
                ang = rs.Angle2((cen, rs.CurveStartPoint(crv)), (cen, sym_pt))
                dbl_ang = ang[0]
                arc_plane = rs.PlaneFromFrame(cen, vec1, vec2)
            else:
                ang = rs.Angle2((cen, sym_pt), (cen, rs.CurveEndPoint(crv)))
                dbl_ang = ang[0]
                arc_plane = rs.PlaneFromFrame(cen, vec2, vec1)

            new_crv = rs.AddArc(arc_plane, radius, 2 * dbl_ang)
        else:
            return

    if new_crv:
        if rs.ObjectGripsOn(crv):
            rs.EnableObjectGrips(new_crv, True)

        color = rs.ObjectColor(crv)
        layer = rs.ObjectLayer(crv)
        linetype = rs.ObjectLinetype(crv)
        print_width = rs.ObjectPrintWidth(crv)
        print_color = rs.ObjectPrintColor(crv)
        groups = rs.ObjectGroups(crv)

        if not rs.IsLine(new_crv):
            rs.ObjectColor(new_crv, color)
            rs.ObjectLayer(new_crv, layer)
            rs.ObjectLinetype(new_crv, linetype)
            rs.ObjectPrintWidth(new_crv, print_width)
            rs.ObjectPrintColor(new_crv, print_color)

        if groups:
            for g in groups:
                rs.AddObjectToGroup(new_crv, g)

        rs.DeleteObject(crv)
    else:
        rs.MessageBox("The curve was not changed.")

    rs.EnableRedraw(True)


if __name__ == "__main__":
    curve_symmetry()
