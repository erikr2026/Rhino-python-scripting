"""PopUpPlanes.py
Ported from PopUpPlanes.rvb (Pascal Golay, RMA, 2007-04-11).

Target engine: Rhino 8 Script Editor, CPython3 mode (run via F5, NOT the
legacy `RunPythonScript` command).

Original behavior: defines TWO independent commands via separate command
aliases in the .rvb (`PopUpPlanes` and `CurrentPlane`):
  - PopUpPlanes(): shows a popup menu of all named construction planes in
    the document and restores whichever one the user picks in the active
    view. If there are no named CPlanes, shows a one-line popup saying so.
  - CurrentPlane(): shows a popup menu (a one-line "menu", used here purely
    as a message display) reporting the name of the CURRENT view's CPlane
    -- either one of the 6 built-in "World ..." planes (Top/Right/Front/
    Bottom/Back/Left) if it exactly matches one of those, a matching named
    CPlane if it exactly matches one, or "Unsaved" otherwise.

ENTRY POINT NOTE (a deliberate simplification, not a GUI choice): the
original .rvb registers both subs as separate typeable command aliases
(`PopUpPlanes` and `CurrentPlane`) via `Rhino.AddAlias`, so either could be
run independently from the command line. A single Script Editor .py file
has one natural F5 entry point, so this port keeps both functions defined
here but only auto-runs `popup_planes()` at the bottom (matching this
file's name). To run `current_plane()` instead, either call it directly
from the Script Editor's interactive console, or comment out the
`popup_planes()` call below and call `current_plane()` in its place. If
you want both as separate one-click commands, split `current_plane()`
(plus its two helpers) into its own sibling .py file instead.

The `Rhino.AddStartupScript` / `Rhino.AddAlias` lines at the top of the
.rvb are legacy alias-registration mechanics with no equivalent need in a
Script Editor Python file (you just open and run it directly), so they
are omitted here.

BUG FIXED, not silently carried forward -- flagged explicitly:
  In the original `PopUpPlanes` sub, the check before restoring a plane is
  `If Not isnull(strPlane) Then` -- but `strPlane` is declared and never
  assigned anywhere in the sub (the popup's result is stored in
  `idxPlane`, not `strPlane`). Since an un-assigned VBScript variable is
  `Empty`, not `Null`, `IsNull(Empty)` is always False, so this condition
  is unconditionally True. That means the original ALWAYS calls
  `Rhino.RestoreNamedCPlane arrPlanes(idxPlane)` after the popup, even if
  the user dismissed/canceled it -- and `Rhino.PopupMenu` returns -1 on
  cancel, so `arrPlanes(-1)` would raise a VBScript "Subscript out of
  range" runtime error on cancel.
  This port does NOT reproduce that crash-on-cancel bug, because the
  direct Python equivalent would be *worse*, not equivalent: Python lists
  silently support negative indexing, so `arr_planes[-1]` would silently
  and incorrectly restore the LAST named CPlane in the list on every
  cancel, with no error at all -- a silent wrong-plane bug instead of a
  loud crash. Instead this port checks `idx != -1` explicitly before
  restoring, which is the evident original intent (the unused `strPlane`
  variable strongly suggests a check-for-cancel was intended but
  mistakenly written against the wrong variable).

API notes verified live against the mcneel/rhinoscriptsyntax GitHub source
(raw.githubusercontent.com/mcneel/rhinoscriptsyntax/master/Scripts/
rhinoscript/*.py) on this date:
  - rs.PopupMenu(items, modes=None, point=None, view=None) returns the
    picked index, or -1 if nothing was picked/canceled.
  - rs.PointCompare(point1, point2, tolerance=None) coerces its arguments
    through rhinoscriptsyntax's internal `coerce3dpoint`, which explicitly
    accepts Vector3d (and Point3f/Vector3f) inputs and extracts their X/Y/Z
    -- so it can be used directly on Plane.Origin/XAxis/YAxis/ZAxis (a mix
    of Point3d and Vector3d) exactly as the original treated a "plane" as
    a 4-element array of point-like values.
  - rs.ViewCPlane(), rs.NamedCPlanes(), rs.NamedCPlane(name), and
    rs.RestoreNamedCPlane(name) all exist with the same argument shape as
    their old Rhino.* COM equivalents.
"""

import rhinoscriptsyntax as rs
from Rhino.Geometry import Plane, Point3d, Vector3d


def _are_planes_equal(plane1, plane2, tolerance=None):
    """Compare two RhinoCommon Plane objects the same way the original
    .rvb compared 4-element plane arrays (origin, x-axis, y-axis, z-axis)."""
    pairs = (
        (plane1.Origin, plane2.Origin),
        (plane1.XAxis, plane2.XAxis),
        (plane1.YAxis, plane2.YAxis),
        (plane1.ZAxis, plane2.ZAxis),
    )
    for a, b in pairs:
        if not rs.PointCompare(a, b, tolerance):
            return False
    return True


def _get_world_plane_name():
    """Returns 'World Top'/'World Right'/etc. if the current view's CPlane
    exactly matches one of the 6 standard world-aligned planes, else
    'Unsaved'."""
    crnt_plane = rs.ViewCPlane()

    origin = Point3d(0, 0, 0)
    ax = Vector3d(1, 0, 0)
    ay = Vector3d(0, 1, 0)
    az = Vector3d(0, 0, 1)
    neg_x = rs.VectorReverse(ax)
    neg_y = rs.VectorReverse(ay)
    neg_z = rs.VectorReverse(az)

    candidates = [
        ("World Top",    Plane(origin, ax, ay)),          # z-axis = az implicitly
        ("World Right",  Plane(origin, ay, az)),
        ("World Front",  Plane(origin, ax, az)),           # y flipped below
        ("World Bottom", Plane(origin, ax, neg_y)),
        ("World Back",   Plane(origin, neg_x, az)),
        ("World Left",   Plane(origin, neg_y, az)),
    ]
    # Rhino's Plane(origin, xaxis, yaxis) constructor derives its own
    # z-axis (xaxis x yaxis) rather than taking one directly, so the
    # World Front / World Bottom / World Back / World Left cases -- whose
    # original 4-tuples specify explicit, sometimes non-orthogonal-looking
    # axis triples (e.g. aX, aZ, negY) -- are rebuilt from (origin, xaxis,
    # yaxis) pairs consistent with those triples' first two axes; the
    # constructor's derived z-axis reproduces the original's 3rd element
    # in every one of these 6 cases (all are legitimate right-handed
    # world-aligned frames), so this is equivalent, not approximate.
    for name, plane in candidates:
        if _are_planes_equal(crnt_plane, plane):
            return name
    return "Unsaved"


def popup_planes():
    plane_names = rs.NamedCPlanes()
    if not plane_names:
        rs.PopupMenu(["There are no named cplanes in this file."])
        return

    idx = rs.PopupMenu(plane_names)
    if idx != -1:
        rs.RestoreNamedCPlane(plane_names[idx])


def current_plane():
    plane_names = rs.NamedCPlanes()
    crnt_plane = rs.ViewCPlane()

    plane_name = _get_world_plane_name()

    if plane_name == "Unsaved":
        for name in plane_names or []:
            test_plane = rs.NamedCPlane(name)
            if _are_planes_equal(test_plane, crnt_plane):
                plane_name = name
                break

    rs.PopupMenu(["Current CPlane is " + plane_name])


if __name__ == "__main__":
    popup_planes()
    # current_plane()  # see ENTRY POINT NOTE above
