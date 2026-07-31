"""
FilletNonPlanar.py

Python 3 (CPython) port of FilletNonPlanar.rvb, for Rhino 8's Script
Editor (ScriptEditor command, run with F5). Not for the legacy
RunPythonScript/IronPython 2 engine.

Original by Pascal Golay (McNeel), 2011-11-07.

Fillets two curves that are NOT coplanar: a best-fit plane is
constructed from the two curve tangents near the pick region, both
curves are flattened onto that plane, a normal 2D fillet arc is built
between the flattened curves, and the arc is then "un-flattened" back
into 3D by reprojecting its cut points and end tangents against the
real 3D curves, using the fillet-plane grips to reshape the arc as a
non-planar (but still smooth) transition.

Function/API mappings verified 2026 against mcneel/rhinoscriptsyntax
GitHub source (rhino-8.x branch) via WebFetch this session:
  - rs.GetCurveObject returns a 6-tuple: (id, preselected, selmethod,
    point, curve_parameter, viewname).
  - rs.TransformObject(object_id, matrix, copy=False) - copy=True
    creates a new transformed copy and leaves the original untouched
    (used here to flatten a copy while keeping the real 3D curve for
    later re-trimming).
  - rs.LineLineIntersection(lineA, lineB) returns a 2-tuple
    (point_on_lineA, point_on_lineB) - NOT a single point, and there is
    no "bounded/unbounded" flag (the legacy VBScript 3rd argument no
    longer exists; the lines are always treated as infinite).
  - rs.MatchObjectAttributes(target_ids, source_id) - target(s) first,
    source second. (Confirmed from source; easy to get backwards.)
  - rs.SplitCurve(curve_id, parameter, delete_input=True) accepts a
    single parameter (not just a list) and deletes/replaces curve_id
    by default - matches the original's reliance on that default.
  - rs.ObjectGripLocation(object_id, index, point=None) is a get/set:
    passing point moves grip `index` to that location.
  - rs.CurveCurveIntersection(curveA, curveB, tolerance) accepts a raw
    Rhino.Geometry.Curve object for curveB (not just a document guid) -
    rhinoscriptsyntax's internal coercecurve() special-cases
    isinstance(id, Rhino.Geometry.Curve). Used below to intersect a
    curve against an in-memory probe LineCurve without ever adding that
    probe to the document.

Real gap found, and how it's handled:
  There is NO rs.LineCurveIntersection in modern rhinoscriptsyntax
  (confirmed absent from the entire GitHub source tree, not just
  undocumented) - the legacy VBScript relied on it to project the flat
  2D fillet's cut points back onto the real 3D input curves along the
  fillet plane's normal. This port replaces it with
  probe_line_curve_intersection() below: a temporary
  Rhino.Geometry.LineCurve, built long enough to span the curve's own
  bounding-box diagonal in both directions (never added to the
  document), intersected via rs.CurveCurveIntersection. The original's
  probe line was only 1 unit long (exactly `vec_dir`, a unit normal) in
  each direction pair, which only works if the 3D curve happens to
  pass within 1 unit of the fillet plane - this port's longer probe is
  more robust and is the single functional improvement made here.

Other deviations, all noted inline where they occur:
  - A missing `ObjDir = ...` bug class is not present in this script,
    but a different one is: the original computed a `Line2` from
    `ftPts(Ubound(ftPts))`, a 6-element array whose last element is a
    Z-axis *vector*, not a point - it is immediately overwritten by a
    correct assignment on the next line, so the bug is silent and dead
    in practice. This port only implements the corrected, actually-used
    version (fillet curve's own start/end points), never the dead one.
  - AutoPlane's original CurveClosestPoint calls looked mismatched
    (calling CurveClosestPoint on curve0 using a point that
    CurveClosestObject returned as being on curve1, or vice versa,
    depending on how the legacy API ordered its return tuple). This
    port uses the modern, verified rs.CurveClosestObject return order -
    (closest_object_id, point_on_other_curve, point_on_test_curve) -
    and matches each point to the correct curve explicitly.
  - Radius memory: the original used a VBScript-level `Private oldrad`
    variable, which persists across repeated runs of the same loaded
    script for the life of the Rhino session. The direct Python
    equivalent of "remember a value across separate script executions
    in the same session" is `scriptcontext.sticky` (a persistent dict),
    used here instead of a plain module global, which would reset on
    every run.
  - Debug-only `rs.ObjectColor` calls in the original (coloring sCrv2
    magenta and sFt blue right before a LineCurveIntersection call)
    were diagnostic scaffolding, not functional; they are dropped here.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino


def get_crv_end(curve_id, t):
    """0 = the pick parameter t is nearer the curve's start, 1 = nearer its end."""
    dom = rs.CurveDomain(curve_id)
    if abs(t - dom[0]) > abs(t - dom[1]):
        return 1
    return 0


def delete_curve_end(crv_pair, int_end):
    """Given the two pieces produced by splitting a curve, deletes one
    and returns the id of the other: always keeps the piece with the
    lower parameter range (the "earlier" piece, i.e. the part of the
    original curve away from the fillet cut), matching how this script
    always calls it with int_end=1."""
    dom1 = rs.CurveDomain(crv_pair[0])
    dom2 = rs.CurveDomain(crv_pair[1])
    if dom1[1] < dom2[1]:
        if int_end == 1:
            rs.DeleteObject(crv_pair[1])
            return crv_pair[0]
        else:
            rs.DeleteObject(crv_pair[0])
            return crv_pair[1]
    else:
        if int_end == 1:
            rs.DeleteObject(crv_pair[0])
            return crv_pair[1]
        else:
            rs.DeleteObject(crv_pair[1])
            return crv_pair[0]


def auto_plane(curve_ids):
    """Best-fit plane through the average of the two curves' closest
    points to each other, and the tangent directions of each curve at
    that region - i.e. a plane that roughly contains both curves'
    local tangent directions near the fillet."""
    result = rs.CurveClosestObject(curve_ids[0], [curve_ids[1]])
    if result is None:
        return None
    _closest_id, pt_on_other, pt_on_test = result

    av_pt = (
        (pt_on_other.X + pt_on_test.X) / 2.0,
        (pt_on_other.Y + pt_on_test.Y) / 2.0,
        (pt_on_other.Z + pt_on_test.Z) / 2.0,
    )

    t1 = rs.CurveClosestPoint(curve_ids[0], pt_on_test)
    t2 = rs.CurveClosestPoint(curve_ids[1], pt_on_other)

    p1 = rs.PointAdd(av_pt, rs.CurveTangent(curve_ids[0], t1))
    p2 = rs.PointAdd(av_pt, rs.CurveTangent(curve_ids[1], t2))

    return rs.PlaneFitFromPoints([av_pt, p1, p2])


def probe_line_curve_intersection(curve_id, base_point, direction, tolerance):
    """Finds where an extended probe line through base_point, along
    direction, crosses curve_id. Returns (point, parameter) or None.
    See module docstring: this replaces the no-longer-existing
    rs.LineCurveIntersection."""
    crv_obj = sc.doc.Objects.Find(curve_id)
    if crv_obj is None:
        return None
    bbox = crv_obj.Geometry.GetBoundingBox(True)
    diag = bbox.Diagonal.Length
    reach = max(diag * 4.0, 10.0)

    dir_unit = rs.VectorUnitize(direction)
    if dir_unit is None:
        return None
    p_start = rs.PointAdd(base_point, rs.VectorScale(dir_unit, -reach))
    p_end = rs.PointAdd(base_point, rs.VectorScale(dir_unit, reach))
    probe = Rhino.Geometry.LineCurve(p_start, p_end)

    events = rs.CurveCurveIntersection(curve_id, probe, tolerance)
    if not events:
        return None
    evt = events[0]
    return evt[1], evt[5]  # point on curve_id, parameter on curve_id


def fillet_non_planar():
    old_rad = sc.sticky.get("FilletNonPlanar_oldrad", 1.0)
    dbl_rad = rs.GetReal("Fillet radius.", old_rad)
    if dbl_rad is None:
        return
    sc.sticky["FilletNonPlanar_oldrad"] = dbl_rad

    flip1 = False
    flip2 = False

    pick1 = rs.GetCurveObject("Select the first curve near the end to fillet.", False)
    if pick1 is None:
        return
    crv1_id, _presel1, _selm1, pick_pt1, pick_t1, _view1 = pick1

    line_array1 = None
    if rs.IsLine(crv1_id):
        line_array1 = (rs.CurveStartPoint(crv1_id), rs.CurveEndPoint(crv1_id))

    if get_crv_end(crv1_id, pick_t1) == 0:
        rs.ReverseCurve(crv1_id)
        flip1 = True

    pick2 = rs.GetCurveObject("Select the second curve near the end to fillet.", False)
    if pick2 is None:
        return
    crv2_id, _presel2, _selm2, pick_pt2, pick_t2, _view2 = pick2

    if get_crv_end(crv2_id, pick_t2) == 0:
        rs.ReverseCurve(crv2_id)
        flip2 = True

    line_array2 = None
    if rs.IsLine(crv2_id):
        line_array2 = (rs.CurveStartPoint(crv2_id), rs.CurveEndPoint(crv2_id))

    rs.EnableRedraw(False)

    plane = auto_plane((crv1_id, crv2_id))
    if plane is None:
        rs.EnableRedraw(True)
        if flip1:
            rs.ReverseCurve(crv1_id)
        if flip2:
            rs.ReverseCurve(crv2_id)
        rs.Print("Could not fit a fillet plane through the selected curves.")
        return

    vec_dir = plane.ZAxis

    xform = rs.XformPlanarProjection(plane)
    flat1 = rs.TransformObject(crv1_id, xform, True)
    flat2 = rs.TransformObject(crv2_id, xform, True)

    int_flat_events = rs.CurveCurveIntersection(flat1, flat2)

    if not int_flat_events:
        if rs.IsLine(flat1) and rs.IsLine(flat2):
            tl1 = (rs.CurveStartPoint(flat1), rs.CurveEndPoint(flat1))
            tl2 = (rs.CurveStartPoint(flat2), rs.CurveEndPoint(flat2))
            ll_result = rs.LineLineIntersection(tl1, tl2)
            if ll_result is not None:
                int_flat_pt = rs.PlaneClosestPoint(plane, ll_result[0])
                temp1 = rs.AddLine(rs.CurveStartPoint(flat1), int_flat_pt)
                temp2 = rs.AddLine(rs.CurveStartPoint(flat2), int_flat_pt)
                rs.DeleteObjects((flat1, flat2))
                flat1, flat2 = temp1, temp2

    ft_pts = rs.CurveFilletPoints(flat1, flat2, dbl_rad, pick_pt1, pick_pt2)

    if ft_pts is None:
        rs.DeleteObjects((flat1, flat2))
        rs.EnableRedraw(True)
        if flip1:
            rs.ReverseCurve(crv1_id)
        if flip2:
            rs.ReverseCurve(crv2_id)
        rs.Print("Fillet failed. Curve ends may be too far apart for the chosen radius.")
        return

    base_pt1 = rs.EvaluateCurve(flat1, rs.CurveClosestPoint(flat1, pick_pt1))
    base_pt2 = rs.EvaluateCurve(flat2, rs.CurveClosestPoint(flat2, pick_pt2))
    ft_id = rs.AddFilletCurve(flat1, flat2, dbl_rad, base_pt1, base_pt2)

    if ft_id is None:
        rs.EnableRedraw(True)
        if flip1:
            rs.ReverseCurve(crv1_id)
        if flip2:
            rs.ReverseCurve(crv2_id)
        rs.Print("Fillet failed. Curve ends may be too far apart for the chosen radius.")
        return

    # bump the fillet arc up to degree 3 so it has at least 4 control points
    rs.UnselectAllObjects()
    rs.SelectObject(ft_id)
    rs.Command("_NoEcho _ChangeDegree 3", False)

    rs.DeleteObjects((flat1, flat2))

    tolerance = rs.UnitAbsoluteTolerance()

    line1 = (rs.CurveStartPoint(ft_id), rs.PointAdd(rs.CurveStartPoint(ft_id), vec_dir))
    line2 = (rs.CurveEndPoint(ft_id), rs.PointAdd(rs.CurveEndPoint(ft_id), vec_dir))

    if rs.IsLine(crv1_id):
        ll1 = rs.LineLineIntersection(line1, line_array1)
        int_pt1 = ll1[1] if ll1 is not None else None
        int_par1 = rs.CurveClosestPoint(crv1_id, int_pt1) if int_pt1 is not None else None
    else:
        probe1 = probe_line_curve_intersection(crv1_id, line1[0], vec_dir, tolerance)
        if probe1 is None:
            int_pt1, int_par1 = None, None
        else:
            int_pt1, int_par1 = probe1

    if rs.IsLine(crv2_id):
        ll2 = rs.LineLineIntersection(line2, line_array2)
        int_pt2 = ll2[1] if ll2 is not None else None
        int_par2 = rs.CurveClosestPoint(crv2_id, int_pt2) if int_pt2 is not None else None
    else:
        probe2 = probe_line_curve_intersection(crv2_id, line2[0], vec_dir, tolerance)
        if probe2 is None:
            int_pt2, int_par2 = None, None
        else:
            int_pt2, int_par2 = probe2

    if int_pt1 is None or int_pt2 is None:
        rs.EnableRedraw(True)
        if flip1:
            rs.ReverseCurve(crv1_id)
        if flip2:
            rs.ReverseCurve(crv2_id)
        rs.Print("Could not project the fillet ends back onto the original curves.")
        return

    a_split1 = rs.SplitCurve(crv1_id, int_par1)
    if a_split1:
        if len(a_split1) > 1:
            crv1_id = delete_curve_end(a_split1, 1)
        else:
            crv1_id = a_split1[0]
    else:
        if rs.IsLine(crv1_id):
            temp = rs.AddLine(line_array1[0], int_pt1)
            rs.MatchObjectAttributes(temp, crv1_id)
            rs.DeleteObject(crv1_id)
            crv1_id = temp

    a_split2 = rs.SplitCurve(crv2_id, int_par2)
    if a_split2:
        if len(a_split2) > 1:
            crv2_id = delete_curve_end(a_split2, 1)
        else:
            crv2_id = a_split2[0]
    else:
        if rs.IsLine(crv2_id):
            temp = rs.AddLine(line_array2[0], int_pt2)
            rs.MatchObjectAttributes(temp, crv2_id)
            rs.DeleteObject(crv2_id)
            crv2_id = temp

    vec_tan1 = rs.CurveTangent(crv1_id, rs.CurveDomain(crv1_id)[1])
    vec_tan2 = rs.CurveTangent(crv2_id, rs.CurveDomain(crv2_id)[1])

    ft_cv = rs.CurvePoints(ft_id)
    bound = len(ft_cv) - 1

    dist1 = rs.Distance(ft_cv[0], ft_cv[1])
    dist2 = rs.Distance(ft_cv[bound], ft_cv[bound - 1])

    rs.EnableObjectGrips(ft_id, True)

    rs.ObjectGripLocation(ft_id, 0, rs.CurveEndPoint(crv1_id))
    targ1 = rs.PointAdd(rs.CurveStartPoint(ft_id), rs.VectorScale(vec_tan1, dist1))
    rs.ObjectGripLocation(ft_id, 1, targ1)

    rs.ObjectGripLocation(ft_id, bound, rs.CurveEndPoint(crv2_id))
    targ2 = rs.PointAdd(rs.CurveEndPoint(ft_id), rs.VectorScale(vec_tan2, dist2))
    rs.ObjectGripLocation(ft_id, bound - 1, targ2)

    # if the fillet has more than 4 points (included angle < 90), fit a
    # plane through the end/tangent points and pull the interior grips
    # onto it, so the middle of the arc doesn't wander off-plane
    if bound > 3:
        loc0 = targ1
        loc1 = rs.CurveStartPoint(ft_id)
        loc2 = targ2
        loc3 = rs.CurveEndPoint(ft_id)
        test_plane = rs.PlaneFitFromPoints((loc0, loc1, loc2, loc3))
        if test_plane is not None:
            for i in range(2, bound - 1):
                current = rs.ObjectGripLocation(ft_id, i)
                rs.ObjectGripLocation(ft_id, i, rs.PlaneClosestPoint(test_plane, current))

    rs.EnableObjectGrips(ft_id, False)
    if flip1:
        rs.ReverseCurve(crv1_id)
    if flip2:
        rs.ReverseCurve(crv2_id)
    rs.SelectObject(ft_id)
    rs.EnableRedraw(True)


if __name__ == "__main__":
    fillet_non_planar()
