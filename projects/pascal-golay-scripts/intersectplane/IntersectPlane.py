"""
IntersectPlane.py

Python 3 (CPython, PythonNet bridge) port of IntersectPlane.rvb, for
Rhino 8's Script Editor (run via the ScriptEditor command, F5). Do NOT run
this through the legacy RunPythonScript command -- that invokes the
IronPython 2 engine.

Original behavior (Pascal Golay, legacy RhinoScript/VBScript, 2008):
  finds the intersections of objects and infinite planes defined by
  1. A selected planar surface of any size
  2. The current cplane
  3. World and local XY, ZX, YZ planes (Local XY = current cplane)
  4. Named Cplanes
  5. 3-point user-defined planes
  6. A tangent plane on a surface at a picked point
  7. A "cut plane" defined by two picked points and the current cplane's Z
  Four aliases shared this logic via one intTrim parameter:
    IntersectPlane (0)        -- intersect selected objects with the plane,
                                 report/select the resulting curves/points.
    TrimWithPlane (1)         -- ghost-display the plane in every view and
                                 kick off an interactive _Trim.
    SplitWithPlane (2)        -- run _Split against the plane surface.
    BooleanSplitWithPlane (3) -- run _BooleanSplit against the plane surface.
  A temporary oversized PlaneSurface is built (sized to the selection's
  bounding-box diagonal, recentered), used as the cutting object for
  whichever intTrim operation was requested, then deleted.

Porting notes:
  - Rhino.AddStartUpScript / Rhino.AddAlias have no equivalent for a
    CPython3 Script Editor file; this port defines intersect_plane(),
    trim_with_plane(), split_with_plane(), and boolean_split_with_plane(),
    and calls intersect_plane() at the bottom when run directly.
  - `Private sOldPlaneType, OldCplaneType` (VBScript module-level state that
    persisted across repeated alias calls within one Rhino session, so the
    plane-type prompt remembered your last choice) is replicated with plain
    module-level globals (`_last_plane_type`, `_last_cplane_type`), which
    persist for the lifetime of the running Script Editor session/process
    the same way. This is functionally equivalent for a single session, but
    won't survive separate script runs the way old startup-script-injected
    module vars effectively did across the whole Rhino session -- if you
    need that persistence, store the value in rhinoscriptsyntax's document
    user text (`rs.SetDocumentUserText`) instead.
  - Function-name mappings verified 2026 against the mcneel/rhinoscriptsyntax
    GitHub source (rhino-8.x branch): GetObjects, GetObject, GetString,
    GetPoints, ListBox, IsSurface, IsSurfacePlanar, IsCurve, IsCurvePlanar,
    IsPointCloud, IsMesh, IsClippingPlane, SurfaceDomain, SurfaceFrame,
    SurfaceNormal, SurfaceClosestPoint, CurvePlane, PlaneFitFromPoints,
    PointCloudPoints, MeshVertices, ViewCPlane, WorldXYPlane, WorldZXPlane,
    WorldYZPlane, RotatePlane, NamedCPlanes, NamedCPlane, PlaneFromPoints,
    PlaneFromNormal, PlaneClosestPoint, BoundingBox, Distance,
    VectorUnitize, VectorScale, VectorAdd, VectorReverse, PointAdd,
    AddPlaneSurface, SurfaceIsocurveDensity, UnselectAllObjects,
    SelectObject, SelectObjects, CurrentView, ViewNames, NormalObjects,
    Command, LastCommandResult, SelectedObjects, DeleteObject, Print all
    exist there with the signatures used below.
  - Rhino.ClippingPlaneDefinition has NO rhinoscriptsyntax equivalent
    (confirmed absent from both object.py and geometry.py source). Ported
    by dropping to RhinoCommon directly: a clipping plane's underlying
    geometry is a Rhino.Geometry.ClippingPlaneSurface, which derives from
    PlaneSurface and inherits its settable/gettable `.Plane` property
    (confirmed 2026 via developer.rhino3d.com's live RhinoCommon API data).
    See get_clipping_plane_definition() below.
  - Rhino.Pt2Str has no rhinoscriptsyntax equivalent; only used here for a
    diagnostic Print of the plane origin, so replaced with a plain
    str(point) call -- purely cosmetic, doesn't affect script logic.
  - WhereInArray (hand-rolled case-insensitive linear search) is ported
    as-is as a small helper rather than replaced with Python's list.index,
    since the original always calls it with intCase=1 (case-insensitive)
    and returns -1 (not an exception) on no match -- preserving that
    contract exactly matters here because several call sites check for -1.
  - AveragePoints (hand-rolled centroid of a point list) is ported directly;
    rhinoscriptsyntax has no built-in for this.
  - The TangentPlane branch's original VBScript calls
    `Rhino.SurfaceClosestPoint(sSrf, srfPt)` TWICE (once passed directly
    into PlaneFromNormal's SurfaceNormal call, and implicitly again inside
    that same expression -- actually the same call is written twice
    literally in the source). This port calls it once and reuses the
    result, which is behaviorally identical (deterministic, side-effect
    free query) and not a functional change, just avoiding a redundant
    call.
  - The TrimWithPlane path's ghosted-display-mode loop, and the final
    interactive `_Trim` command, are preserved as fire-and-continue
    `rs.Command(...)` calls exactly as in the original -- these are
    inherently interactive (the user still has to click to finish the
    trim), not something this port can or should make non-interactive.
  - Bug NOTED, not fixed: in the "Select" plane-type branch, if the picked
    object is a non-planar surface, non-planar curve, or an unrecognized
    type, the original leaves `aPlane` undefined (VBScript would treat it
    as Empty) and execution continues into the redraw/bounding-box code
    below, which would then fail. This port makes that failure explicit:
    if aPlane could not be determined, it prints a message and returns
    instead of continuing with an undefined plane, which is a
    micro-behavior-change (explicit early exit vs. an eventual
    ilo-defined runtime type error) but avoids leaving the script in an
    inconsistent state (grips/redraw disabled, etc.) -- flagged here as a
    deliberate change.

Limitation: no live Rhino available in this environment to actually run the
script -- validated only with `python3 -m py_compile` (syntax parses) and a
manual read-through against the rhinoscriptsyntax source. Test in Script
Editor before relying on it.
"""

import scriptcontext
import rhinoscriptsyntax as rs

PLANE_TYPES = ["Select", "CurrentCPlane", "CPlanes", "NamedCplane", "3pt", "TangentPlane", "CutPlane"]
CPLANE_TYPES = ["XY", "XZ", "YZ", "WorldXY", "WorldZX", "WorldYZ"]

_last_plane_type = "Select"
_last_cplane_type = "WorldXY"


def where_in_array(item, arr, case_insensitive=True):
    """Index of `item` in `arr`, or -1 if not found. Mirrors the original
    WhereInArray helper (always called case-insensitively in this script)."""
    needle = item.lower() if case_insensitive else item
    for i, value in enumerate(arr):
        candidate = value.lower() if case_insensitive else value
        if candidate == needle:
            return i
    return -1


def average_points(pts):
    """Centroid of a list of 3D points."""
    x = sum(p[0] for p in pts)
    y = sum(p[1] for p in pts)
    z = sum(p[2] for p in pts)
    n = len(pts)
    return (x / n, y / n, z / n)


def get_clipping_plane_definition(object_id):
    """Rhino.ClippingPlaneDefinition equivalent -- no rhinoscriptsyntax
    wrapper exists, so this drops to RhinoCommon directly. See module
    docstring."""
    robj = scriptcontext.doc.Objects.Find(object_id)
    if robj is None:
        return None
    geom = robj.Geometry  # Rhino.Geometry.ClippingPlaneSurface
    return geom.Plane


def intersect_the_plane(int_trim):
    global _last_plane_type, _last_cplane_type

    obj_ids = None
    if int_trim in (0, 2, 3):
        obj_ids = rs.GetObjects("Select objects. Press Enter when done.", preselect=True, select=True)
        if not obj_ids:
            return

    plane_type = rs.GetString("Plane type", _last_plane_type, PLANE_TYPES)
    if plane_type is None:
        return

    pos = where_in_array(plane_type, PLANE_TYPES)
    if pos == -1:
        return
    plane_type = PLANE_TYPES[pos]
    _last_plane_type = plane_type
    plane_type = plane_type.upper()

    a_plane = None

    if plane_type == "SELECT":
        # 2+4+8+16+32+536870912 = point + curve + surface + polysurface +
        # mesh + clipping plane (rs.filter bit flags, unchanged from the
        # original RhinoScript object-type constants).
        sel_filter = 2 + 4 + 8 + 16 + 32 + 536870912
        s_plane_obj = rs.GetObject("Select object to set plane.", sel_filter)
        if s_plane_obj is None:
            return

        if rs.IsSurface(s_plane_obj) and not rs.IsClippingPlane(s_plane_obj):
            if rs.IsSurfacePlanar(s_plane_obj):
                param_u = rs.SurfaceDomain(s_plane_obj, 0)
                dbl_u = (param_u[1] + param_u[0]) / 2
                param_v = rs.SurfaceDomain(s_plane_obj, 1)
                dbl_v = (param_v[1] + param_v[0]) / 2
                a_plane = rs.SurfaceFrame(s_plane_obj, (dbl_u, dbl_v))
            else:
                rs.MessageBox("The surface must be planar", 0, "IntersectPlane")
        elif rs.IsCurve(s_plane_obj):
            if not rs.IsCurvePlanar(s_plane_obj):
                rs.MessageBox("The curve must be planar", 0, "IntersectPlane")
            else:
                a_plane = rs.CurvePlane(s_plane_obj)
        elif rs.IsPointCloud(s_plane_obj):
            a_plane = rs.PlaneFitFromPoints(rs.PointCloudPoints(s_plane_obj))
        elif rs.IsMesh(s_plane_obj):
            a_plane = rs.PlaneFitFromPoints(rs.MeshVertices(s_plane_obj))
        elif rs.IsClippingPlane(s_plane_obj):
            a_plane = get_clipping_plane_definition(s_plane_obj)

    elif plane_type == "CURRENTCPLANE":
        a_plane = rs.ViewCPlane(rs.CurrentView())

    elif plane_type == "CPLANES":
        cplane_type = rs.GetString("Choose Cplane", _last_cplane_type, CPLANE_TYPES)
        if cplane_type is None:
            return

        pos = where_in_array(cplane_type, CPLANE_TYPES)
        if pos == -1:
            return
        _last_cplane_type = CPLANE_TYPES[pos]

        if pos == 0:
            a_plane = rs.ViewCPlane(rs.CurrentView())
        elif pos == 1:
            # VBScript indexed the plane-as-array at (1) = X-axis.
            base_plane = rs.ViewCPlane(rs.CurrentView())
            a_plane = rs.RotatePlane(base_plane, 90, base_plane.XAxis)
        elif pos == 2:
            # VBScript indexed the plane-as-array at (2) = Y-axis.
            base_plane = rs.ViewCPlane(rs.CurrentView())
            a_plane = rs.RotatePlane(base_plane, 90, base_plane.YAxis)
        elif pos == 3:
            a_plane = rs.WorldXYPlane()
        elif pos == 4:
            a_plane = rs.WorldZXPlane()
        elif pos == 5:
            a_plane = rs.WorldYZPlane()
        else:
            return

    elif plane_type == "NAMEDCPLANE":
        named = rs.NamedCPlanes()
        if named:
            s_named = rs.ListBox(named, "Select saved Cplane", "Saved Cplanes")
            if s_named is None:
                return
            a_plane = rs.NamedCPlane(s_named)
        else:
            rs.MessageBox(
                "The NamedCPlanes option allows selection of CPlanes that are named "
                "and saved in the file.\nNo named CPlanes were found in the file.",
                0,
                "IntersectPlane",
            )
            return

    elif plane_type == "3PT":
        plane_pts = rs.GetPoints(True, False, "First plane point", "Next plane point", 3)
        if not plane_pts or len(plane_pts) != 3:
            return
        a_plane = rs.PlaneFromPoints(plane_pts[0], plane_pts[1], plane_pts[2])

    elif plane_type == "TANGENTPLANE":
        s_srf = rs.GetObject("Select surface.", 8)
        if s_srf is None:
            return
        srf_pt = rs.GetPointOnSurface(s_srf, "Set tangent point.")
        if not srf_pt:
            return
        uv = rs.SurfaceClosestPoint(s_srf, srf_pt)
        a_plane = rs.PlaneFromNormal(srf_pt, rs.SurfaceNormal(s_srf, uv))

    elif plane_type == "CUTPLANE":
        cut_pts = rs.GetPoints(True, True, "Start of cut plane", "End of cut plane", 2)
        if not cut_pts or len(cut_pts) != 2:
            return
        # VBScript indexed the plane-as-array at (3) = Z-axis.
        third_pt = rs.PointAdd(cut_pts[0], rs.ViewCPlane(rs.CurrentView()).ZAxis)
        a_plane = rs.PlaneFromPoints(cut_pts[0], cut_pts[1], third_pt)

    else:
        return

    if a_plane is None:
        rs.Print("Could not determine a plane from that selection.")
        return

    rs.EnableRedraw(False)

    crnt_plane = rs.ViewCPlane(rs.CurrentView())

    rs.Print(str(a_plane.Origin))
    rs.ViewCPlane(rs.CurrentView(), a_plane)

    if int_trim != 1:
        bb_plane = rs.BoundingBox(obj_ids, rs.CurrentView())
    else:
        bb_plane = rs.BoundingBox(rs.NormalObjects(), rs.CurrentView())

    if not bb_plane:
        rs.ViewCPlane(rs.CurrentView(), crnt_plane)
        rs.EnableRedraw(True)
        rs.Print("Could not compute a bounding box to size the cutting plane.")
        return

    dbl_dist = rs.Distance(bb_plane[0], bb_plane[6])

    a_plane.Origin = rs.PlaneClosestPoint(a_plane, average_points([bb_plane[0], bb_plane[2]]))

    vec_x = rs.VectorScale(rs.VectorUnitize(a_plane.XAxis), dbl_dist)
    vec_y = rs.VectorScale(rs.VectorUnitize(a_plane.YAxis), dbl_dist)
    vec_xy = rs.VectorAdd(vec_x, vec_y)
    vec_xy = rs.VectorReverse(rs.VectorScale(vec_xy, 0.5))

    a_plane.Origin = rs.PointAdd(a_plane.Origin, vec_xy)

    s_test_plane = rs.AddPlaneSurface(a_plane, dbl_dist, dbl_dist)

    rs.ViewCPlane(rs.CurrentView(), crnt_plane)

    if int_trim == 1:
        rs.SurfaceIsocurveDensity(s_test_plane, 0)
        rs.UnselectAllObjects()
        rs.SelectObject(s_test_plane)

        s_view = rs.CurrentView()
        views = rs.ViewNames(False, 0)
        for view_id in views:
            rs.CurrentView(view_id)
            rs.Command("_SetObjectDisplayMode _Mode=Ghosted", False)
        rs.CurrentView(s_view)

    result = []

    if int_trim == 0:
        for obj_id in obj_ids:
            rs.UnselectAllObjects()
            rs.SelectObject(obj_id)
            rs.SelectObject(s_test_plane)
            rs.Command("_Intersect _NoEcho ", False)

            if rs.LastCommandResult() == 0:
                last = rs.SelectedObjects()
                if last:
                    result.extend(last)

        if result:
            rs.SelectObjects(result)

    if int_trim == 0:
        rs.Print("{0} intersections found.".format(len(result)))

    elif int_trim == 1:
        rs.UnselectAllObjects()
        rs.SelectObject(s_test_plane)
        rs.Command("_SetObjectDisplayMode _Ghosted", False)
        rs.EnableRedraw(True)
        rs.Command("_Trim")

    elif int_trim == 2:
        rs.UnselectAllObjects()
        rs.SelectObjects(obj_ids)
        rs.Command("_Split _SelID " + str(s_test_plane) + " _Enter")

    else:
        rs.UnselectAllObjects()
        rs.SelectObjects(obj_ids)
        rs.Command("_BooleanSplit _SelID " + str(s_test_plane) + " _Enter")

    rs.DeleteObject(s_test_plane)
    rs.ViewCPlane(rs.CurrentView(), crnt_plane)
    rs.EnableRedraw(True)


def intersect_plane():
    intersect_the_plane(0)


def trim_with_plane():
    intersect_the_plane(1)


def split_with_plane():
    intersect_the_plane(2)


def boolean_split_with_plane():
    intersect_the_plane(3)


if __name__ == "__main__":
    # Original had four aliases (IntersectPlane / TrimWithPlane /
    # SplitWithPlane / BooleanSplitWithPlane) sharing this logic. Default to
    # plain intersection; call one of the other three functions instead (or
    # edit this line) for the other behaviors.
    intersect_plane()
