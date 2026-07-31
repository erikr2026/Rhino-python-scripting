"""
Distribute.py

Port of Distribute.rvb (Pascal Golay, McNeel — legacy RhinoScript/
VBScript, version Saturday, September 03, 2011) to Python 3 for Rhino 8's
Script Editor (CPython3 mode). Run via ScriptEditor -> open this file ->
F5. NOT for RunPythonScript (that invokes the IronPython 2 engine).

What it does (unchanged from the original): select 2+ objects (or
groups), pick a distribution direction (the current CPlane's X or Y axis,
or a user-defined 2-point direction), pick a spacing style (equal
bounding-box-center spacing, equal gap, or an explicit numeric center
spacing / gap), and move all but the two end objects/groups so they are
evenly spaced along that direction. Existing groups are respected and
kept as move-together units; ungrouped objects are temporarily grouped
one-per-object so each can be positioned independently, then that
scratch grouping is cleaned up (deleted) before the script finishes.

Porting notes / deliberate simplifications (verified against the
rhinoscriptsyntax source, Scripts/rhinoscript/*.py, rhino-8.x branch,
2026-07-31):

- rs.MoveObjects(object_ids, translation) takes a single translation
  VECTOR, unlike the legacy Rhino.MoveObjects(objects, fromPoint,
  toPoint) two-point form used throughout the original. Every call below
  computes translation = to_point - from_point explicitly.
- rs.Plane objects (from rs.ViewCPlane, rs.WorldXYPlane, etc.) are real
  Rhino.Geometry.Plane objects with .Origin/.XAxis/.YAxis/.ZAxis
  properties (Origin is settable) — NOT the 4-element indexable arrays
  VBScript's RhinoScript exposed planes as. All `Plane(0)`/`Plane(1)`/
  `Plane(3)`-style indexing in the original is translated to
  `.Origin`/`.XAxis`/`.ZAxis` etc. accordingly.
- Confirmed rhinoscriptsyntax has NO CullDuplicateStrings function (the
  original's `Rhino.CullDuplicateStrings` was a legacy-COM-only helper).
  Reimplemented locally as `_cull_duplicate_strings`, an order-preserving
  dedupe.
- The original's transformation function is exposed in rhinoscriptsyntax
  as `XformRotation1(initial_plane, final_plane)` (plane-to-plane), not a
  bare `XformRotation` — rhinoscriptsyntax splits the legacy RhinoScript
  `Rhino.XformRotation` overloads into four separately named functions
  (XformRotation1..4) since Python doesn't support VBScript-style
  argument-count overloading. Confirmed against
  Scripts/rhinoscript/transformation.py.
- In `Distribute`, right after `OrderGroups` returns, the original does:
  `j = Orderly(0): k = Orderly(1): If IsArray(j) Then If IsArray(k) Then
  aOrderedGrp = JoinArrays(j, k) ...`. `Orderly(0)` (the ordered group
  name list) and `Orderly(1)` (the ordered bbox-center *points* list) are
  both always arrays in every code path of `OrderGroups`, so this always
  falls into `JoinArrays(j, k)` — concatenating a list of group-name
  strings with a list of points into one mixed-type array. Every later
  use of `aOrderedGrp(i)` only ever indexes `i` in `[0, Bound]`, i.e.
  strictly within the length of `j`, so the appended `k` values are never
  read; the join has no observable effect on behavior. It is also worth
  noting the `Else If isArr(k)` branch (lowercase, no final "ay") calls a
  function name (`isArr`) that does not exist anywhere in this script —
  a latent bug that never fires in practice because `j` is always an
  array, so that branch is unreachable. This port skips the pointless
  join and the dead/buggy branch entirely and just uses
  `a_ordered_grp = orderly[0]` directly, which is behaviorally identical.
- `CullEmptyGroups`, a helper function defined in the original, is never
  called anywhere in the original script (dead code) and is not ported.
- `DrawPlaneFrame`, a debug-only helper invoked exclusively from
  commented-out `'TEST` lines in the original, is not ported — it has no
  effect on the shipped behavior.
- Point/vector arithmetic below (`+`, `-`, `*` on Point3d/Vector3d) relies
  on RhinoCommon's operator overloads being exposed through pythonnet in
  Rhino 8's CPython3 engine. This is very widely used and expected to
  work, but — unlike the function-signature lookups above — operator
  overload behavior was not independently re-verified against a live
  Rhino session in this port; flag this if arithmetic on these types
  raises a TypeError when first run.
"""

import math

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino


def q_distance(pt_a, pt_b):
    return math.sqrt(
        (pt_a[0] - pt_b[0]) ** 2 + (pt_a[1] - pt_b[1]) ** 2 + (pt_a[2] - pt_b[2]) ** 2
    )


def where_in_array(item, arr, case_insensitive):
    for i, entry in enumerate(arr):
        if case_insensitive:
            if entry.lower() == item.lower():
                return i
        else:
            if entry == item:
                return i
    return -1


def average_points(pts):
    x = sum(p[0] for p in pts) / len(pts)
    y = sum(p[1] for p in pts) / len(pts)
    z = sum(p[2] for p in pts) / len(pts)
    return Rhino.Geometry.Point3d(x, y, z)


def cull_duplicate_strings(names):
    seen = set()
    result = []
    for name in names:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def get_plane_from_direction():
    pts = rs.GetPoints(True, False, "First direction point.", "Second direction point.", 2)
    if not pts:
        return None
    vec_dir = rs.VectorCreate(pts[1], pts[0])
    # PlaneFromNormal picks an arbitrary x-axis perpendicular to vec_dir;
    # re-use that x-axis as the y-axis of the final frame so the result
    # is an orthonormal plane with vec_dir as its x-axis.
    temp_plane = rs.PlaneFromNormal(pts[0], vec_dir)
    return rs.PlaneFromFrame(
        pts[0], rs.VectorUnitize(vec_dir), rs.VectorUnitize(temp_plane.XAxis)
    )


def sort_objects_to_groups(objs):
    """Returns (new_grps, temp_grps, all_one):
    all_one == 0: all objects distributed across multiple pre-existing groups
    all_one == 1: all objects effectively in one group (existing or ad-hoc)
    all_one == 2: some grouped, some ungrouped
    """
    existing_group_names = rs.GroupNames()
    temp_grps = []

    if not existing_group_names:
        grps = []
        for obj in objs:
            g = rs.AddGroup()
            temp_grps.append(g)
            grps.append(g)
            rs.AddObjectToGroup(obj, g)
        return None, temp_grps, 1

    grps = []
    n = 0
    i = 0
    for obj in objs:
        obj_grps = rs.ObjectGroups(obj)
        if obj_grps:
            grps.append(obj_grps[-1])
            n += 1
        else:
            g = rs.AddGroup()
            temp_grps.append(g)
            rs.AddObjectToGroup(obj, g)
            i += 1

    if n > 0:
        all_one = 0
        if i > 0:
            all_one = 2
        new_grps = cull_duplicate_strings(grps)
        if len(new_grps) == 1 and i == 0:
            all_one = 1
            temp_grps = []
            for obj in objs:
                g = rs.AddGroup()
                rs.AddObjectToGroup(obj, g)
                temp_grps.append(g)
        return new_grps, temp_grps, all_one
    else:
        return None, temp_grps, 1


def order_groups(grps, plane):
    bound = len(grps) - 1
    test_line = (plane.Origin, plane.Origin + plane.XAxis)

    a_obj = list(rs.ObjectsByGroup(grps[0]) or [])
    for i in range(1, len(grps)):
        temp_obj = rs.ObjectsByGroup(grps[i])
        if temp_obj:
            a_obj = a_obj + list(temp_obj)

    a_bb = rs.BoundingBox(a_obj, plane)
    plane.Origin = average_points([a_bb[0], a_bb[6]])

    xform = rs.XformRotation1(plane, rs.WorldXYPlane())
    rev_xform = rs.XformRotation1(rs.WorldXYPlane(), plane)

    a_cen = [None] * len(grps)
    for i in range(len(grps)):
        temp_box = rs.BoundingBox(rs.ObjectsByGroup(grps[i]), plane)
        center = average_points([temp_box[0], temp_box[6]])
        a_cen[i] = rs.PointTransform(rs.LineClosestPoint(test_line, center), xform)

    a_ordered_cen = rs.SortPoints(a_cen)
    test_arr = rs.CullDuplicatePoints(a_ordered_cen)

    if not test_arr or len(test_arr) <= 1:
        # Unable to determine spacing order (all centers coincide, or
        # only one distinguishable location).
        return grps, a_ordered_cen

    ordered_grp = [None] * len(grps)
    n = 0
    for i in range(len(test_arr)):
        for j in range(len(grps)):
            if rs.PointCompare(test_arr[i], a_cen[j]):
                ordered_grp[n] = grps[j]
                n += 1

    for i in range(len(grps)):
        a_ordered_cen[i] = rs.PointTransform(a_ordered_cen[i], rev_xform)

    return ordered_grp, a_ordered_cen


def distribute():
    objs = rs.GetObjects("Select objects to distribute.", preselect=True)
    if not objs:
        return

    new_grps, temp_grps, all_one = sort_objects_to_groups(objs)

    if all_one == 1:
        all_grps = temp_grps
    elif all_one == 2:
        all_grps = new_grps + temp_grps
    else:
        all_grps = new_grps

    if not all_grps or len(all_grps) < 2:
        rs.MessageBox("At least 2 objects must be selected.")
        return

    bound = len(all_grps) - 1

    a_dir = ("X", "Y", "User")
    old_ddir = sc.sticky.get("Distribute_OldDDir", "X")
    s_dir = rs.GetString("Direction", old_ddir, a_dir)
    if s_dir is None:
        return

    int_dir = where_in_array(s_dir, a_dir, True)
    if int_dir == -1:
        return
    sc.sticky["Distribute_OldDDir"] = a_dir[int_dir]

    temp_plane = rs.ViewCPlane()

    if int_dir == 0:
        plane = temp_plane
    elif int_dir == 1:
        plane = rs.RotatePlane(temp_plane, 90, temp_plane.ZAxis)
    else:
        plane = get_plane_from_direction()
        if not plane:
            return

    a_style = ("Centers", "Gap", "SetCenters", "SetGap")
    old_gap_style = sc.sticky.get("Distribute_OldGapStyle", "Centers")
    s_style = rs.GetString("Set spacing style.", old_gap_style, a_style)
    if s_style is None:
        return

    int_style = where_in_array(s_style, a_style, True)
    if int_style == -1:
        return
    sc.sticky["Distribute_OldGapStyle"] = a_style[int_style]

    orderly = order_groups(all_grps, plane)

    if orderly is None or len(all_grps) < 3:
        if int_style < 2:
            rs.MessageBox(
                "Unable to determine spacing.\n"
                "At least 3 objects must be selected for automatic spacing."
            )
            for g in temp_grps:
                rs.DeleteGroup(g)
            return

    a_ordered_grp = orderly[0]
    a_ordered_cen = orderly[1]

    test_line = (plane.Origin, plane.Origin + plane.XAxis)

    old_c_space = sc.sticky.get("Distribute_OldCSpace", 1.0)
    old_gap = sc.sticky.get("Distribute_OldGap", 1.0)

    a_cen = None
    space = 0.0

    if int_style == 0:  # Centers
        a_cen = a_ordered_cen
        space = q_distance(a_cen[0], a_cen[bound]) / bound
    elif int_style == 2:  # SetCenters
        a_cen = a_ordered_cen
        space = rs.GetReal("Set center spacing.", old_c_space)
        if space is None:
            return
        sc.sticky["Distribute_OldCSpace"] = space
    elif int_style == 3:  # SetGap
        space = rs.GetReal("Set gap size.", old_gap)
        if space is None:
            return
        sc.sticky["Distribute_OldGap"] = space
    else:  # Gap (auto)
        ttl_length = 0.0
        for i in range(1, bound):
            temp = rs.BoundingBox(rs.ObjectsByGroup(a_ordered_grp[i]), plane)
            ttl_length += q_distance(temp[0], temp[1])

        pt1 = rs.LineClosestPoint(
            test_line, rs.BoundingBox(rs.ObjectsByGroup(a_ordered_grp[0]), plane)[1]
        )
        pt2 = rs.LineClosestPoint(
            test_line, rs.BoundingBox(rs.ObjectsByGroup(a_ordered_grp[bound]), plane)[0]
        )
        span = q_distance(pt1, pt2)
        space = (span - ttl_length) / bound

    rs.EnableRedraw(False)

    if int_style == 0:
        bound = bound - 1

    if int_style in (0, 2):
        for i in range(1, bound + 1):
            target = a_cen[0] + plane.XAxis * (i * space)
            rs.MoveObjects(rs.ObjectsByGroup(a_ordered_grp[i]), target - a_cen[i])
    else:
        vec = plane.XAxis * space
        if int_style == 1:
            bound = bound - 1
        for i in range(1, bound + 1):
            grp = a_ordered_grp[i]
            min_pt = rs.LineClosestPoint(
                test_line, rs.BoundingBox(rs.ObjectsByGroup(a_ordered_grp[i]), plane)[0]
            )
            prev_box = rs.BoundingBox(rs.ObjectsByGroup(a_ordered_grp[i - 1]), plane)
            base_pt = rs.LineClosestPoint(test_line, prev_box[1])
            target = base_pt + vec
            rs.MoveObjects(rs.ObjectsByGroup(grp), target - min_pt)

    for g in temp_grps:
        rs.DeleteGroup(g)

    rs.EnableRedraw(True)


if __name__ == "__main__":
    distribute()
