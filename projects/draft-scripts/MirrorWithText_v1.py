"""
MirrorWithText_v1.py

PROBABLE HOME: BRIX CNC PARTS (not confirmed -- owner flagged as likely,
2026-08-07; move it there once that's settled and drop this note).

v1. Minimized/hardcoded derivative of Pascal Golay's Mirror_ex.rvb port
(erikr2026/rhino-python-scripting, projects/pascal-golay-scripts/mirror_ex/
Mirror_ex.py) -- the original prompts for 1 of 3 mirror styles and 1 of 4-5
plane-definition methods; this hardcodes the only combination the owner
actually uses and drops every other prompt:
  - Mirror style: TextPositionOnly (text objects get moved to their
    mirrored position without being flipped; everything else is a true
    geometric mirror).
  - Mirror plane: TwoPt (two picked points + the current view's vertical).

Target engine: Rhino 8 Script Editor, CPython3 mode (ScriptEditor command,
F5). Do not run via RunPythonScript/legacy IronPython2 -- confirmed
2026-08-07 that the legacy engine's bundled rhinoscript library handles
PointAdd(point, vector) differently and raises
"object of type 'Vector3d' has no len()" for code that runs fine under
ScriptEditor's CPython3.

Removed vs. Mirror_ex.py: the Standard/PositionOnly style choice, the
ThreePt/Select/Cplane/NamedCPlane plane choices, the two rs.GetString
prompts and scriptcontext.sticky remembered-mode plumbing that selected
between them (nothing left to remember once there's only one path), and
the now-unused plane_from_curve/plane_from_selection/plane_3pt/
get_named_cplane/where_in_array helpers. mirror_position,
mirror_across_plane, bb_centroid, and vertical_plane_from_2pts are
unchanged from Mirror_ex.py.
"""

import rhinoscriptsyntax as rs


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


def mirror_with_text():
    obj_ids = rs.GetObjects("Select objects to mirror", 0, True, True, True)
    if not obj_ids:
        return

    plane = vertical_plane_from_2pts()
    if plane is None:
        return

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
    mirror_with_text()
