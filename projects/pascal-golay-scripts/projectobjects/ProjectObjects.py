"""ProjectObjects.py

Ported from ProjectObjects.rvb (Pascal Golay, McNeel, 2009) - the legacy
VBScript/RhinoScript engine - to Python 3 for Rhino 8's Script Editor
(CPython 3 engine). Run this file via the Script Editor's F5 command, NOT
via the legacy `RunPythonScript` command (that runs IronPython 2, a
different engine).

What it does: builds a CageEdit (morph control) box around the selected
objects, then drags each pair of cage control points onto a target
surface/polysurface along a chosen projection direction (world Z, the
current CPlane's Z, or a user-picked direction), which "wraps" a copy (or
the originals) of the selection onto the target.

Function-name mapping verified live against the modern rhinoscriptsyntax
source (github.com/mcneel/rhinoscriptsyntax, rhino-8.x branch,
Scripts/rhinoscript/*.py) this session - not from memory. Notably,
VectorCreate/VectorUnitize/VectorReverse/VectorScale/PointAdd/
ProjectPointToSurface/XformRotation1 all exist in modern rhinoscriptsyntax
with (mostly) the same call signatures as the legacy engine used; the one
real rename is Rhino.XformRotation(plane1, plane2) -> rs.XformRotation1(
plane1, plane2) (modern rhinoscriptsyntax splits the old overloaded
XformRotation into XformRotation1..4 by signature).

Persistence note: the original used script-level `Private` variables
(OldXpts, OldYpts, OldDir, OldSide) that survived between runs because the
legacy RVB engine kept one interpreter process alive across invocations
launched via Rhino.AddStartUpScript/AddAlias. CPython3 script-editor runs
re-execute the module fresh every time, so there is no in-process
persistence to port. This version uses Rhino's sticky dictionary
(scriptcontext.sticky) instead, which is the standard modern equivalent
for "remember last value entered" - closest available analog, not a
literal translation.

Known original-script quirk kept (not a bug, just worth flagging): the
CageEdit object type filter value 131072 corresponds to "Morph control"
objects (Rhino.DocObjects.ObjectType.MorphControl) - that is what
`_CageEdit` actually creates - NOT the unrelated 134217728 "Cage" object
type that also exists in the modern object-type enum. Kept the original's
131072 value (rs.filter.morph) since that's the one that actually matches
CageEdit's output.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino


def is_string_in_array(item, arr, case_sensitive=False):
    """Case-insensitive (default) or case-sensitive membership test."""
    if case_sensitive:
        return item in arr
    item_l = item.lower()
    return any(str(s).lower() == item_l for s in arr)


def move_cage_points(grips, cage_id, target_id, direction):
    """Project each grip-point pair onto target_id along `direction` and
    slide the pair together by the resulting offset. Returns False if any
    point fails to project (typically because the target's trimmed area
    doesn't reach far enough in the projection direction to be hit by
    every cage point)."""
    for i in range(0, len(grips), 2):
        pt1 = grips[i]
        pt2 = grips[i + 1]

        targ_pts = rs.ProjectPointToSurface([pt1], target_id, direction)
        if not targ_pts:
            return False

        vector = rs.VectorCreate(targ_pts[0], pt1)
        rs.ObjectGripLocation(cage_id, i, rs.PointAdd(pt1, vector))
        rs.ObjectGripLocation(cage_id, i + 1, rs.PointAdd(pt2, vector))

    return True


def project_objects():
    captives = rs.GetObjects("Select objects to project.", preselect=True)
    if not captives:
        return

    target = rs.GetObject(
        "Select target surface or polysurface", rs.filter.surface + rs.filter.polysurface
    )
    if not target:
        return

    crnt_view = rs.CurrentView()
    crnt_plane = rs.ViewCPlane(crnt_view)

    bln_copy = rs.GetBoolean("Copy?", ("Copy", "No", "Yes"), (True,))
    if bln_copy is None:
        return

    if bln_copy[0]:
        rs.CopyObjects(captives)

    a_dir = ("WorldZ", "CplaneZ", "User")
    old_dir = sc.sticky.get("ProjectObjects_OldDir", "CplaneZ")
    s_dir = rs.GetString("Projection direction", old_dir, a_dir)
    if s_dir is None:
        return

    if not is_string_in_array(s_dir, a_dir):
        return
    sc.sticky["ProjectObjects_OldDir"] = s_dir

    a_temp = None
    vec_dir = None
    s_dir_l = s_dir.lower()

    if s_dir_l == "worldz":
        vec_dir = (0, 0, 1)
    elif s_dir_l == "cplanez":
        vec_dir = crnt_plane.ZAxis
    elif s_dir_l == "user":
        a_temp = rs.GetPoints(True, False, "First direction point", "Second direction point.", 2)
        if not a_temp or len(a_temp) != 2:
            return
        vec_dir = rs.VectorUnitize(rs.VectorCreate(a_temp[1], a_temp[0]))

    old_side = sc.sticky.get("ProjectObjects_OldSide", (True,))
    bln_side = rs.GetBoolean(
        "Project to top side of target?", ("ProjectTo", "Bottom", "Top"), old_side
    )
    if bln_side is None:
        return
    sc.sticky["ProjectObjects_OldSide"] = bln_side

    max_density = 50
    old_xpts = sc.sticky.get("ProjectObjects_OldXpts", 4)
    x_pts = rs.GetInteger("X density", old_xpts, 2, max_density)
    if x_pts is None:
        return
    sc.sticky["ProjectObjects_OldXpts"] = x_pts

    old_ypts = sc.sticky.get("ProjectObjects_OldYpts", 4)
    y_pts = rs.GetInteger("Y density", old_ypts, 2, max_density)
    if y_pts is None:
        return
    sc.sticky["ProjectObjects_OldYpts"] = y_pts

    rs.EnableRedraw(False)
    rs.CurrentView(crnt_view)

    if s_dir_l == "user":
        # Original computed this plane but never used it further - kept as a
        # faithful, side-effect-free port; harmless dead code in the source.
        rs.PlaneFromNormal(a_temp[0], vec_dir)

    if not bln_side[0]:
        if s_dir_l == "cplanez":
            cplane = rs.ViewCPlane()
            flipped = rs.PlaneFromFrame(cplane.Origin, cplane.ZAxis, cplane.YAxis)
            rs.ViewCPlane(rs.CurrentView(), flipped)
        elif s_dir_l == "worldz":
            rs.ViewCPlane(rs.CurrentView(), rs.PlaneFromFrame((0, 0, 0), (0, 1, 0), (1, 0, 0)))
    else:
        if s_dir_l == "worldz":
            rs.ViewCPlane(rs.CurrentView(), rs.WorldXYPlane())

    rs.UnselectAllObjects()
    rs.SelectObjects(captives)

    cmd_str = "_CageEdit _BoundingBox _CPlane"
    cmd_str += " _XPointCount {}".format(x_pts)
    cmd_str += " _YPointCount {}".format(y_pts)
    cmd_str += " _ZPointCount 2 "
    cmd_str += " _XDegree=3 _YDegree=3 _ZDegree=1"
    cmd_str += " _Enter _Enter"
    print(cmd_str)

    rs.Command(cmd_str, False)

    cage = None
    if rs.LastCommandResult() == 0:
        cage_objs = rs.ObjectsByType(rs.filter.morph)
        if cage_objs:
            cage = cage_objs[0]

    if cage is None:
        rs.ViewCPlane(crnt_view, crnt_plane)
        rs.EnableRedraw(True)
        return

    rs.EnableObjectGrips(cage)
    grips = rs.ObjectGripLocations(cage)

    moved = move_cage_points(grips, cage, target, vec_dir)

    if not moved:
        if bln_copy[0]:
            rs.DeleteObjects(captives)
        rs.DeleteObject(cage)
        rs.EnableRedraw(True)
        rs.MessageBox(
            "The bounding box of the objects must fit within the target object "
            "edges in the projection direction.\n"
            "Try untrimming the target, or otherwise expanding it."
        )
        return

    rs.EnableObjectGrips(cage, False)
    rs.ViewCPlane(crnt_view, crnt_plane)
    rs.DeleteObject(cage)
    rs.EnableRedraw(True)


if __name__ == "__main__":
    project_objects()
