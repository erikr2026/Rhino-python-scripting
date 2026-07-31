"""
SurfaceTangent.py

Ported from SurfaceTangent.rvb (legacy VBScript RhinoScript, Pascal Golay /
McNeel). Target engine: Rhino 8 Script Editor, CPython 3 mode (open the .py
file in ScriptEditor and press F5). Not for the legacy `RunPythonScript`
(IronPython 2) command.

Two tools for adjusting the tangency of an UNTRIMMED surface edge by
manipulating its control-point grips:

  tangent_direction_srf() -- picks a surface near one edge, then a 2-point
      direction, and re-aims every tangent (second-row) control point along
      that edge so it lies in the given direction from its corresponding
      edge point (each point's distance from the edge is preserved, only
      its direction changes).

  tangent_tension_srf() -- picks a surface near one edge, then lets you
      interactively drag one tangent point along the line through it and
      its edge point (Rhino's own `_Move _AlongLine` mechanism supplies the
      live drag); every other tangent point on that edge is then moved to
      match, either by the same absolute distance from its edge point
      ("Absolute") or by the same proportional change in distance
      ("Proportional").

Not ported: `Rhino.AddStartupScript` / two `Rhino.AddAlias` calls, which
registered permanent Rhino aliases ("TangentDirectionSrf",
"TangentTensionSrf") that re-ran this exact script file, dispatching to one
Sub or the other based on the alias's argument. Script Editor has no
equivalent "re-invoke this file and call one specific function" mechanism
triggered by a typed alias, so this file instead prompts on the command
line for which of the two tools to run when executed directly (see the
bottom of the file). If you want one-word aliases, create them by hand in
Rhino's Options > Aliases pointing at this file with a documented
convention for picking the tool (e.g. two separate tiny wrapper .py files).

Persistence of the "last used" tension-adjustment style ("Absolute" vs.
"Proportional") is done via scriptcontext.sticky, the standard
rhinoscriptsyntax mechanism for values that should survive from one run of
a script to the next within the same Rhino session -- replacing the
original's module-scope `Private OldAdjStyle` VBScript variable, which only
persisted because the script stayed loaded as a running alias.

Bugs found in the original:
  - `Rhino.Command "_Move W" & Pt2Str(LocTan,,True) &"_alongLine W" & ...`
    concatenates the tangent point's coordinate text directly against
    "_alongLine" with no separating space (e.g. "...0.0,0.0,0.0_alongLine
    W..."), which would very likely break Rhino's command-line token
    parsing. Fixed below by inserting a space between every macro token.
  - `SurfaceEdge`'s "nearest edge" fallback branch (used only when a pick
    lands exactly on a corner or otherwise not cleanly on one of the four
    parameter-domain edges) is explicitly marked `'not working right...`
    in the original's own comment, and its `UDist <= .5` / `VDist <= .5`
    checks are close to tautological given how UDist/VDist are computed
    (they range roughly (-0.5, 0.5], so the check is almost always true).
    That fallback logic is reproduced AS-IS below (bug preserved, not
    fixed) since the owner hasn't asked for a redesign of it and it's only
    reachable in an edge case; flagged here so it isn't mistaken for new
    behavior introduced by the port.

Verification note: rs.GetSurfaceObject, rs.GetPoints, rs.GetObjectGrip,
rs.EnableObjectGrips, rs.ObjectGripsOn, rs.ObjectGripLocation,
rs.SelectObjectGrip, rs.SurfacePointCount, rs.SurfaceDomain, rs.GetString,
rs.Command, rs.LastCommandResult, rs.ViewCPlane, rs.WorldXYPlane, rs.Distance
were all confirmed this session against the mcneel/rhinoscriptsyntax GitHub
source. `Rhino.VectorCreate` / `Rhino.VectorUnitize` / `Rhino.VectorScale` /
`Rhino.PointAdd` / `Rhino.Pt2Str` are legacy RhinoScript (VBScript COM)
methods with NO equivalents in rhinoscriptsyntax (confirmed by listing every
`def` in rhinoscriptsyntax's utility.py, geometry.py, plane.py) -- this port
uses Rhino.Geometry.Point3d/Vector3d arithmetic directly instead (points
returned by rs.* calls are already Point3d objects under the Script Editor's
PythonNet binding, so `p2 - p1` yields a Vector3d, `Vector3d.Unitize()`
normalizes in place, and `point + vector` yields a Point3d).

One geometric assumption carried over unverified from the original: the
flattened control-point grip index formula (`u_index * v_count + v_index`,
derived by reverse-engineering the original's index arithmetic against the
confirmed `rs.SurfacePointCount` return order of `(u_count, v_count)`)
matches the actual grip ordering `rs.ObjectGripLocation` uses for a
surface's control-point grid. This has always been the conventional
row-major ordering for Rhino's underlying `RhinoObject.GetGrips()`, and the
original script (by Pascal Golay, a McNeel developer) evidently worked
against that same ordering -- but there is no live Rhino available in this
environment to actually confirm it. Test on a real surface before relying
on this for production work, especially near a periodic or singular edge.

Also unverified: the exact argument order Pascal intended for
`Rhino.VectorCreate(pointA, pointB)` in the original (legacy RhinoScript
docs describe it as "vector from pointB to pointA", i.e. pointA - pointB,
but this could not be independently confirmed live). Rather than guess that
order, this port reasons directly from what each vector is used for:
  - direction vector in tangent_direction_srf(): user picks a base point
    then a direction point, so the natural direction is base -> second
    pick (`second - base`). If this comes out visually backwards in Rhino,
    swap the two GetPoints results.
  - direction vector in tangent_tension_srf(): must point from the edge
    point toward the (old) tangent point, so the surface bends the same
    way it already did, just by a different amount (`tan_pt - edge_pt`).
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Vector3d

_STICKY_KEY = "SurfaceTangent_OldAdjStyle"


def _get_old_adj_style():
    return sc.sticky.get(_STICKY_KEY, "Absolute")


def _set_old_adj_style(value):
    sc.sticky[_STICKY_KEY] = value


def _pt_str(pt):
    """Format a Point3d as 'x,y,z' text for a Rhino command-line macro."""
    return "{0},{1},{2}".format(pt.X, pt.Y, pt.Z)


def _surface_edge(u_dom, v_dom, param):
    """Return which parametric edge (0=Umin, 1=Umax, 2=Vmin, 3=Vmax) a
    surface pick parameter lies on (or nearest to)."""
    u, v = param[0], param[1]

    if u == u_dom[0]:
        return 0
    if u == u_dom[1]:
        return 1
    if v == v_dom[0]:
        return 2
    if v == v_dom[1]:
        return 3

    # Nearest-edge fallback for a pick that didn't land exactly on an edge.
    # Reproduced as-is from the original, which flags this branch itself as
    # "not working right..." -- see the docstring note above.
    u_prop = (u_dom[1] - u) / (u_dom[1] - u_dom[0])
    v_prop = (v_dom[1] - v) / (v_dom[1] - v_dom[0])

    u_dist = u_prop if u_prop <= 0.5 else -1 * (1 - u_prop)
    v_dist = v_prop if v_prop <= 0.5 else -1 * (1 - v_prop)

    if abs(u_dist) < abs(v_dist):
        return 0 if u_dist <= 0.5 else 1
    else:
        return 2 if v_dist <= 0.5 else 3


def _surface_tangent_points(u_count, v_count, edge):
    """Return (range_pos, range_tan): parallel lists of flattened grip
    indices for the edge-row control points and the corresponding
    one-row-in "tangent" control points, for the given edge."""
    if edge < 2:
        count = v_count - 1
    else:
        count = u_count - 1

    range_pos = [0] * (count + 1)
    range_tan = [0] * (count + 1)

    if edge == 0:
        for i in range(count + 1):
            range_pos[i] = i
            range_tan[i] = i + count + 1
    elif edge == 1:
        total = u_count * v_count
        for i in range(count + 1):
            range_pos[i] = (total - v_count) + i
            range_tan[i] = (total - 2 * v_count) + i
    elif edge == 2:
        for i in range(count + 1):
            range_pos[i] = i * v_count
            range_tan[i] = i * v_count + 1
    elif edge == 3:
        for i in range(count + 1):
            range_pos[i] = v_count + (i * v_count - 1)
            range_tan[i] = (v_count - 1) + (i * v_count - 1)

    return range_pos, range_tan


def tangent_direction_srf():
    s_srf_pick = rs.GetSurfaceObject(
        "Select untrimmed surface on the edge to adjust", False
    )
    if s_srf_pick is None:
        return
    s_srf = s_srf_pick[0]
    a_param = s_srf_pick[4]

    a_dir = rs.GetPoints(
        draw_lines=True,
        in_plane=False,
        message1="Tangent direction base point",
        message2="Tangent direction point",
        max_points=2,
    )
    if not a_dir or len(a_dir) < 2:
        return

    vec_dir = a_dir[1] - a_dir[0]  # see docstring note on direction convention
    vec_dir.Unitize()

    u_dom = rs.SurfaceDomain(s_srf, 0)
    v_dom = rs.SurfaceDomain(s_srf, 1)
    int_edge = _surface_edge(u_dom, v_dom, a_param)

    a_cnt = rs.SurfacePointCount(s_srf)
    u_count, v_count = a_cnt[0], a_cnt[1]
    range_pos, range_tan = _surface_tangent_points(u_count, v_count, int_edge)

    rs.EnableRedraw(False)
    try:
        bln_on = True
        if not rs.ObjectGripsOn(s_srf):
            bln_on = False
            rs.EnableObjectGrips(s_srf)

        for i in range(len(range_pos)):
            tan_pt = rs.ObjectGripLocation(s_srf, range_tan[i])
            pos_pt = rs.ObjectGripLocation(s_srf, range_pos[i])
            dist = rs.Distance(tan_pt, pos_pt)
            rs.ObjectGripLocation(
                s_srf, range_tan[i], pos_pt + vec_dir * dist
            )

        if not bln_on:
            rs.EnableObjectGrips(s_srf, False)
    finally:
        rs.EnableRedraw(True)


def tangent_tension_srf():
    s_srf_pick = rs.GetSurfaceObject(
        "Select untrimmed surface near edge to change", False
    )
    if s_srf_pick is None:
        return
    s_srf = s_srf_pick[0]
    a_param = s_srf_pick[4]

    u_dom = rs.SurfaceDomain(s_srf, 0)
    v_dom = rs.SurfaceDomain(s_srf, 1)
    int_edge = _surface_edge(u_dom, v_dom, a_param)

    a_cnt = rs.SurfacePointCount(s_srf)
    u_count, v_count = a_cnt[0], a_cnt[1]
    range_pos, range_tan = _surface_tangent_points(u_count, v_count, int_edge)
    bound = len(range_pos) - 1

    old_style = _get_old_adj_style()
    s_style = rs.GetString(
        "Tension adjustment style", old_style, ["Absolute", "Proportional"]
    )
    if not s_style:
        return

    style_lower = s_style.lower()
    if style_lower == "absolute":
        bln_abs = True
        _set_old_adj_style("Absolute")
    elif style_lower == "proportional":
        bln_abs = False
        _set_old_adj_style("Proportional")
    else:
        return

    rs.EnableRedraw(False)
    bln_on = True
    if not rs.ObjectGripsOn(s_srf):
        bln_on = False
        rs.EnableObjectGrips(s_srf)

    a_dummy = [None] * (bound + 1)
    for i in range(bound + 1):
        rs.SelectObjectGrip(s_srf, range_tan[i])
        a_dummy[i] = rs.AddPoint(rs.ObjectGripLocation(s_srf, range_pos[i]))

    rs.Command("_InvertPt", False)
    rs.Command("_HidePt", False)

    rs.EnableRedraw(True)

    a_dir = rs.GetObjectGrip("Select a control point", preselect=True)
    if a_dir is None:
        rs.DeleteObjects(a_dummy)
        rs.Command("_ShowPt", False)
        return

    x = None
    a_base = None
    for i in range(bound + 1):
        if a_dir[1] == range_tan[i]:
            a_base = range_pos[i]
            x = i
            break

    if x is None:
        # Picked grip wasn't one of the tangent points on this edge.
        rs.DeleteObjects(a_dummy)
        rs.Command("_ShowPt", False)
        return

    loc_edge = rs.ObjectGripLocation(s_srf, a_base)
    loc_tan = rs.ObjectGripLocation(s_srf, a_dir[1])
    dist = rs.Distance(loc_edge, loc_tan)

    macro = "_Move W{0} _AlongLine W{0} W{1} ".format(
        _pt_str(loc_tan), _pt_str(loc_edge)
    )
    rs.Command(macro, False)

    if rs.LastCommandResult() != 0:
        rs.DeleteObjects(a_dummy)
        rs.Command("_ShowPt", False)
        return

    rs.EnableRedraw(False)

    dist2 = rs.Distance(loc_edge, rs.ObjectGripLocation(s_srf, a_dir[1]))
    dbl_prop = dist2 / dist if dist else 0.0

    for i in range(bound + 1):
        if i != x:
            loc_edge_i = rs.ObjectGripLocation(s_srf, range_pos[i])
            loc_tan_i = rs.ObjectGripLocation(s_srf, range_tan[i])
            temp_dist = rs.Distance(loc_edge_i, loc_tan_i)
            temp_scale = temp_dist * dbl_prop
            if bln_abs:
                temp_scale = dist2

            vec_dir = loc_tan_i - loc_edge_i  # edge -> old tangent point
            if vec_dir.Length > 0:
                vec_dir.Unitize()
            vec_dir = vec_dir * temp_scale

            rs.ObjectGripLocation(
                s_srf, range_tan[i], loc_edge_i + vec_dir
            )

    rs.DeleteObjects(a_dummy)
    rs.Command("_ShowPt", False)
    # NOTE: the original leaves grips in whatever on/off state they were
    # in before the AddObjectGrips call turned them on (its "restore"
    # line is commented out: `'If BlnOn = False Then Rhino.EnableObjectGrips
    # sSrf, False`), so grips are intentionally left ON here too --
    # reproduced as-is, not a port bug.
    rs.EnableRedraw(True)


if __name__ == "__main__":
    choice = rs.GetString(
        "Which tool?", "TangentDirectionSrf",
        ["TangentDirectionSrf", "TangentTensionSrf"],
    )
    if choice:
        choice_lower = choice.lower()
        if choice_lower == "tangentdirectionsrf":
            tangent_direction_srf()
        elif choice_lower == "tangenttensionsrf":
            tangent_tension_srf()
