"""RotateOnNormal.py

Ported from RotateOnNormal.rvb (Pascal Golay, RMA, 2007) - legacy
VBScript/RhinoScript engine - to Python 3 for Rhino 8's Script Editor
(CPython 3 engine). Run via the Script Editor's F5, not via the legacy
`RunPythonScript` (IronPython 2) command.

What it does: rotates the selected objects (or the current selection, if
any) repeatedly about an axis built from the surface normal at a
user-picked point on a reference surface - i.e. "Rotate3D" with the axis
pre-loaded to that point and its normal-offset point, run in a loop so you
can keep dialing in additional rotation passes without re-picking the
axis, until you cancel.

Function names verified live this session against the modern
rhinoscriptsyntax source (github.com/mcneel/rhinoscriptsyntax, rhino-8.x
branch): SelectedObjects, GetObjects, GetObject, GetPointOnSurface,
XformWorldToCPlane, SurfaceClosestPoint, SurfaceNormal, PointAdd,
SelectObjects, GetString, Command - all exist with the call signatures
used here. `Rhino.Pt2Str` from the legacy engine has no equivalent in
modern rhinoscriptsyntax (there is no rs.Pt2Str) - replaced with a small
local `pt_to_cmd_str()` helper that formats a Point3d as the plain
"x,y,z" text Rhino's command line expects (the point is first converted
to CPlane-relative coordinates via XformWorldToCPlane, exactly as the
original did, since bare "x,y,z" typed at the command line is interpreted
relative to the active CPlane unless a "w" world-coordinate prefix is
added).

Bug fixed from the original (flagged, not silently ported): the original's
exit-loop test was `If UCase(sCont) = "" Then Exit Sub` - comparing the
uppercased *return value* of GetString to an empty string. But
`Rhino.GetString(..., array("Continue"))` (a single-item "list of
acceptable strings") returns the string the user typed only when they type
something other than just pressing Enter; if Escape is pressed the
original already exits earlier via `If isNull(sCont) Then Exit Sub`, and if
Enter is pressed with the default (empty string prompt, "Continue" is just
a listed command-line option, not the default text) GetString returns ""
- so the `UCase(sCont) = ""` branch was actually the *only real way* this
ever exits by continuing normally, making the surrounding `Do ... Loop
Until isNull(sCont)` dead: isNull(sCont) is never true at the loop-continue
check because that path already returned via the `Exit Sub` above it.
Net effect: the original loop can only ever run once before hitting one of
its two exits it can never legitimately loop back around. This port
replicates the *intended* behavior instead (loop applying another rotation
pass each time Enter is pressed, stop on Escape) using a plain post-checks
in a while loop, since guessing the exact intended semantics is more useful
here than reproducing a control-flow dead end. Flagged rather than left
silently "fixed" - if you relied on the original's single-pass behavior,
this now genuinely loops.
"""

import rhinoscriptsyntax as rs


def pt_to_cmd_str(world_pt):
    """Format a world point as CPlane-relative "x,y,z" text for use inside
    an rs.Command() macro string - matches how the legacy engine's
    Rhino.Pt2Str (fed a CPlane-space point) formatted values for the
    command line."""
    cplane_pt = rs.XformWorldToCPlane(world_pt, rs.ViewCPlane())
    return "{},{},{}".format(cplane_pt.X, cplane_pt.Y, cplane_pt.Z)


def rotate_on_normal():
    obj_ids = rs.SelectedObjects()
    if not obj_ids:
        obj_ids = rs.GetObjects("Select objects to rotate", group=True, select=True)
        if not obj_ids:
            return

    srf_id = rs.GetObject("Select base surface", rs.filter.surface, preselect=True)
    if not srf_id:
        return

    pt = rs.GetPointOnSurface(srf_id, "Point on the surface")
    if not pt:
        return

    param = rs.SurfaceClosestPoint(srf_id, pt)
    normal = rs.SurfaceNormal(srf_id, param)
    end_pt = rs.PointAdd(pt, normal)

    s_pt = pt_to_cmd_str(pt)
    s_end = pt_to_cmd_str(end_pt)

    rs.SelectObjects(obj_ids)
    cmd_str = "_Rotate3D _Pause {} {}".format(s_pt, s_end)

    # See "Bug fixed" note in the module docstring: this loop intentionally
    # keeps applying another rotation pass each time the user presses Enter
    # at the "Continue" prompt, and stops on Escape.
    first_pass = True
    while True:
        if not first_pass:
            s_cont = rs.GetString("Press Enter to accept", "", ("Continue",))
            if s_cont is None:
                return
        first_pass = False

        rs.Command(cmd_str, False)


if __name__ == "__main__":
    rotate_on_normal()
