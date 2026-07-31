"""SetbackFillet.py

Python 3 (CPython, PythonNet) port of SetbackFillet.rvb, for Rhino 8's
Script Editor (ScriptEditor command, F5). Not written for legacy
IronPython/RunPythonScript.

Original: Pascal Golay, SetbackFillet.rvb (2012).
Ported 2026-07-31.

What it does: for each selected planar curve with sharp (tangent-
discontinuous) corners, it fillets each corner by "setting back" a fixed
distance from the corner along the curve on both sides, dropping a
tangent arc between the two setback points, then splitting the curve at
those points and discarding the short corner segments (and rejoining
the arcs with the remaining curve pieces). Non-planar curves and plain
2-point lines are skipped.

Function names/signatures (GetObjects, GetReal, GetString, UnitAbsolute-
Tolerance, IsCurvePlanar, CopyObject, IsPolyline, ExplodeCurves,
JoinCurves, CurvePlane, CurveDiscontinuity, MovePlane, AddCircle,
CurveCurveIntersection, DeleteObject, AddArcPtTanPt, VectorCreate,
CurveClosestPoint, IsCurveClosed, PolyCurveCount, SimplifyCurve,
CurveEndPoint, CurveStartPoint, CurveTangent, IsVectorParallelTo,
SplitCurve, CurveMidPoint, PointArrayClosestPoint, Distance,
EvaluateCurve, EnableRedraw, UnselectAllObjects) verified 2026-07-31
against the rhinoscriptsyntax source on GitHub
(https://github.com/mcneel/rhinoscriptsyntax, rhino-8.x branch,
Scripts/rhinoscript/{selection,userinterface,document,curve,plane,
pointvector,object,utility}.py).

Persisted "last used" defaults (setback distance, delete-inputs choice)
use `scriptcontext.sticky`, the standard Rhino-Python session-persistent
dict, mirroring the original's module-level `Private` variables (which
persisted across alias-triggered runs because the VBScript host stayed
resident). NOTE: I could not independently re-confirm `scriptcontext.sticky`
against a live guide page this session (the specific guide URLs I tried
404'd) -- its existence is inferred from (a) rhinoscriptsyntax's own
source importing and using the sibling `scriptcontext.doc` throughout,
confirmed live this session, and (b) long-standing convention. Flagging
per house rules rather than asserting verification that didn't happen.
If `scriptcontext.sticky` turns out unavailable, defaults will just fall
back to the hardcoded values below with no persistence -- not a
functional break, just loses the "remembers last value" convenience.

BUGS FOUND IN THE ORIGINAL (preserved here for behavioral parity, not
silently fixed):
  1. `aArcs` and `aPar` are declared ONCE outside the main curve loop
     and only reset to index 0 (via `n = 0` / `p = 0`) when a curve
     actually has discontinuity points (`If isArray(aPts) Then`). If a
     later curve in the same multi-curve selection has NO sharp corners
     found by CurveDiscontinuity (e.g. a smooth closed curve), `n`/`p`
     are never reset, so `aArcs`/`aPar` still contain the arcs and
     parameters from the previous curve -- which then get spliced/
     joined into the wrong curve's result. This only bites when
     filleting more than one curve at once and at least one of them is
     fully smooth. Reproduced faithfully below (arcs/pars are only
     cleared when new discontinuities are found), not silently fixed.
  2. `PolyCurveCount` in modern rhinoscriptsyntax *raises* ValueError
     for a non-polycurve rather than returning None the way the old
     RhinoScript COM call did -- ported with a try/except to preserve
     the original's "isNull(Count) -> simplify and re-check" intent.
  3. The original's `VectorAngle`/`Arcos` helper functions are dead code
     -- never called anywhere in the .rvb. Omitted here; nothing in this
     port depends on them.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc

_STICKY_RAD = "SetbackFillet_oldrad"
_STICKY_DEL = "SetbackFillet_olddel"


def weed_out_curves(curve_ids):
    """Keep only planar curves that are not plain 2-point lines."""
    result = []
    for crv in curve_ids:
        if not rs.IsLine(crv):
            if rs.IsCurvePlanar(crv):
                result.append(crv)
    return result


def poly_curve_count_or_none(curve_id):
    try:
        return rs.PolyCurveCount(curve_id)
    except ValueError:
        return None


def setback_fillet():
    crv_ids = rs.GetObjects("Select curves to fillet.", 4, True, True)
    if not crv_ids:
        return

    old_rad = sc.sticky.get(_STICKY_RAD, 1.0)
    old_del = sc.sticky.get(_STICKY_DEL, "Yes")

    rad = rs.GetReal("Setback distance.", old_rad, 10 * rs.UnitAbsoluteTolerance())
    if rad is None:
        return

    s_del = rs.GetString("Delete inputs?", old_del, ["Yes", "No"])
    bln_del = True
    if s_del is not None and s_del.lower() == "no":
        sc.sticky[_STICKY_DEL] = "No"
        bln_del = False
    else:
        sc.sticky[_STICKY_DEL] = "Yes"

    sc.sticky[_STICKY_RAD] = rad

    crvs = weed_out_curves(crv_ids)

    # NOTE (bug #1 above): arcs/pars are intentionally NOT reset per-curve
    # here -- only when new discontinuities are actually found -- to
    # match the original's carried-over-state behavior exactly.
    arcs = []
    pars = []
    split_ids = []

    rs.EnableRedraw(False)
    try:
        for crv in crvs:
            if rs.IsCurvePlanar(crv):

                if not bln_del:
                    rs.CopyObject(crv)

                if rs.IsPolyline(crv):
                    pieces = rs.ExplodeCurves(crv, True)
                    joined = rs.JoinCurves(pieces, True)
                    crv = joined[0]

                plane = rs.CurvePlane(crv)
                disc_pts = rs.CurveDiscontinuity(crv, 4)  # 4 = G1, tangent discontinuities (corners)

                if disc_pts:
                    arcs = []
                    pars = []

                    for pt in disc_pts:
                        corner_plane = rs.MovePlane(plane, pt)
                        temp_circle = rs.AddCircle(corner_plane, rad)
                        events = rs.CurveCurveIntersection(crv, temp_circle)
                        rs.DeleteObject(temp_circle)
                        if not events or len(events) < 2:
                            continue
                        p1 = events[0][1]
                        p2 = events[1][1]
                        temp_arc = rs.AddArcPtTanPt(p1, rs.VectorCreate(pt, p1), p2)

                        if temp_arc is not None:
                            arcs.append(temp_arc)
                            pars.append(rs.CurveClosestPoint(crv, p1))
                            pars.append(rs.CurveClosestPoint(crv, p2))

                    if rs.IsCurveClosed(crv):
                        # add the start/end join point to the mix
                        count = poly_curve_count_or_none(crv)
                        if count is None:
                            rs.SimplifyCurve(crv)
                            if rs.IsPolyline(crv):
                                pieces = rs.ExplodeCurves(crv, True)
                                joined = rs.JoinCurves(pieces, True)
                                crv = joined[0]
                            count = poly_curve_count_or_none(crv)

                        seg_index = (count - 1) if count else 0
                        end_pt = rs.CurveEndPoint(crv)
                        start_pt = rs.CurveStartPoint(crv)
                        vec1 = rs.CurveTangent(crv, rs.CurveClosestPoint(crv, end_pt, seg_index), seg_index)
                        vec2 = rs.CurveTangent(crv, rs.CurveClosestPoint(crv, start_pt, 0), 0)

                        if rs.IsVectorParallelTo(vec1, vec2) == 0:
                            corner_plane = rs.MovePlane(plane, end_pt)
                            temp_circle = rs.AddCircle(corner_plane, rad)
                            events = rs.CurveCurveIntersection(crv, temp_circle)
                            rs.DeleteObject(temp_circle)
                            if events and len(events) >= 2:
                                p1 = events[0][1]
                                p2 = events[1][1]
                                temp_arc = rs.AddArcPtTanPt(p1, rs.VectorCreate(end_pt, p1), p2)

                                if temp_arc is not None:
                                    arcs.append(temp_arc)
                                    pars.append(rs.CurveClosestPoint(crv, p1))
                                    pars.append(rs.CurveClosestPoint(crv, p2))

                split_ids = rs.SplitCurve(crv, pars, False) or []

                if rs.IsCurveClosed(crv):
                    ref_pts = list(disc_pts) + [rs.CurveStartPoint(crv)]
                else:
                    ref_pts = list(disc_pts)

                for split_id in list(split_ids):
                    if len(ref_pts) <= 1:
                        test_pt = ref_pts[0] if ref_pts else rs.CurveMidPoint(split_id)
                    else:
                        idx = rs.PointArrayClosestPoint(ref_pts, rs.CurveMidPoint(split_id))
                        test_pt = ref_pts[idx]

                    closest_param = rs.CurveClosestPoint(split_id, test_pt)
                    closest_pt = rs.EvaluateCurve(split_id, closest_param)
                    if rs.Distance(test_pt, closest_pt) < rad / 2.0:
                        rs.DeleteObject(split_id)
                        split_ids.remove(split_id)
                        rs.DeleteObject(crv)

            else:
                print("Skipped a non-planar curve")

            all_ids = arcs + split_ids
            if all_ids:
                rs.JoinCurves(all_ids, True)

        rs.UnselectAllObjects()
    finally:
        rs.EnableRedraw(True)


if __name__ == "__main__":
    setback_fillet()
