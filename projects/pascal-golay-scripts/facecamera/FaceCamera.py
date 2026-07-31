"""
FaceCamera.py

Python 3 (CPython) port of FaceCamera.rvb, for Rhino 8's Script Editor
(ScriptEditor command, run with F5). Not for the legacy
RunPythonScript/IronPython 2 engine.

Original by Pascal Golay (McNeel), 2011-02-23.

Rotates each selected surface, polysurface, or mesh about the world Z
axis, around its own area centroid, until its face normal (flattened
onto the world XY plane, i.e. ignoring tilt/pitch) points toward the
active viewport's camera (also flattened onto world XY). This gives a
"billboard" yaw rotation - useful for turning signage-like flat or
curved panels to face the viewer without changing their tilt.

Function/API mappings verified 2026 against mcneel/rhinoscriptsyntax
GitHub source (rhino-8.x branch) via WebFetch this session:
  - rs.ViewCameraTarget() with no args returns (camera_point, target_point).
  - rs.VectorCreate(to_point, from_point) returns (to_point - from_point) -
    note the argument order: it is NOT (from, to).
  - rs.WorldXYPlane()/rs.PlaneFitFromPoints(...) return a
    Rhino.Geometry.Plane object (not an indexable array like the old
    VBScript plane arrays) - use .Origin/.ZAxis, not plane(0)/plane(3).
  - rs.IsVectorParallelTo(vector1, vector2) takes exactly two arguments;
    there is no angle-tolerance parameter in the current API (a docs
    excerpt initially suggested otherwise - the actual GitHub source
    confirms only 2 params).
  - The old GetObjects positional order (message, filter, preselect,
    select) is NOT the same as the modern rs.GetObjects(message, filter,
    group, preselect, select, ...) - the 3rd positional slot changed
    meaning (group vs. preselect). This port uses keyword arguments for
    preselect/select to avoid silently mis-mapping them.

There is no rs.ExtractRenderMesh / rs.SurfaceCone-style helper for
"give me a representative facing plane of an arbitrary Brep" in modern
rhinoscriptsyntax, so this port replaces the original's
ExtractRenderMesh-command + best-fit-plane approach with the RhinoCommon
equivalent done in memory (Rhino.Geometry.Mesh.CreateFromBrep +
rs.PlaneFitFromPoints) - same technique, but without adding/deleting a
temporary mesh object in the document.

Two deviations from the original, both noted inline below:
  1. The original computed a reversed ObjDir
     (`Rhino.VectorReverse(ObjDir)`) but never assigned the result back
     to ObjDir - almost certainly a bug (VectorReverse returns a new
     vector, it does not mutate in place). This port assigns it, since
     leaving it unassigned would make the "face toward camera, not away"
     check a no-op.
  2. The original's Do/Loop has no iteration cap and could spin forever
     if IsVectorParallelTo never reports exact alignment (e.g. due to
     floating-point noise after a rotation). This port caps it at 8
     iterations per object as a safety net; that is generous headroom
     since a single correctly-signed rotation should normally converge
     in 1 pass, and this algorithm's rotation is unsigned so it may
     need a couple of corrective passes.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino

MAX_ITERATIONS = 8


def project_vector(vec, plane):
    """Projects the direction of vec onto plane, returning a unit
    vector (in the plane) pointing from the plane's origin toward the
    projection of (plane.Origin + vec)."""
    test_pt = rs.PlaneClosestPoint(plane, rs.PointAdd(plane.Origin, vec))
    return rs.VectorUnitize(rs.VectorCreate(test_pt, plane.Origin))


def get_render_mesh(obj_id):
    """Builds a temporary, in-memory joined mesh for a Brep object
    (surface or polysurface), used only to sample vertex points for a
    best-fit plane. Nothing is added to the document."""
    rhobj = sc.doc.Objects.Find(obj_id)
    brep = rhobj.Geometry
    face_meshes = Rhino.Geometry.Mesh.CreateFromBrep(brep, Rhino.Geometry.MeshingParameters.Default)
    if not face_meshes:
        return None
    joined = Rhino.Geometry.Mesh()
    for m in face_meshes:
        joined.Append(m)
    return joined


def brep_plane(obj_id):
    """Best-fit plane through a Brep's render-mesh vertices - an
    approximation of the object's overall facing direction, valid even
    for curved or multi-face surfaces that have no single normal."""
    mesh = get_render_mesh(obj_id)
    if mesh is None or mesh.Vertices.Count == 0:
        return None
    pts = [Rhino.Geometry.Point3d(v) for v in mesh.Vertices]
    return rs.PlaneFitFromPoints(pts)


def mesh_plane(mesh_id):
    """Best-fit plane through a mesh object's own vertices."""
    pts = rs.MeshVertices(mesh_id)
    if not pts:
        return None
    return rs.PlaneFitFromPoints(pts)


def face_camera():
    cam_pt, target_pt = rs.ViewCameraTarget()

    obj_ids = rs.GetObjects(
        "Select surfaces or meshes to face the camera.",
        rs.filter.surface | rs.filter.polysurface | rs.filter.mesh,
        preselect=False,
        select=True,
    )
    if not obj_ids:
        return

    world_xy = rs.WorldXYPlane()

    rs.EnableRedraw(False)

    for obj_id in obj_ids:

        for _ in range(MAX_ITERATIONS):

            if rs.IsMesh(obj_id):
                centroid = rs.MeshAreaCentroid(obj_id)
                plane = mesh_plane(obj_id)
            else:
                centroid = rs.SurfaceAreaCentroid(obj_id)[0]
                plane = brep_plane(obj_id)

            if plane is None or centroid is None:
                rs.Print("Could not determine a facing direction; skipping an object.")
                break

            vec_norm = plane.ZAxis

            vec_dir = project_vector(rs.VectorCreate(cam_pt, centroid), world_xy)
            obj_dir = project_vector(vec_norm, world_xy)

            far_pt = rs.PointAdd(centroid, obj_dir)
            near_pt = rs.PointAdd(centroid, rs.VectorReverse(obj_dir))
            if rs.Distance(centroid, far_pt) > rs.Distance(centroid, near_pt):
                obj_dir = rs.VectorReverse(obj_dir)  # see deviation (1) above

            angle = rs.VectorAngle(vec_dir, obj_dir)

            rs.RotateObject(obj_id, centroid, angle, (0, 0, 1))

            if rs.IsVectorParallelTo(obj_dir, vec_dir) != 0:
                break
        else:
            rs.Print("An object did not fully align after {} attempts.".format(MAX_ITERATIONS))

    rs.EnableRedraw(True)


if __name__ == "__main__":
    face_camera()
