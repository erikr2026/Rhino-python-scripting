"""
DimensionOffset.py

Port of DimensionOffset.rvb (Pascal Golay, McNeel — legacy RhinoScript/
VBScript, version Wednesday, December 12, 2012) to Python 3 for Rhino 8's
Script Editor (CPython3 mode). Run via ScriptEditor -> open this file ->
F5. NOT for RunPythonScript (that invokes the IronPython 2 engine).

What it does (unchanged from the original): select linear/aligned
dimensions, enter a text-offset distance, and for each selected dimension
move its text-definition grip (whichever end grip pair is closer together
— the text/witness-line-anchor pair) outward along the dimension's own
direction by that distance. Non-linear/aligned dimension types in the
selection are silently skipped, matching the original.

Porting notes:
- The "W" prefix in the original's `_Move` command string
  (`"_Move W" & Pt2Str(dirpt) & "W" & Pt2Str(targ)"`) forces the typed
  coordinates to be read as WORLD coordinates rather than active
  construction-plane coordinates — the standard Rhino command-line
  convention (typed "x,y,z" is CPlane-relative unless prefixed with w/W).
  Reproduced here with a lowercase `w` prefix on both point strings for
  the same reason.
- Sticky default distance (OldDist in the original) reproduced via
  `scriptcontext.sticky`, matching the same run-to-run persistence the
  VBScript module-level Private variable had within one host session.
- rs.IsLinearDimension / rs.IsAlignedDimension / rs.EnableObjectGrips /
  rs.ObjectGripLocation / rs.SelectObjectGrip all confirmed present in
  rhinoscriptsyntax (dimension.py and grips.py, rhino-8.x branch) with
  signatures matching this script's usage.
- Grip indices 0-3 on a linear/aligned dimension are its four definition
  points (the two witness-line origins and the two dimension-line end
  points) — this matches the original's direct indexing scheme
  unchanged; RhinoCommon does not expose a more semantic accessor for
  these through rhinoscriptsyntax, so the original's positional
  assumption is kept as-is.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc


def dimension_offset():
    dims = rs.GetObjects(
        "Select dimensions to modify.",
        rs.filter.annotation,
        group=True,
        preselect=True,
    )
    if not dims:
        return

    old_dist = sc.sticky.get("DimensionOffset_OldDist", 1.0)
    dist = rs.GetReal("Set Dim text distance", old_dist)
    if dist is None:
        return
    sc.sticky["DimensionOffset_OldDist"] = dist

    rs.EnableRedraw(False)
    for dim in dims:
        if rs.IsLinearDimension(dim) or rs.IsAlignedDimension(dim):
            rs.EnableObjectGrips(dim, True)

            p = [rs.ObjectGripLocation(dim, i) for i in range(4)]

            d1 = rs.Distance(p[0], p[1])
            d2 = rs.Distance(p[2], p[3])

            test_pt = p[0]
            dir_pt = p[1]
            idx = 1
            if d1 > d2:
                test_pt = p[2]
                dir_pt = p[3]
                idx = 3

            vec_x = rs.VectorUnitize(rs.VectorCreate(dir_pt, test_pt))
            targ = rs.PointAdd(test_pt, rs.VectorScale(vec_x, dist))

            rs.UnselectAllObjects()
            rs.SelectObjectGrip(dim, idx)
            rs.Command(
                "_Move w{0},{1},{2} w{3},{4},{5}".format(
                    dir_pt[0], dir_pt[1], dir_pt[2],
                    targ[0], targ[1], targ[2],
                ),
                False,
            )

            rs.EnableObjectGrips(dim, False)

    rs.EnableRedraw(True)


if __name__ == "__main__":
    dimension_offset()
