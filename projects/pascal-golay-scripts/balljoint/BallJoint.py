"""
BallJoint.py - Python 3 (CPython) port of BallJoint.rvb (Pascal Golay, McNeel)

TARGET ENGINE: Rhino 8 Script Editor, CPython3 mode (ScriptEditor command,
F5). Not intended for the legacy `RunPythonScript` (IronPython 2) command.

Original behavior: pick objects, pick a pivot point and a reference point
(pivot -> reference defines the sphere's radius), build a temporary
construction sphere at the pivot, then use Rhino's `Orient` command
(`Onsrf` option) so the picked objects can be re-oriented by dragging along
that sphere's surface (a "ball joint" gizmo), after which the temporary
sphere is deleted.

Porting notes / deliberate simplifications:
  - `Rhino.AddAlias`/`Rhino.AddStartupScript` (registering a persistent
    "BallJoint" command alias) is a legacy VBScript RhinoScript mechanism
    with no Script Editor CPython3 equivalent; dropped. Run this file
    directly with F5, or point a Rhino alias/button at it manually.
  - `Rhino.Pt2Str` (legacy point-to-command-string formatter) has no
    rhinoscriptsyntax or RhinoCommon equivalent -- there is no
    `rs.Pt2Str`. Replaced with a small local `_pt_to_str()` helper that
    formats a point as `"x,y,z"` for use in a Rhino command-line macro
    string, which is the same thing Pt2Str was doing here.
  - `Rhino.Command "Sphere " & strCent & strRefPt` is replaced with a
    direct `rs.AddSphere(center, radius)` call (radius computed via
    `rs.Distance`) -- functionally identical to the two-point Sphere
    command, but avoids building a command-line string and its point-
    formatting/quoting pitfalls for this step.
  - The final `Orient Scale=No <pivot> <reference> <pivot> Onsrf SelID
    <sphere>` step is kept as a `rs.Command(...)` macro string, because
    "orient onto a surface with OnSrf snapping" is a full interactive
    Rhino command behavior (surface-snap drag) with no direct
    rhinoscriptsyntax/RhinoCommon transform equivalent -- this mirrors
    what the original script itself did (delegate to the command line for
    this step). The macro string/argument order is carried over verbatim
    from the original, only reformatting the point tokens with
    `_pt_to_str()`.
    # TODO: unverified -- the exact token order/spacing Rhino's `Orient`
    # command macro expects for the `Onsrf` (orient-onto-surface) option
    # could not be confirmed live (no running Rhino instance in this
    # environment). This is carried over as literally as possible from
    # the original .rvb macro string; test it once in Rhino before relying
    # on it, and adjust spacing/option order if the command line rejects it.
  - `Rhino.GetObjects`, `Rhino.GetPoints`, `Rhino.UnselectAllObjects`,
    `Rhino.SelectObjects`/`SelectObject`, `Rhino.FirstObject`,
    `Rhino.LastCommandResult`, `Rhino.SurfaceIsocurveDensity`,
    `Rhino.DeleteObject` map 1:1 to their rhinoscriptsyntax equivalents
    (confirmed against https://developer.rhino3d.com/api/RhinoScriptSyntax/,
    fetched live this session).
"""

import rhinoscriptsyntax as rs


def _pt_to_str(pt):
    return "{0},{1},{2}".format(pt.X, pt.Y, pt.Z)


def ball_joint():
    obj_ids = rs.GetObjects("Select objects to pivot", preselect=True, select=True)
    if not obj_ids:
        return

    ref_pts = rs.GetPoints(True, False, "Pivot point", "Reference point", 2)
    if not ref_pts:
        return

    rs.EnableRedraw(False)

    pivot, reference = ref_pts[0], ref_pts[1]
    radius = rs.Distance(pivot, reference)

    rs.UnselectAllObjects()
    sphere_id = rs.AddSphere(pivot, radius)
    if sphere_id is None:
        rs.EnableRedraw(True)
        return

    rs.UnselectAllObjects()
    rs.SurfaceIsocurveDensity(sphere_id, -1)
    rs.SelectObject(sphere_id)
    rs.Command("SetObjectDisplayMode Mode=WireFrame ", False)

    rs.EnableRedraw(True)

    rs.UnselectAllObjects()
    rs.SelectObjects(obj_ids)
    cmd = "Orient Scale=No {}{}{}Onsrf SelID {} ".format(
        _pt_to_str(pivot), _pt_to_str(reference), _pt_to_str(pivot), sphere_id
    )
    rs.Command(cmd, False)
    rs.DeleteObject(sphere_id)


if __name__ == "__main__":
    ball_joint()
