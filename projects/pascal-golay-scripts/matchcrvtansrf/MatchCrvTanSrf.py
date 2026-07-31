"""
MatchCrvTanSrf.py
Ported from MatchCrvTanSrf.rvb (Pascal Golay, McNeel - script version 2011-04-07).

Target engine: Rhino 8 Script Editor, CPython3 mode (run via the ScriptEditor
command: open this file, press F5). This is NOT written for the legacy
RunPythonScript/IronPython2 engine.

What it does: pick a curve near the end you want to edit, choose what
continuity to preserve at the OTHER end (None/Position/Tangency/Curvature -
elevating the curve's degree with _ChangeDegree if it isn't high enough to
support that continuity), then pick a target point on a surface. The picked
end of the curve is snapped to that point, the adjacent control point is
pulled onto the surface's tangent plane there (setting tangency), and you
get an interactive tension pull (GetPoint) followed by an interactive
_Rotate3d step (about the surface normal at the target point) so you can
dial in the tangent direction visually.

Porting notes / deliberate changes from the original:
- Dropped `Rhino.AddStartupScript` / `Rhino.AddAlias` and the `Rhino.Version()
  > 4` legacy branch: these existed to (a) auto-register a command alias for
  the old RhinoScript engine and (b) support Rhino <= 4, neither of which is
  meaningful/reachable from a Script Editor Python 3 script. This is an
  intentional platform-migration change, not an oversight.
- `rs.Pt2Str` does not exist in current rhinoscriptsyntax (confirmed against
  the live rhinoscriptsyntax reference on developer.rhino3d.com, 2026-07-31
  - it was an old RhinoScript-only helper). Coordinates for the `_Rotate3d`
  command-line macro are formatted manually instead, keeping the same "W"
  (world coordinate system) prefix convention the original relied on -
  that command-line prefix syntax is unchanged in Rhino 8.
- There is no rhinoscriptsyntax function that changes a curve's degree
  in place (confirmed live) - both the original and this port fall back to
  running the `_ChangeDegree` command line macro on the selected curve.
- The VBScript `Private oldPres` module-level variable (which persisted
  between repeated invocations of the same loaded RhinoScript alias within
  one Rhino session) has no direct equivalent for a script re-run via F5 in
  Script Editor - each run is argued to be a fresh module. The nearest
  equivalent that survives across runs within the same Rhino session is
  `scriptcontext.sticky`, used here for the "preserve" default.
- No behavior bugs found in the original logic itself; ported as-is.

Not run against a live Rhino in this session - validated only with
`python3 -m py_compile` / `ast.parse` (no syntax errors), and function names/
signatures were cross-checked against the live rhinoscriptsyntax reference
where noted above. Grip and command-line macro behavior could not be
exercised live - test on a real curve/surface before relying on it.
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


def change_curve_degree(curve_id, degree):
    rs.EnableRedraw(False)
    rs.UnselectAllObjects()
    rs.SelectObject(curve_id)
    rs.Command("_ChangeDegree {} ".format(degree), False)
    rs.UnselectAllObjects()
    rs.EnableRedraw(True)


def format_world_point(pt):
    """Format a point as a Rhino command-line coordinate string, forced to
    World coordinates with the 'W' prefix (unchanged Rhino command-line
    syntax) - replaces the old RhinoScript Pt2Str() helper, which no longer
    exists in rhinoscriptsyntax."""
    return "W{},{},{}".format(pt.X, pt.Y, pt.Z)


def match_crv_tan_srf():
    old_pres = sc.sticky.get("MatchCrvTanSrf_OldPres", 1)

    curve_pick = rs.GetCurveObject("Select curve near the end to edit.", False, False)
    if not curve_pick:
        return
    curve_id = curve_pick[0]
    pick_t = curve_pick[4]

    pt_count = rs.CurvePointCount(curve_id)

    pres_options = ["None", "Position", "Tangency", "Curvature"]
    default_pres = pres_options[old_pres] if 0 <= old_pres < len(pres_options) else "Position"
    pres_choice = rs.GetString("Preserve other end?", default_pres, pres_options)
    if pres_choice is None:
        return

    try:
        pres_index = pres_options.index(pres_choice)
    except ValueError:
        # case-insensitive fallback, in case GetString returns a re-cased match
        lowered = [p.lower() for p in pres_options]
        if pres_choice.lower() in lowered:
            pres_index = lowered.index(pres_choice.lower())
        else:
            return

    sc.sticky["MatchCrvTanSrf_OldPres"] = pres_index

    if pres_index == 1:  # Position
        if pt_count < 3:
            change_curve_degree(curve_id, 2)
    elif pres_index == 2:  # Tangency
        if pt_count < 4:
            change_curve_degree(curve_id, 3)
    elif pres_index == 3:  # Curvature
        if pt_count < 5:
            change_curve_degree(curve_id, 4)

    grip_count = rs.CurvePointCount(curve_id)
    last_grip_index = grip_count - 1
    end_index = get_curve_end(curve_id, pick_t)
    print("Curve has {} grips (last index {}).".format(grip_count, last_grip_index))

    surface_id = rs.GetObject("Select target surface", 8, True)
    if surface_id is None:
        return

    target_pt = rs.GetPointOnSurface(surface_id, "Set target point")
    if target_pt is None:
        return

    uv = rs.SurfaceClosestPoint(surface_id, target_pt)
    normal = rs.SurfaceNormal(surface_id, uv)
    axis_pt0 = target_pt
    axis_pt1 = rs.PointAdd(target_pt, normal)
    tangent_plane = rs.SurfaceFrame(surface_id, uv)

    rs.EnableObjectGrips(curve_id, True)

    if end_index == 0:
        grip_a = 0
        grip_b = 1
    else:
        grip_a = last_grip_index
        grip_b = last_grip_index - 1

    rs.ObjectGripLocation(curve_id, grip_a, target_pt)
    adjacent_pt = rs.ObjectGripLocation(curve_id, grip_b)
    projected_pt = rs.PlaneClosestPoint(tangent_plane, adjacent_pt, True)
    rs.ObjectGripLocation(curve_id, grip_b, projected_pt)

    rs.UnselectAllObjects()
    rs.SelectObjectGrip(curve_id, grip_b)
    tension_pt = rs.ObjectGripLocation(curve_id, grip_b)
    grip_a_pt = rs.ObjectGripLocation(curve_id, grip_a)

    # NOTE on mapping: the original VBScript call was
    #   Rhino.GetPoint("Set tension", C, Rhino.ObjectGripLocation(sCrv,A))
    # i.e. a 3-argument (message, point, basisPoint) overload from the old
    # RhinoScript engine. Current rhinoscriptsyntax's GetPoint(message,
    # base_point, distance, in_plane) has no equivalent "point"+"basisPoint"
    # pair - only a single base_point for the dynamic rubber-band line.
    # We use grip A's location (the anchor end) as base_point, which
    # reproduces the visible rubber-band guide from the anchor to the
    # cursor; unlike the original there's no way to also pre-seed the
    # cursor at C. Unverified live (no Rhino available here) - confirm the
    # rubber-band visual matches expectations before relying on it.
    picked_pt = rs.GetPoint("Set tension", grip_a_pt)
    if picked_pt is None:
        picked_pt = tension_pt
    rs.ObjectGripLocation(curve_id, grip_b, picked_pt)

    current_pt = rs.ObjectGripLocation(curve_id, grip_b)
    rotate_cmd = "_Rotate3d _Copy=No {} {} {}".format(
        format_world_point(axis_pt0),
        format_world_point(axis_pt1),
        format_world_point(current_pt),
    )
    rs.Command(rotate_cmd, False)

    rs.EnableObjectGrips(curve_id, False)


if __name__ == "__main__":
    match_crv_tan_srf()
