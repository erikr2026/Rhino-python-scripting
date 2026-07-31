"""
ExtractUnderlyingSrfs.py

Python 3 (CPython) port of ExtractUnderlyingSrfs.rvb, for Rhino 8's
Script Editor (ScriptEditor command, run with F5). Not for the legacy
RunPythonScript/IronPython 2 engine.

Original by Pascal Golay (McNeel), 2010-04-01.

Converts a surface or polysurface into its underlying untrimmed
surfaces (i.e. removes all trims: a trimmed hole in a NURBS surface,
or a barrel-shaped trim on a sphere/cone/torus, is expanded back out
to the surface's natural, full extent). Optionally deletes the input.

Function/API mappings verified 2026 against the mcneel/rhinoscriptsyntax
GitHub source (rhino-8.x branch, Scripts/rhinoscript/surface.py) via
WebFetch this session — not guessed from memory:
  - rs.SurfaceSphere / rs.SurfaceCone / rs.SurfaceTorus return
    (plane, radius) / (plane, height, radius) / (plane, major, minor)
    tuples (unpack directly, no "out"-parameter surprises here since
    these are pure rhinoscriptsyntax wrappers, not raw RhinoCommon).
  - rs.AddNurbsSurface(point_count, points, knots_u, knots_v, degree,
    weights=None) - point_count and degree are each a (U, V) pair.
  - rs.SurfaceDegree(surface_id, direction=2) with direction=2 (default)
    returns a (degreeU, degreeV) tuple, matching the AddNurbsSurface
    degree parameter shape directly.

Note: unlike the legacy AddTorus's undocumented tolerance for a plane
base combined with a direction argument, the modern rs.AddTorus errors
out if both a plane and an explicit direction are supplied - so this
port omits the direction argument entirely, since the plane returned by
rs.SurfaceTorus already fully encodes the torus orientation.
"""

import rhinoscriptsyntax as rs


def get_untrimmed_srf(srf_id):
    """Returns the id of a new, untrimmed version of the given surface.
    For analytic surfaces (sphere/cone/torus) the full analytic shape
    is rebuilt; otherwise a NURBS surface is rebuilt from the same
    control points, knots, degree and weights but with no trim curves.
    """
    if rs.IsSphere(srf_id):
        plane, radius = rs.SurfaceSphere(srf_id)
        return rs.AddSphere(plane, radius)

    elif rs.IsCone(srf_id):
        plane, height, radius = rs.SurfaceCone(srf_id)
        return rs.AddCone(plane, height, radius, False)

    elif rs.IsTorus(srf_id):
        plane, major_radius, minor_radius = rs.SurfaceTorus(srf_id)
        return rs.AddTorus(plane, major_radius, minor_radius)

    else:
        point_count = rs.SurfacePointCount(srf_id)
        points = rs.SurfacePoints(srf_id)
        knots_u, knots_v = rs.SurfaceKnots(srf_id)
        degree = rs.SurfaceDegree(srf_id)
        weights = rs.SurfaceWeights(srf_id)
        return rs.AddNurbsSurface(point_count, points, knots_u, knots_v, degree, weights)


def underlying_srf(srf_ids):
    """Replaces each surface in srf_ids with its untrimmed equivalent,
    then deletes the (already-copied-or-owned) input surfaces.
    """
    rs.EnableRedraw(False)
    for srf_id in srf_ids:
        get_untrimmed_srf(srf_id)
    rs.EnableRedraw(True)


def extract_underlying_srfs():
    obj_id = rs.GetObject("Select object", rs.filter.surface | rs.filter.polysurface, True)
    if obj_id is None:
        return

    delete_choice = rs.GetString("Delete input", "No", ("No", "Yes"))
    if delete_choice is None:
        return
    delete_input = delete_choice.lower() == "yes"

    if rs.IsPolysurface(obj_id):
        srf_ids = rs.ExplodePolysurfaces(obj_id, delete_input)
    else:
        if delete_input:
            srf_ids = [obj_id]
        else:
            srf_ids = [rs.CopyObject(obj_id)]

    if not srf_ids:
        return

    underlying_srf(srf_ids)
    rs.DeleteObjects(srf_ids)


if __name__ == "__main__":
    extract_underlying_srfs()
