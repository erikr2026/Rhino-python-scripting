"""
Mirror_ex.py

TESTED AND WORKING (2026-08-07): owner ran this in real Rhino 8 via
ScriptEditor and confirmed it runs clean, after fixing an EvaluateSurface
tuple-vs-separate-args bug in plane_from_selection() (see git history).

Ported from Mirror_ex.rvb (Pascal Golay, McNeel - script version 2009-09-28).

Target engine: Rhino 8 Script Editor, CPython3 mode (run via the ScriptEditor
command: open this file, press F5). Not written for the legacy
RunPythonScript/IronPython2 engine.

What it does: select objects, choose a mirror STYLE (Standard = true
geometric mirror transform; PositionOnly = move a copy to the mirrored
bounding-box-centroid location without actually mirroring its geometry -
useful for text/dimensions/blocks you don't want flipped; TextPositionOnly
= like Standard but text objects only get position-mirrored while
everything else gets geometrically mirrored), then choose how to define the
mirror PLANE (two points + current view's vertical, three points, pick an
existing object, the active view's construction plane, or a named
construction plane).

Porting notes / deliberate changes from the original:
- Dropped `Rhino.AddStartupScript` / `Rhino.AddAlias`: this alias/startup
  registration mechanism belongs to the legacy RhinoScript engine, not a
  Script Editor Python 3 script run via F5.
- `Private OldMirStyle, oldPlaneStyle` (module-level state that persisted
  across repeated invocations of the loaded RhinoScript alias in the same
  Rhino session) is replaced with `scriptcontext.sticky`, the nearest
  equivalent that survives across separate F5 runs in the same session.
- Plane objects returned by rhinoscriptsyntax (e.g. `rs.ViewCPlane()`) are
  `Rhino.Geometry.Plane` objects with `.Origin`/`.XAxis`/`.YAxis`/`.ZAxis`
  properties - NOT old-style indexable arrays. The original's
  `Plane(0)`/`Plane(3)` (old RhinoScript plane-array convention: origin,
  x-axis, y-axis, z-axis/normal) are replaced with `.Origin`/`.ZAxis`
  (confirmed against the live rhinoscriptsyntax `XformMirror` example,
  which itself does `rs.XformMirror(plane.Origin, plane.Normal)`).
- `rs.CopyObject(object_id, translation=None)` takes a single translation
  VECTOR (confirmed live), not a (from_point, to_point) pair like the old
  RhinoScript `CopyObject`. `MirrorPosition` here builds the vector with
  `rs.VectorCreate(to_point, from_point)` before calling `rs.CopyObject`,
  reproducing the original's "copy from bounding-box centroid to its
  mirror image" behavior.
- No behavior bugs found in the original's logic; ported 1:1 otherwise,
  including the somewhat convoluted `Case 2` (TextPositionOnly) branch
  that splits the selection into text vs. non-text objects and applies a
  different mirror function to each.

Not run against a live Rhino in this session - validated only with
`python3 -m py_compile` / `ast.parse` (no syntax errors). Function names
and signatures were cross-checked against the live rhinoscriptsyntax
reference where noted above.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc


def where_in_array(item, arr, case_sensitive=False):
    """Returns the index of item in arr, or -1 if not found."""
    if case_sensitive:
        for i, val in enumerate(arr):
            if val == item:
                return i
    else:
        lowered_item = item.lower()
        for i, val in enumerate(arr):
            if val.lower() == lowered_item:
                return i
    return -1


def bb_centroid(obj_id):
    """Bounding-box centroid of a single object."""
    bbox = rs.BoundingBox(obj_id, rs.CurrentView())
    if not bbox:
        return None
    first = bbox[0]
    second = bbox[6]
    return (
        0.5 * (first.X + second.X),
        0.5 * (first.Y + second.Y),
        0.5 * (first.Z + second.Z),
    )


def mirror_position(obj_ids, plane):
    result = []
    for obj_id in obj_ids:
        loc = bb_centroid(obj_id)
        if loc is None:
            continue
        vec_targ = rs.VectorCreate(rs.PlaneClosestPoint(plane, loc), loc)
        targ = rs.PointAdd(loc, rs.VectorScale(vec_targ, 2.0))
        translation = rs.VectorCreate(targ, loc)
        new_id = rs.CopyObject(obj_id, translation)
        if new_id:
            result.append(new_id)
    return result


def mirror_across_plane(obj_ids, plane):
    xform = rs.XformMirror(plane.Origin, plane.ZAxis)
    return rs.TransformObjects(obj_ids, xform, True)


def vertical_plane_from_2pts():
    pts = rs.GetPoints(True, True, "First point for vertical plane", "Second point for vertical plane", 2)
    if not pts or len(pts) < 2:
        return None
    vec_x = rs.VectorCreate(pts[1], pts[0])
    vec_y = rs.ViewCPlane().ZAxis
    return rs.PlaneFromFrame(pts[0], vec_x, vec_y)


def plane_from_curve(curve_id):
    pts = rs.DivideCurve(curve_id, 32, False)
    if not pts:
        return None
    return rs.PlaneFitFromPoints(pts)


def plane_from_selection():
    obj_id = rs.GetObject("Select object to define plane", 4 + 8, False)
    if obj_id is None:
        return None

    if rs.IsSurface(obj_id):
        u_dom = rs.SurfaceDomain(obj_id, 0)
        v_dom = rs.SurfaceDomain(obj_id, 1)
        u_mid = u_dom[0] + 0.5 * (u_dom[1] - u_dom[0])
        v_mid = v_dom[0] + 0.5 * (v_dom[1] - v_dom[0])
        uv_mid = (u_mid, v_mid)
        pt = rs.EvaluateSurface(obj_id, u_mid, v_mid)
        return rs.PlaneFromNormal(pt, rs.SurfaceNormal(obj_id, uv_mid))
    else:
        plane = rs.CurvePlane(obj_id)
        if plane is not None:
            return plane
        return plane_from_curve(obj_id)


def plane_3pt():
    pts = rs.GetPoints(True, False, "First point for vertical plane", "Next point for plane", 3)
    if not pts or len(pts) != 3:
        return None
    vec_x = rs.VectorCreate(pts[1], pts[0])
    vec_y = rs.VectorCreate(pts[2], pts[0])
    return rs.PlaneFromFrame(pts[0], vec_x, vec_y)


def get_named_cplane():
    names = rs.NamedCPlanes()
    if not names:
        return None
    name = rs.ListBox(names, "Select mirror plane", "Named CPlanes")
    if name is None:
        return None
    return rs.NamedCPlane(name)


def mirror_ex():
    old_mir_style = sc.sticky.get("MirrorEx_OldMirStyle", "Standard")
    old_plane_style = sc.sticky.get("MirrorEx_OldPlaneStyle", "TwoPt")

    obj_ids = rs.GetObjects("Select objects to mirror", 0, True, True, True)
    if not obj_ids:
        return

    if rs.NamedCPlanes():
        plane_styles = ["TwoPt", "ThreePt", "Select", "Cplane", "NamedCPlane"]
    else:
        plane_styles = ["TwoPt", "ThreePt", "Select", "Cplane"]

    styles = ["Standard", "PositionOnly", "TextPositionOnly"]

    style_choice = rs.GetString("Choose mirror style", old_mir_style, styles)
    if style_choice is None:
        return
    style_index = where_in_array(style_choice, styles)
    if style_index == -1:
        return
    old_mir_style = styles[style_index]
    sc.sticky["MirrorEx_OldMirStyle"] = old_mir_style

    plane_style_choice = rs.GetString("Choose mirror plane", old_plane_style, plane_styles)
    if plane_style_choice is None:
        return
    plane_style_index = where_in_array(plane_style_choice, plane_styles)
    if plane_style_index == -1:
        return
    old_plane_style = plane_styles[plane_style_index]
    sc.sticky["MirrorEx_OldPlaneStyle"] = old_plane_style

    plane = None
    if plane_style_index == 0:
        plane = vertical_plane_from_2pts()
    elif plane_style_index == 1:
        plane = plane_3pt()
    elif plane_style_index == 2:
        plane = plane_from_selection()
    elif plane_style_index == 3:
        plane = rs.ViewCPlane()
    elif plane_style_index == 4:
        plane = get_named_cplane()

    if plane is None:
        return

    if style_index == 0:
        mirror_across_plane(obj_ids, plane)
    elif style_index == 1:
        mirror_position(obj_ids, plane)
    elif style_index == 2:
        text_objs = []
        misc_objs = []
        for obj_id in obj_ids:
            if rs.IsText(obj_id):
                text_objs.append(obj_id)
            else:
                misc_objs.append(obj_id)
        if text_objs:
            mirror_position(text_objs, plane)
        if misc_objs:
            mirror_across_plane(misc_objs, plane)


if __name__ == "__main__":
    mirror_ex()
