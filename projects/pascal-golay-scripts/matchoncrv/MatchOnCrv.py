"""
MatchOnCrv.py
Ported from MatchOnCrv.rvb (Pascal Golay, McNeel - script version 2011-04-28).

Target engine: Rhino 8 Script Editor, CPython3 mode (run via the ScriptEditor
command: open this file, press F5). Not written for the legacy
RunPythonScript/IronPython2 engine.

What it does: pick an open curve near the end you want to match, pick a
target curve, click a point ON the target curve to say where the match
should land. If that point is exactly the target's start or end, it just
runs the `_Match` command directly. Otherwise it splits a copy of the
target curve at that point (so `_Match` has an actual endpoint to match
against), matches to the resulting piece, and then offers to flip which
of the two split pieces was used (if continuity isn't just Position),
cleaning up all the scratch curves/point afterward.

Porting notes / deliberate changes from the original:
- Dropped `Rhino.AddStartupScript` / `Rhino.AddAlias`: alias/startup-script
  registration is a mechanism for the legacy RhinoScript engine, not
  meaningful for a Script Editor Python 3 script run via F5.
- The VBScript `Private OldCon` module-level variable (persisted between
  repeated invocations of the loaded RhinoScript alias in one Rhino
  session) is replaced with `scriptcontext.sticky`, the nearest equivalent
  that survives across separate F5 runs within the same Rhino session.
- `rs.MatchObjectAttributes` takes `(target_ids, source_id)` where
  `target_ids` must be a LIST of ids, not a bare id (confirmed against the
  live rhinoscriptsyntax reference on developer.rhino3d.com, 2026-07-31).
  The original VBScript call `Rhino.MatchObjectAttributes CopyCrv, sCrv`
  passed bare ids (fine for the old RhinoScript signature); this port
  wraps the target in `[copy_crv]`.
- No behavior bugs found in MatchOnCrv.rvb's own logic; its
  `sCon`/`sPres`-style choice handling and split/match/flip control flow
  is ported 1:1.
- The `Rhino.Command "..." , false` calls in the original pass `False` as
  the echo argument (suppress command-line echo). Reproduced with
  `rs.Command(cmd, False)`.
- No other behavior changes; ported 1:1 including the somewhat unusual
  control flow (match against one split half, optionally redo against the
  other half and delete the first result).

Not run against a live Rhino in this session - validated only with
`python3 -m py_compile` / `ast.parse` (no syntax errors). Function names
and signatures were cross-checked against the live rhinoscriptsyntax
reference where noted above; the interactive `_-Match` command-line macro
behavior itself could not be exercised live - test on real curves before
relying on it.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc


def get_curve_end(curve_id, t):
    """0 = curve start is nearer parameter t, 1 = curve end is nearer."""
    dom = rs.CurveDomain(curve_id)
    if abs(t - dom[0]) > abs(t - dom[1]):
        return 1
    else:
        return 0


def match_on_crv():
    old_con = sc.sticky.get("MatchOnCrv_OldCon", "Tangency")

    curve_pick = rs.GetCurveObject("Select open curve near the end to match.", False, False)
    if not curve_pick:
        return
    crv = curve_pick[0]
    pick_t = curve_pick[4]

    if rs.IsCurveClosed(crv):
        rs.MessageBox("Closed curves cannot be matched.")
        return

    end_index = get_curve_end(crv, pick_t)

    targ = rs.GetObject("Select target curve.", 4, False, False)
    if targ is None:
        return

    flip = (end_index == 1)

    if end_index == 0:
        crv_end_pt = rs.CurveStartPoint(crv)
    else:
        crv_end_pt = rs.CurveEndPoint(crv)

    pick_pt = rs.GetPointOnCurve(targ, "Set target point.")
    if pick_pt is None:
        return
    temp_pt = rs.AddPoint(pick_pt)
    tol = rs.UnitAbsoluteTolerance()

    con_choice = rs.GetString("Continuity?", old_con, ["Position", "Tangency", "Curvature"])
    if con_choice is None:
        return

    lowered = con_choice.lower()
    if lowered == "position":
        con = "Position"
    elif lowered == "tangency":
        con = "Tangency"
    elif lowered == "curvature":
        con = "Curvature"
    else:
        return

    sc.sticky["MatchOnCrv_OldCon"] = con

    if rs.PointCompare(pick_pt, rs.CurveStartPoint(targ), tol):
        rs.Command(
            "_-Match SelID {} _SelID {} _Mode=_{} _AverageCurves=_No _Enter".format(crv, targ, con),
            False,
        )
        return
    elif rs.PointCompare(pick_pt, rs.CurveEndPoint(targ), tol):
        rs.ReverseCurve(targ)
        rs.Command(
            "_-Match SelID {} _SelID {} _Mode=_{} _AverageCurves=_No _Enter".format(crv, targ, con),
            False,
        )
        rs.ReverseCurve(targ)
        return

    t = rs.CurveClosestPoint(targ, pick_pt)

    copy_targ = rs.CopyObject(targ)
    split_result = rs.SplitCurve(copy_targ, t)
    if not split_result or len(split_result) < 2:
        # TODO: unverified - original assumed SplitCurve always returns
        # exactly 2 pieces here since t is guaranteed interior to the
        # domain by construction; keeping that assumption but guarding
        # against a None/short result rather than crashing.
        return

    new_targ = split_result[0]
    if rs.PointCompare(rs.CurveEndPoint(new_targ), pick_pt, tol):
        rs.ReverseCurve(new_targ)
    new_targ2 = split_result[1]
    if rs.PointCompare(rs.CurveEndPoint(new_targ2), pick_pt, tol):
        rs.ReverseCurve(new_targ2)

    if flip:
        rs.ReverseCurve(crv)

    copy_crv = rs.CopyObject(crv)
    rs.MatchObjectAttributes([copy_crv], crv)

    rs.EnableRedraw(False)
    rs.Command(
        "_-Match SelID {} _SelID {} _Mode=_{} _AverageCurves=_No _Enter".format(crv, new_targ, con),
        False,
    )
    rs.EnableRedraw(True)

    if con != "Position":
        rev_choice = rs.GetString("Flip?", "No", ["Yes", "No"])

        if rev_choice is None or rev_choice.lower() == "no":
            rs.DeleteObjects([new_targ, new_targ2, copy_crv, temp_pt])
            if flip:
                rs.ReverseCurve(crv)
        elif rev_choice.lower() == "yes":
            rs.EnableRedraw(False)
            rs.DeleteObject(crv)
            rs.Command(
                "_-Match SelID {} _SelID {} _Mode=_{} _AverageCurves=_No _Enter".format(copy_crv, new_targ2, con),
                False,
            )
            rs.DeleteObjects([new_targ, new_targ2, temp_pt])
            if flip:
                rs.ReverseCurve(copy_crv)
    else:
        rs.DeleteObjects([new_targ, new_targ2, copy_crv, temp_pt])
        if flip:
            rs.ReverseCurve(crv)

    rs.EnableRedraw(True)


if __name__ == "__main__":
    match_on_crv()
