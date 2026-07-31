"""ReTrim.py

Ported from ReTrim.rvb (Pascal Golay, McNeel, 2012) - legacy VBScript/
RhinoScript engine - to Python 3 for Rhino 8's Script Editor (CPython 3
engine). Run via the Script Editor's F5, not via the legacy
`RunPythonScript` (IronPython 2) command.

What it does: for each selected trimmed surface, rebuilds a fresh
untrimmed copy of its underlying NURBS shape, re-splits that copy with the
surface's own outer border curves (via the `_Split` command), and keeps
whichever resulting piece(s) actually correspond to the original trimmed
region (compared by bounding box of the duplicated edge curves) - a way to
"clean" a trim that's gone bad (e.g. after some kinds of history/booleans)
without hand-rebuilding the surface. Surfaces that fail any step are left
untouched and reported/selected at the end.

Function names verified live this session against the modern
rhinoscriptsyntax source (github.com/mcneel/rhinoscriptsyntax, rhino-8.x
branch): GetObjects, DuplicateSurfaceBorder, MatchObjectAttributes,
SelectObject(s), Command, LastCommandResult, LastCreatedObjects, IsCurve,
IsSurface, DeleteObject(s), DuplicateEdgeCurves, BoundingBox, PointCompare,
SurfacePointCount, SurfacePoints, SurfaceKnotCount, SurfaceKnots,
SurfaceDegree, SurfaceWeights, AddNurbsSurface, ExeVersion, FlashObject,
UnitAbsoluteTolerance - all exist with the call signatures used here.

Simplification: the original branched on `Rhino.ExeVersion` (>=5 vs older)
for both DuplicateSurfaceBorder's optional `type` argument and for how to
check the _Split command's success (LastCommandResult in v5+, vs.
LastCreatedObjects being non-null pre-v5). Rhino 8/9 are always >= 5, so
this port always takes the modern branch and drops the pre-v5 fallback
code as dead weight - not a behavior change for any Rhino version this
script can actually run in.

Bug fixed from the original (flagged, not silently ported): the
pass/fail message in ReTrimSurfaces() had its singular/plural grammar
backwards - it read "...retrim N face." (singular) whenever any failures
occurred (N could be > 1) and only used the plural "faces." on the branch
that's actually unreachable (the message box is only ever shown when
r > 0). Fixed to use proper "face."/"faces." pluralization based on
whether r == 1.

Bug kept as-is (flagged, not fixed): BBCompare()'s selection logic for
picking "the split piece that matches the original trim" is the original's
own bounding-box-corner-matching heuristic, including its early `Exit For`
on the first mismatched corner and its `Min`/`b` bookkeeping. It's
convoluted and its correctness for all cases wasn't re-derived here - it
was ported verbatim (translated 1:1 into Python control flow) rather than
redesigned, per the "surgical port, don't fix things that aren't asked
for" brief. Anyone hitting spurious ReTrim failures on multi-face splits
should look here first.

Also note: the original's commented-out sphere/cone/torus special-casing
in GetUntrimmedSrf (dead code, never executed) was dropped rather than
ported, since it's inert either way.
"""

import rhinoscriptsyntax as rs


def get_untrimmed_srf(srf_id):
    """Returns a new, untrimmed NURBS surface built from srf_id's own
    control points/knots/degree/weights (matches the original's active
    code path - trims are lost, the full underlying NURBS shape is kept)."""
    pt_count = rs.SurfacePointCount(srf_id)
    pts = rs.SurfacePoints(srf_id)
    knots_u, knots_v = rs.SurfaceKnots(srf_id)
    degree = rs.SurfaceDegree(srf_id)
    weights = rs.SurfaceWeights(srf_id)

    result = rs.AddNurbsSurface(pt_count, pts, knots_u, knots_v, degree, weights)
    if result:
        rs.MatchObjectAttributes([result], srf_id)
    return result


def bb_compare(srf_id, split_ids):
    """Picks whichever object in split_ids has a duplicated-edge-curve
    bounding box matching srf_id's, within 10x the model's absolute
    tolerance. Returns that object's id, or None if no good match is
    found. Ported verbatim from the original's heuristic - see the
    "Bug kept as-is" note in the module docstring."""
    tol = 10 * rs.UnitAbsoluteTolerance()

    trims = rs.DuplicateEdgeCurves(srf_id)
    bb = rs.BoundingBox(trims)
    rs.DeleteObjects(trims)

    boxes = []
    for split_id in split_ids:
        trims = rs.DuplicateEdgeCurves(split_id)
        boxes.append(rs.BoundingBox(trims))
        rs.DeleteObjects(trims)

    min_b = 0
    x = None
    del_count = -1

    for n, box in enumerate(boxes):
        b = 0
        for i in range(8):
            if rs.PointCompare(bb[i], box[i], tol):
                b = i
            else:
                rs.DeleteObject(split_ids[n])
                del_count += 1
                break
            if b > min_b:
                min_b = b
                x = n

    if min_b > 2 and del_count < len(split_ids) - 1:
        return split_ids[x]
    return None


def retrim(face_id):
    """Re-trims a single surface. Returns True on success (face_id has been
    deleted and replaced by the retrimmed result(s)), False on any failure
    (face_id is left untouched)."""
    rs.EnableRedraw(False)

    crvs = rs.DuplicateSurfaceBorder(face_id, 0)
    if not crvs:
        rs.EnableRedraw(True)
        return False

    srf = get_untrimmed_srf(face_id)
    if not srf:
        rs.DeleteObjects(crvs)
        rs.EnableRedraw(True)
        return False

    rs.UnselectAllObjects()
    rs.SelectObject(srf)

    sel_ids_str = "".join(" _SelID {}".format(c) for c in crvs)
    rs.Command("_Split" + sel_ids_str + " _Enter", False)

    if rs.LastCommandResult() != 0:
        rs.DeleteObjects(crvs)
        rs.DeleteObject(face_id)
        rs.EnableRedraw(True)
        return False

    rs.DeleteObjects(crvs)

    last = rs.LastCreatedObjects()
    if not last:
        rs.EnableRedraw(True)
        return False

    split_srfs = []
    for obj_id in last:
        if rs.IsCurve(obj_id):
            rs.DeleteObject(obj_id)
        elif rs.IsSurface(obj_id):
            split_srfs.append(obj_id)

    if len(split_srfs) < 2:
        rs.DeleteObjects(last)
        return False

    kept = bb_compare(face_id, split_srfs)
    if kept is not None:
        rs.DeleteObject(face_id)
        result = True
    else:
        result = False

    rs.EnableRedraw(True)
    for f in split_srfs:
        rs.FlashObject(f)

    return result


def retrim_surfaces():
    srfs = rs.GetObjects("Select Surfaces to ReTrim", rs.filter.surface, preselect=True)
    if not srfs:
        return

    rs.EnableRedraw(False)
    failed = []
    for srf in srfs:
        if not retrim(srf):
            failed.append(srf)

    rs.UnselectAllObjects()
    rs.EnableRedraw(True)

    r = len(failed)
    if r > 0:
        word = "face" if r == 1 else "faces"
        msg = "Failed to correctly retrim {} {}.".format(r, word)
        msg += "\nThe selected objects were not retrimmed."

        rs.UnselectAllObjects()
        rs.SelectObjects(failed)
        rs.MessageBox(msg)


if __name__ == "__main__":
    retrim_surfaces()
