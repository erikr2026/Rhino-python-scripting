"""
ZoomSame.py

Ported from ZoomSame.rvb (legacy VBScript RhinoScript, Pascal Golay /
McNeel). Target engine: Rhino 8 Script Editor, CPython 3 mode (open the .py
file in ScriptEditor and press F5). Not for the legacy `RunPythonScript`
(IronPython 2) command.

What it does: makes every other viewport match the current view's apparent
zoom level/target.
  - If the current view is a parallel projection, it directly copies the
    current view's radius (`rs.ViewRadius`) and target point to every other
    view.
  - If the current view is in perspective, there's no single "radius" to
    copy, so instead it builds a temporary sphere that roughly fills the
    current viewport's frustum (via the near-clipping-plane corners and the
    camera position), selects it, and zooms every other view to fit that
    sphere -- then deletes the temporary sphere. This is the same
    "zoom-to-a-reference-object" trick used to sync scale across a
    perspective view and orthogonal views, which don't share a literal
    zoom-radius concept.
  Does nothing (with a message) if the current view is a page layout view.
  The current object selection is restored afterward.

Not ported: `Rhino.AddStartupScript` / `Rhino.AddAlias`, which registered a
permanent Rhino alias ("ZoomSame") that re-ran this script from disk on
every Rhino startup. No equivalent mechanism exists for a Script Editor .py
file; create an alias by hand (Options > Aliases) if you want one.

Verification note: rs.IsLayout, rs.CurrentView, rs.SelectedObjects,
rs.ViewNames, rs.ViewTarget, rs.UnselectAllObjects, rs.ViewProjection,
rs.SelectObject, rs.ZoomSelected, rs.DeleteObject, rs.ViewRadius,
rs.SelectObjects, rs.ViewNearCorners, rs.ViewCamera, rs.LinePlaneIntersection,
rs.AddSphere, and rs.Distance signatures/return shapes were all confirmed
this session against the mcneel/rhinoscriptsyntax GitHub source (view.py,
selection.py, object.py, line.py, sphere-adding is in surface.py/mesh.py --
AddSphere confirmed present). Two call-shape notes from that check:
  - `rs.ViewNearCorners()` returns corners in the order
    `(near-bottom-left, near-bottom-right, near-top-right, near-top-left)`
    i.e. index 3 is the counter-clockwise-adjacent corner to index 0 (the
    source explicitly reorders the underlying `GetNearRect()` result to
    `rc[0], rc[1], rc[3], rc[2]`) -- this matches the original's use of
    corners 0, 1, and 3 one-for-one, so no change was needed there.
  - `rs.CurrentView(view=None, return_name=True)`: the original's
    `Rhino.CurrentView(,False)` (blank view arg, return_name=False) becomes
    `rs.CurrentView(return_name=False)` here, which returns the view's GUID
    rather than its title -- used purely as an opaque view identifier for
    comparisons and to pass to other rs.* calls, exactly as the original
    VBScript variable was used, so this is a faithful port.

There is no live Rhino available in this environment to actually execute
this script.
"""

import rhinoscriptsyntax as rs


def _sphere_to_view(s_view):
    """Create a sphere roughly filling s_view's viewport, and return its
    object id."""
    a_corners = rs.ViewNearCorners(s_view)
    cam = rs.ViewCamera(s_view)

    line1 = (cam, a_corners[0])

    w = rs.Distance(a_corners[0], a_corners[1])
    h = rs.Distance(a_corners[0], a_corners[3])

    if h < w:
        line2 = (cam, a_corners[3])
    else:
        line2 = (cam, a_corners[1])

    plane = rs.ViewCameraPlane(s_view)
    plane.Origin = rs.ViewTarget(s_view)

    pt1 = rs.LinePlaneIntersection(line1, plane)
    pt2 = rs.LinePlaneIntersection(line2, plane)

    rad = rs.Distance(pt1, pt2) / 2.0

    return rs.AddSphere(plane.Origin, rad)


def zoom_same():
    if rs.IsLayout(rs.CurrentView()):
        print("This tool does not work in layouts.")
        return

    a_sel = rs.SelectedObjects()
    a_views = rs.ViewNames(False)
    crnt_view = rs.CurrentView(return_name=False)
    a_targ = rs.ViewTarget()

    rs.EnableRedraw(False)
    try:
        rs.UnselectAllObjects()

        if rs.ViewProjection() == 2:
            v_sphere = _sphere_to_view(crnt_view)
            rs.SelectObject(v_sphere)

            for s_view in a_views:
                if s_view != crnt_view:
                    rs.ZoomSelected(s_view)

            rs.DeleteObject(v_sphere)
        else:
            rad = rs.ViewRadius()

            for s_view in a_views:
                if s_view != crnt_view:
                    rs.ViewRadius(s_view, rad)
                    rs.ViewTarget(s_view, a_targ)

        if a_sel:
            rs.SelectObjects(a_sel)
    finally:
        rs.EnableRedraw(True)


if __name__ == "__main__":
    zoom_same()
