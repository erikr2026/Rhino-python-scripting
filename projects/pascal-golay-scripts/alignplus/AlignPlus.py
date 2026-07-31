"""
AlignPlus.py - Python 3 (CPython) port of AlignPlus.rvb (Pascal Golay, McNeel)

TARGET ENGINE: Rhino 8 Script Editor, CPython3 mode (ScriptEditor command,
F5). Not intended for the legacy `RunPythonScript` (IronPython 2) command.

Original behavior: align one or more selected objects (and/or whole groups)
to a target object's bounding-box edge/center, or to a picked point, along
one axis (Left/Right/Top/Bottom/HorizCenter/VertCenter) or both (Concentric),
all measured in the active construction plane.

Porting notes / deliberate simplifications:
  - `Rhino.AddAlias`/`Rhino.AddStartupScript` (registering "AlignToObject"/
    "AlignToPoint" as persistent command aliases) is a legacy VBScript
    RhinoScript mechanism with no Script Editor CPython3 equivalent; dropped.
    The two original entry points are kept as `align_to_object()` and
    `align_to_point()`, and the bottom of the file prompts once for which to
    run.
  - `OldAlign` (remembering the last alignment choice between calls) is
    ported using `scriptcontext.sticky`.
  - Legacy `Rhino.MoveObject`/`MoveObjects` took a 3-argument form
    (object(s), from_point, to_point). Modern rhinoscriptsyntax
    `MoveObject(object_id, translation)` / `MoveObjects(object_ids,
    translation)` take a single translation *vector* instead -- this is a
    real signature change, not a naming difference, and each call below
    computes `translation = to_point - from_point` via `rs.PointSubtract`
    before calling.
  - `Rhino.CullDuplicateStrings` has no rhinoscriptsyntax/RhinoCommon
    equivalent; replaced with a plain Python order-preserving dedupe
    (`dict.fromkeys`).
  - `IsUpperBound` / VBScript `UBound` (checking "is this a non-empty
    array") become plain Python truthiness / `len(x) > 0` checks throughout.
  - `Rhino.ObjectGroups`, `Rhino.ObjectsByGroup`, `Rhino.BoundingBox`,
    `Rhino.XformWorldToCplane`, `Rhino.XformCPlaneToWorld`, `Rhino.ViewCplane`
    map 1:1 to their rhinoscriptsyntax equivalents (confirmed against
    https://developer.rhino3d.com/api/RhinoScriptSyntax/, fetched live this
    session, not from trained memory).
  - The nested loop structure (a `Do ... Loop Until` letting the user repeat
    alignments in the same run) is preserved as a plain `while True` loop.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc


ALIGN_MODES = ["Left", "Right", "HorizCenter", "VertCenter", "Concentric", "Top", "Bottom"]


def average_points(pts):
    n = len(pts)
    x = sum(p[0] for p in pts) / n
    y = sum(p[1] for p in pts) / n
    z = sum(p[2] for p in pts) / n
    return (x, y, z)


def find_bb_point_plane(obj_ids, idx_pt):
    """idx_pt: 8 means centroid of corners 0 and 6; otherwise a bbox corner index.
    obj_ids may be a single object id or a list of ids."""
    view = rs.CurrentView()
    if not isinstance(obj_ids, (list, tuple)):
        obj_ids = [obj_ids]
    bbox = rs.BoundingBox(obj_ids, view)
    if bbox is None:
        return None
    if idx_pt == 8:
        return average_points((bbox[0], bbox[6]))
    return bbox[idx_pt]


def get_coordinate(align_type):
    a = align_type.upper()
    if a in ("LEFT", "RIGHT", "VERTCENTER"):
        return ("X", a)
    if a in ("TOP", "BOTTOM", "HORIZCENTER"):
        return ("Y", a)
    if a == "CONCENTRIC":
        return ("XY", a)
    return None


def get_align_point(obj_ids, coordinate):
    """Returns one alignment reference point per object (or per group's
    combined bbox, when called with a group's member-object list)."""
    tag = coordinate[1]
    if tag in ("HORIZCENTER", "VERTCENTER", "CONCENTRIC"):
        idx = 8
    elif tag in ("LEFT", "TOP"):
        idx = 7
    else:  # RIGHT, BOTTOM
        idx = 1
    return [find_bb_point_plane(obj_id, idx) for obj_id in obj_ids]


def get_align_point_grp(groups, coordinate):
    tag = coordinate[1]
    if tag in ("HORIZCENTER", "VERTCENTER", "CONCENTRIC"):
        idx = 8
    elif tag in ("LEFT", "TOP"):
        idx = 7
    else:
        idx = 1
    result = []
    for grp in groups:
        members = rs.ObjectsByGroup(grp)
        result.append(find_bb_point_plane(members, idx))
    return result


def extract_grouped(obj_ids):
    """Split picked objects into ungrouped objects and a de-duplicated list
    of group names those objects belong to."""
    ungrouped = []
    groups = []
    for obj_id in obj_ids:
        obj_groups = rs.ObjectGroups(obj_id)
        if obj_groups:
            groups.extend(obj_groups)
        else:
            ungrouped.append(obj_id)
    groups = list(dict.fromkeys(groups))  # order-preserving dedupe
    return ungrouped, groups


def world_to_cplane_pts(pts, plane):
    return [rs.XformWorldToCPlane(p, plane) for p in pts]


def cplane_to_world_pts(pts):
    plane = rs.ViewCPlane()
    return [rs.XformCPlaneToWorld(p, plane) for p in pts]


def align_plus(align_kind):
    """align_kind: 'Obj' or 'Pt'."""
    obj_ids = rs.GetObjects("Select objects to align", preselect=True, select=True)
    if not obj_ids:
        return

    ungrouped, groups = extract_grouped(obj_ids)

    old_align = sc.sticky.get("AlignPlus_mode", "VertCenter")

    while True:
        align_type = rs.GetString("Choose alignment", old_align, ALIGN_MODES)
        if not align_type:
            return
        old_align = align_type
        sc.sticky["AlignPlus_mode"] = align_type

        coordinate = get_coordinate(align_type)
        if coordinate is None:
            return
        coord_axis = coordinate[0]

        if align_kind == "Obj":
            target_id = rs.GetObject("Select target object", preselect=True)
            if target_id is None:
                return
            target_pt = get_align_point([target_id], coordinate)[0]
        else:
            target_pt = rs.GetPoint("Select target point")

        if target_pt is None:
            return

        rs.EnableRedraw(False)
        plane = rs.ViewCPlane()
        target_plane_pt = rs.XformWorldToCPlane(target_pt, plane)

        if ungrouped:
            base_pts = get_align_point(ungrouped, coordinate)
            if base_pts:
                base_plane_pts = world_to_cplane_pts(base_pts, plane)
                new_target_plane_pts = []
                for i in range(len(ungrouped)):
                    b = base_plane_pts[i]
                    if coord_axis == "X":
                        new_target_plane_pts.append((target_plane_pt[0], b[1], b[2]))
                    elif coord_axis == "Y":
                        new_target_plane_pts.append((b[0], target_plane_pt[1], b[2]))
                    elif coord_axis == "XY":
                        new_target_plane_pts.append((target_plane_pt[0], target_plane_pt[1], b[2]))
                final_pts = cplane_to_world_pts(new_target_plane_pts)

                for i, obj_id in enumerate(ungrouped):
                    translation = rs.PointSubtract(final_pts[i], base_pts[i])
                    rs.MoveObject(obj_id, translation)

        if groups:
            base_pts = get_align_point_grp(groups, coordinate)
            base_plane_pts = world_to_cplane_pts(base_pts, plane)
            new_target_plane_pts = []
            grouped_members = []
            for i, grp in enumerate(groups):
                grouped_members.append(rs.ObjectsByGroup(grp))
                b = base_plane_pts[i]
                if coord_axis == "X":
                    new_target_plane_pts.append((target_plane_pt[0], b[1], b[2]))
                elif coord_axis == "Y":
                    new_target_plane_pts.append((b[0], target_plane_pt[1], b[2]))
                elif coord_axis == "XY":
                    new_target_plane_pts.append((target_plane_pt[0], target_plane_pt[1], b[2]))
            final_pts = cplane_to_world_pts(new_target_plane_pts)

            for i, grp in enumerate(groups):
                translation = rs.PointSubtract(final_pts[i], base_pts[i])
                rs.MoveObjects(grouped_members[i], translation)

        rs.EnableRedraw(True)


def align_to_object():
    align_plus("Obj")


def align_to_point():
    align_plus("Pt")


def main():
    choice = rs.GetString("Align to an Object or a Point?", "Object", ["Object", "Point"])
    if choice is None:
        return
    if choice.lower() == "point":
        align_to_point()
    else:
        align_to_object()


if __name__ == "__main__":
    main()
