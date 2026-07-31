"""QInfo.py

Ported from QInfo.rvb (2011) - legacy VBScript/RhinoScript engine - to
Python 3 for Rhino 8's Script Editor (CPython 3 engine). Run via the Script
Editor's F5, not via the legacy `RunPythonScript` (IronPython 2) command.

What it does: looks at the currently-selected objects, buckets them into
curves / surfaces / polysurfaces / meshes, and pops a scrollable text
report (Rhino's TextOut dialog) summarizing degree/point/closed-ness for
curves and surfaces, closed-ness for polysurfaces, and face/vertex counts
for meshes, plus a count of any selected objects that didn't fall into one
of those four buckets.

Function names below were checked live this session against the modern
rhinoscriptsyntax source (github.com/mcneel/rhinoscriptsyntax, rhino-8.x
branch) rather than from memory: SelectedObjects, IsCurve/IsSurface/
IsPolysurface/IsMesh, IsCurveClosed, CurvePointCount, CurveDegree,
IsSurfaceClosed, SurfaceDegree, SurfacePointCount, IsPolysurfaceClosed,
IsMeshClosed, MeshVertexCount, MeshFaceCount, TextOut - all exist with the
call signatures used here.

Bug fixed from the original (flagged, not silently ported): in the VBScript
mesh-info loop, `sClosed` was never reset to "Open " at the top of each
iteration (every other loop - curves, surfaces, polysurfaces - does reset
it). That meant a mesh following a closed curve/surface/polysurface in the
selection could get mislabeled "Closed" even when
`Rhino.IsMeshClosed(sObj)` was False, because the stale value from a
previous bucket's loop was reused. Fixed here by resetting the flag each
iteration, matching the (correct) pattern used everywhere else in the
script.
"""

import rhinoscriptsyntax as rs


def qinfo():
    obj_ids = rs.SelectedObjects()
    if not obj_ids:
        return

    crv_ids = []
    srf_ids = []
    poly_ids = []
    mesh_ids = []

    for obj_id in obj_ids:
        if rs.IsCurve(obj_id):
            crv_ids.append(obj_id)
        elif rs.IsSurface(obj_id):
            srf_ids.append(obj_id)
        elif rs.IsPolysurface(obj_id):
            poly_ids.append(obj_id)
        elif rs.IsMesh(obj_id):
            mesh_ids.append(obj_id)

    crv_info = []
    for obj_id in crv_ids:
        s_closed = "Closed " if rs.IsCurveClosed(obj_id) else "Open "
        int_pt = rs.CurvePointCount(obj_id)
        int_deg = rs.CurveDegree(obj_id)
        crv_info.append(
            "{}curve, Degree = {};\t\tPoints = {}.".format(s_closed, int_deg, int_pt)
        )

    srf_info = []
    for obj_id in srf_ids:
        s_closed = "Closed " if (rs.IsSurfaceClosed(obj_id, 0) and rs.IsSurfaceClosed(obj_id, 1)) else "Open "
        int_deg_u = rs.SurfaceDegree(obj_id, 0)
        int_deg_v = rs.SurfaceDegree(obj_id, 1)
        int_pt_u, int_pt_v = rs.SurfacePointCount(obj_id)

        temp = "{} surface.\n\t\tU Degree = {}\n\t\tU Points =  {}".format(s_closed, int_deg_u, int_pt_u)
        temp += "\n\t\tV Degree = {}\n\t\tV Points =  {}".format(int_deg_v, int_pt_v)
        srf_info.append(temp)

    poly_info = []
    for obj_id in poly_ids:
        s_closed = "Closed " if rs.IsPolysurfaceClosed(obj_id) else "Open "
        poly_info.append("{}polysurface.".format(s_closed))

    mesh_info = []
    for obj_id in mesh_ids:
        # Reset each iteration - see docstring "Bug fixed" note.
        s_closed = "Closed " if rs.IsMeshClosed(obj_id) else "Open "
        int_mesh_pt = rs.MeshVertexCount(obj_id)
        int_face = rs.MeshFaceCount(obj_id)
        mesh_info.append(
            "{} mesh with {} faces, {} vertices.".format(s_closed, int_face, int_mesh_pt)
        )

    c, s, p, m = len(crv_ids), len(srf_ids), len(poly_ids), len(mesh_ids)
    if c + s + p + m == 0:
        return

    num = len(obj_ids)
    int_dif = num - (c + s + p + m)

    lines = ["{} objects selected.".format(num)]
    divider = "\n***************\n"

    if c > 0:
        s_crv = " curve:" if c == 1 else " curves:"
        lines.append(divider + str(c) + s_crv)
        for item in crv_info:
            lines.append("\n" + item)
        lines.append("\n")

    if s > 0:
        s_srf = " surface:" if s == 1 else " surfaces:"
        lines.append(divider + str(s) + s_srf)
        for item in srf_info:
            lines.append("\n" + item)
        lines.append("\n")

    if p > 0:
        s_poly = " polysurface:" if p == 1 else " polysurfaces:"
        lines.append(divider + str(p) + s_poly)
        for item in poly_info:
            lines.append("\n" + item)
        lines.append("\n")

    if m > 0:
        s_mesh = " mesh:" if m == 1 else " meshes:"
        lines.append(divider + str(m) + s_mesh)
        for item in mesh_info:
            lines.append("\n" + item)
        lines.append("\n")

    s_other = " other object." if int_dif == 1 else " other objects."
    lines.append(divider + str(int_dif) + s_other)

    report = "".join(lines)
    rs.TextOut(report)


if __name__ == "__main__":
    qinfo()
