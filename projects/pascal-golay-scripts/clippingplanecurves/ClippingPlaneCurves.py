"""
ClippingPlaneCurves.py - Python 3 (CPython) port of ClippingPlaneCurves.rvb
(Pascal Golay, McNeel)

TARGET ENGINE: Rhino 8 Script Editor, CPython3 mode (ScriptEditor command,
F5). Not intended for the legacy `RunPythonScript` (IronPython 2) command.

Original behavior: pick a clipping plane object, build a temporary planar
surface sized to the bounding box of all normal (visible/selectable) scene
objects projected onto the clipping plane, select all those objects, and run
Rhino's `IntersectTwoSets` command against the temporary surface -- producing
the curves where the model crosses the clipping plane. The temporary surface
is deleted afterward.

Porting notes / deliberate simplifications:
  - `Rhino.AddAlias`/`Rhino.AddStartupScript` (registering a persistent
    "ClippingPlaneCurves" command alias) is a legacy VBScript RhinoScript
    mechanism with no Script Editor CPython3 equivalent; dropped. Run this
    file directly with F5, or point a Rhino alias/button at it manually.
  - `Rhino.ClippingPlaneDefinition` has no rhinoscriptsyntax equivalent --
    there is no `rs.ClippingPlaneDefinition`. Rebuilt via RhinoCommon:
    `Rhino.DocObjects.ClippingPlaneObject.ClippingPlaneGeometry` (a
    `Rhino.Geometry.ClippingPlaneSurface`, which derives from `PlaneSurface`)
    exposes a `.Plane` property -- confirmed against the live RhinoCommon
    API index (developer.rhino3d.com/api/rhinocommon/data/api_info.json,
    fetched this session) since the RhinoCommon HTML doc pages themselves
    are a JS single-page app that a plain fetch can't render.
  - `536870912` (the `GetObject` filter value for "clipping plane") is
    carried over unchanged from the original -- confirmed against
    rhinoscriptsyntax's documented `ObjectType` value table (same value,
    same meaning) this session.
  - `_IntersectTwoSets` has no rhinoscriptsyntax wrapper (it operates on two
    interactive-command selection sets, which is different from the
    curve/surface intersection helpers rhinoscriptsyntax exposes); kept as
    an `rs.Command(...)` macro call, exactly as the original did.
  - `Rhino.BoundingBox`, `Rhino.NormalObjects`, `Rhino.PlaneClosestPoint`,
    `Rhino.AddSrfPt`, `Rhino.SelectObjects`, `Rhino.DeleteObject` map 1:1 to
    their rhinoscriptsyntax equivalents (confirmed against
    https://developer.rhino3d.com/api/RhinoScriptSyntax/, fetched live this
    session).
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc
import System


def _get_clipping_plane_plane(obj_id):
    """Returns the Rhino.Geometry.Plane of a clipping plane object, or None."""
    guid = obj_id if isinstance(obj_id, System.Guid) else System.Guid(str(obj_id))
    rhobj = sc.doc.Objects.Find(guid)
    if rhobj is None:
        return None
    cp_geo = getattr(rhobj, "ClippingPlaneGeometry", None)
    if cp_geo is None:
        return None
    return cp_geo.Plane


def clipping_plane_curves():
    plane_id = rs.GetObject("Select clipping plane.", 536870912, True)
    if plane_id is None:
        return

    plane = _get_clipping_plane_plane(plane_id)
    if plane is None:
        print("Could not read clipping plane geometry from selected object.")
        return

    normal_objs = rs.NormalObjects()
    if not normal_objs:
        print("No normal objects in the document to intersect against.")
        return

    bbox = rs.BoundingBox(normal_objs, plane)
    if bbox is None:
        return

    rs.EnableRedraw(False)
    rs.SelectObjects(normal_objs)

    corner_pts = [
        rs.PlaneClosestPoint(plane, bbox[0]),
        rs.PlaneClosestPoint(plane, bbox[1]),
        rs.PlaneClosestPoint(plane, bbox[2]),
        rs.PlaneClosestPoint(plane, bbox[3]),
    ]
    srf_id = rs.AddSrfPt(corner_pts)

    rs.Command("_IntersectTwoSets _SelID {} _Enter".format(srf_id), False)
    rs.DeleteObject(srf_id)
    rs.EnableRedraw(True)


if __name__ == "__main__":
    clipping_plane_curves()
