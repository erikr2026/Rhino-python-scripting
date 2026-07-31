"""
HighPt.py

Python 3 (CPython, PythonNet bridge) port of HighPt.rvb, for Rhino 8's
Script Editor (run via the ScriptEditor command, F5). Do NOT run this
through the legacy RunPythonScript command -- that invokes the IronPython 2
engine.

Original behavior (Pascal Golay, legacy RhinoScript/VBScript, 2008):
  - Two entry points existed as command aliases: HighPt and LowPt, both
    implemented by a shared MaxPt(dir) routine (dir=0 for high, dir=1 for
    low).
  - Prompts for a surface/polysurface and a starting point on it.
  - Builds a vertical search plane near one corner of the object's bounding
    box (aligned to the current view's construction plane, offset along
    the box's diagonal), then repeatedly walks a point back and forth
    between "closest point on that plane" and "closest point on the brep"
    for a fixed 512 iterations. Because the plane sits near one end of the
    bounding-box diagonal, this ping-pong process tends to walk the point
    toward the local high (or low) point on the surface nearest the search
    direction, rather than actually finding the plane/brep intersection.
  - After the fixed iteration count, drops a Point object at the final
    location -- this is the reported high/low point.

Porting notes:
  - Rhino.AddStartUpScript / Rhino.AddAlias have no equivalent for a
    CPython3 Script Editor file; this port defines high_pt() and low_pt()
    and calls one at the bottom of the file when run directly.
  - Function-name mappings verified against the mcneel/rhinoscriptsyntax
    GitHub source (rhino-8.x branch): GetObject, BoundingBox,
    GetPointOnSurface, VectorCreate, PointAdd, VectorScale, ViewCPlane,
    CurrentView, PlaneClosestPoint, BrepClosestPoint, EnableRedraw,
    AddPoint all exist with the signatures used below.
  - rs.BrepClosestPoint(object_id, point) returns a tuple
    (point, (u, v), (type, index), normal) -- the closest point itself is
    result[0] -- same as in FindClearance2.py; rs.PlaneClosestPoint(plane,
    point) returns just a Point3d directly (return_point defaults True),
    which is different from BrepClosestPoint's tuple return and matches how
    the original VBScript used `Temp = Rhino.PlaneClosestPoint(...)`
    directly as a point (no `Temp(0)` indexing), unlike its brep
    counterpart.
  - RhinoCommon's Plane.Origin has a setter (`Gets or sets the origin
    point of this plane`, confirmed via developer.rhino3d.com's live
    RhinoCommon API data 2026), so `Plane(0) = PlaneOrigin` in the original
    (VBScript treated planes as 4-element arrays) is ported as
    `plane.Origin = plane_origin` rather than item-index assignment, which
    the RhinoCommon Plane struct/Python binding does not support.
  - BUG PRESERVED FROM ORIGINAL (flagged, not fixed): the closing
    `Rhino.EnableRedraw` call at the end of MaxPt is called with NO
    argument, unlike every other EnableRedraw call in this script (and in
    the other 4 ported scripts) which explicitly pass True/False. Old
    RhinoScript's Rhino.EnableRedraw() with no argument does default to
    enabling redraw, and rhinoscriptsyntax's EnableRedraw(enable=True) has
    the same default, so behavior is preserved either way -- but the
    inconsistency (present nowhere else in any of these five scripts) looks
    like an oversight rather than a deliberate omission. Written here as
    `rs.EnableRedraw(True)` for clarity, which is behaviorally identical.
  - The fixed 512-iteration ping-pong loop with no convergence check is
    preserved exactly as in the original (same design as FindClearance2.rvb's
    PingPong) -- there is no early exit once the point stops moving.

Limitation: no live Rhino available in this environment to actually run the
script -- validated only with `python3 -m py_compile` (syntax parses) and a
manual read-through against the rhinoscriptsyntax source. Test in Script
Editor before relying on it.
"""

import rhinoscriptsyntax as rs

SURFACE_AND_POLYSURFACE_FILTER = 8 + 16  # rs.filter.surface + rs.filter.polysurface
MAX_ITERATIONS = 512


def max_pt(direction):
    """direction=0 walks toward the high point, direction=1 toward the low
    point, relative to the current view's construction plane."""
    obj = rs.GetObject("Select a surface or polysurface to test", SURFACE_AND_POLYSURFACE_FILTER, True)
    if obj is None:
        return

    current_view = rs.CurrentView()
    bbox = rs.BoundingBox(obj, current_view)
    if not bbox:
        rs.Print("Could not compute a bounding box for the selected object.")
        return

    pt = rs.GetPointOnSurface(obj)
    if not pt:
        return

    if direction == 0:
        base_pt = bbox[4]
        vec_dir = rs.VectorCreate(bbox[4], bbox[0])
    else:
        vec_dir = rs.VectorCreate(bbox[0], bbox[4])
        base_pt = bbox[0]

    plane_origin = rs.PointAdd(base_pt, rs.VectorScale(vec_dir, 0.05))
    plane = rs.ViewCPlane(current_view)
    plane.Origin = plane_origin

    rs.EnableRedraw(False)

    i = 0
    while True:
        temp = rs.PlaneClosestPoint(plane, pt)
        closest = rs.BrepClosestPoint(obj, temp)
        if not closest:
            rs.EnableRedraw(True)
            rs.Print("Lost track of the surface during the search -- aborting.")
            return
        pt = closest[0]
        i += 1

        if i == MAX_ITERATIONS:
            rs.AddPoint(pt)
            break

    rs.EnableRedraw(True)


def high_pt():
    max_pt(0)


def low_pt():
    max_pt(1)


if __name__ == "__main__":
    # Original had two aliases (HighPt / LowPt) sharing this logic.
    # Default to the high-point behavior; call low_pt() instead (or edit
    # this line) for the low-point variant.
    high_pt()
