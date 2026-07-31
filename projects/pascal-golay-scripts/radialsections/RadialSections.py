"""RadialSections.py

Ported from RadialSections.rvb (2010) - legacy VBScript/RhinoScript engine
- to Python 3 for Rhino 8's Script Editor (CPython 3 engine). Run via the
Script Editor's F5, not via the legacy `RunPythonScript` (IronPython 2)
command.

Two independent commands, same as the original:
  - section_radial(): fan out cutting planes at a fixed angular step around
    a center point/axis and intersect them with the selected objects.
  - section_path(): step a cutting plane at a fixed spacing along a path
    curve (oriented by the curve's tangent at each step) and intersect it
    with the selected objects.

Function names verified live this session against the modern
rhinoscriptsyntax source (github.com/mcneel/rhinoscriptsyntax, rhino-8.x
branch): GetObjects, GetObject, GetPoints, GetReal, DivideCurveLength,
CurveStartPoint, CurveTangent, CurveDomain, CurveClosestPoint,
VectorRotate/VectorScale/VectorReverse/VectorUnitize/VectorCreate,
PlaneFromFrame, AddPlaneSurface, EvaluateSurface, SurfaceDomain,
MoveObject, XformRotation1 (this is the modern name for the old
overloaded `Rhino.XformRotation(plane1, plane2)` plane-to-plane variant -
rhinoscriptsyntax splits that overload into XformRotation1..4 by
signature), TransformObject, IntersectBreps, CurveSurfaceIntersection,
IsSurface/IsBrep/IsCurve, BoundingBox, Distance, UnitAbsoluteTolerance -
all exist with the call signatures used here.

Persistence note: the original's `Private oldStep, oldSpace` module-level
variables relied on the legacy RVB engine keeping one interpreter alive
across runs (via Rhino.AddStartupScript/AddAlias). CPython3 script-editor
runs re-execute the module fresh each time, so this port uses Rhino's
sticky dictionary (scriptcontext.sticky) as the standard modern equivalent
for "remember the last value entered" - not a literal translation, since
none exists.

Bug note (kept, not fixed - matches original behavior exactly): in
section_path(), if the path curve has a negative-tangent surprise near its
start point or the objects extend behind the path's start, only the plane
frame at the *start point* is used to build the base intersection plane
before iterating forward - this matches the original's design intent
(planes are always built relative to the curve's own tangent frame at each
division point via XformRotation1, so a globally-inconsistent base frame
mostly self-corrects each step). Not treated as a bug to fix, just noting
the geometry assumption for anyone extending this.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc


def mid_param(surface_id):
    """Middle (u, v) parameter pair of a surface's domain."""
    u_dom = rs.SurfaceDomain(surface_id, 0)
    v_dom = rs.SurfaceDomain(surface_id, 1)
    u_mid = u_dom[0] + 0.5 * (u_dom[1] - u_dom[0])
    v_mid = v_dom[0] + 0.5 * (v_dom[1] - v_dom[0])
    return u_mid, v_mid


def bb_diag(obj_ids):
    """Bounding-box diagonal length for a set of objects (corner 0 to
    corner 6 of the 8-point rs.BoundingBox result, same as the original)."""
    bbox = rs.BoundingBox(obj_ids)
    return rs.Distance(bbox[0], bbox[6])


def intersect_objects_with_srf(obj_ids, srf_id):
    """Intersect each object with a cutting surface: breps/surfaces via
    IntersectBreps (creates curve/point objects directly), curves via
    CurveSurfaceIntersection (only the "Point"-type events, matching the
    original's `allint(i,0) = 1` filter, are turned into point objects).
    Selects everything created, same as the original."""
    for obj_id in obj_ids:
        result_ids = None

        if rs.IsSurface(obj_id) or rs.IsBrep(obj_id):
            result_ids = rs.IntersectBreps(srf_id, obj_id)
        elif rs.IsCurve(obj_id):
            all_int = rs.CurveSurfaceIntersection(obj_id, srf_id)
            if all_int:
                temp = []
                for event in all_int:
                    if event[0] == 1:  # Point-type event
                        temp.append(rs.AddPoint(event[1]))
                result_ids = temp

        if result_ids:
            rs.SelectObjects(result_ids)


def section_path():
    obj_ids = rs.GetObjects("Select objects to section", 4 + 8 + 16, preselect=True)
    if not obj_ids:
        return

    path_id = rs.GetObject("Select path curve for sections", 4)
    if not path_id:
        return

    old_space = sc.sticky.get("RadialSections_OldSpace", 10)
    dbl_space = rs.GetReal("Spacing", old_space, rs.UnitAbsoluteTolerance() * 10)
    if dbl_space is None:
        return
    sc.sticky["RadialSections_OldSpace"] = dbl_space

    a_div = rs.DivideCurveLength(path_id, dbl_space)
    if not a_div:
        return

    rs.EnableRedraw(False)

    # Bounding-box diagonal for the objects plus the path start point,
    # used to size the cutting plane big enough to clear everything.
    start_pt = rs.CurveStartPoint(path_id)
    pt_id = rs.AddPoint(start_pt)
    temp_ids = list(obj_ids) + [pt_id]
    dbl_scale = bb_diag(temp_ids)
    rs.DeleteObject(pt_id)

    cplane_z = rs.ViewCPlane().ZAxis
    start_tan = rs.CurveTangent(path_id, rs.CurveDomain(path_id)[0])
    vec_x = rs.VectorScale(rs.VectorRotate(start_tan, 90, cplane_z), dbl_scale)
    vec_y = rs.VectorScale(cplane_z, dbl_scale)
    a_base = start_pt
    a_plane = rs.PlaneFromFrame(a_base, vec_x, vec_y)
    plane_srf = rs.AddPlaneSurface(a_plane, dbl_scale, dbl_scale * 2)
    rs.MoveObject(plane_srf, rs.EvaluateSurface(plane_srf, *mid_param(plane_srf)), a_base)

    base_plane = rs.PlaneFromNormal(start_pt, start_tan)

    for div_pt in a_div:
        t = rs.CurveClosestPoint(path_id, div_pt)
        tangent = rs.CurveTangent(path_id, t)
        temp_plane = rs.PlaneFromNormal(div_pt, tangent)

        xform = rs.XformRotation1(base_plane, temp_plane)
        temp_plane_obj = rs.TransformObject(plane_srf, xform, True)

        intersect_objects_with_srf(obj_ids, temp_plane_obj)

        rs.DeleteObject(temp_plane_obj)

    rs.DeleteObject(plane_srf)
    rs.EnableRedraw(True)


def section_radial():
    obj_ids = rs.GetObjects("Select objects to section", 4 + 8 + 16, preselect=True)
    if not obj_ids:
        return

    a_cen = rs.GetPoints(True, True, "Center point", "Direction", 2)
    if not a_cen or len(a_cen) != 2:
        return

    old_step = sc.sticky.get("RadialSections_OldStep", 30)
    dbl_deg = rs.GetReal("Step angle", old_step, -180, 180)
    if dbl_deg is None:
        return
    sc.sticky["RadialSections_OldStep"] = dbl_deg

    rs.EnableRedraw(False)
    pt_id = rs.AddPoint(a_cen[0])
    temp_ids = list(obj_ids) + [pt_id]
    dbl_scale = bb_diag(temp_ids)
    rs.DeleteObject(pt_id)

    cplane_z = rs.ViewCPlane().ZAxis
    vec_x = rs.VectorScale(rs.VectorUnitize(rs.VectorCreate(a_cen[1], a_cen[0])), dbl_scale)
    vec_y = rs.VectorScale(cplane_z, dbl_scale)
    a_base = rs.PointAdd(a_cen[0], rs.VectorReverse(vec_y))
    a_plane = rs.PlaneFromFrame(a_base, vec_x, vec_y)
    plane_srf = rs.AddPlaneSurface(a_plane, dbl_scale, dbl_scale * 2)

    deg_count = 0
    while True:
        intersect_objects_with_srf(obj_ids, plane_srf)
        rs.RotateObject(plane_srf, a_base, dbl_deg, cplane_z, False)
        deg_count += dbl_deg
        if deg_count >= 360:
            break

    rs.DeleteObject(plane_srf)
    rs.EnableRedraw(True)


if __name__ == "__main__":
    section_radial()
    # section_path()
