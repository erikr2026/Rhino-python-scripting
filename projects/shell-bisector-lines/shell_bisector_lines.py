"""
shell_bisector_lines.py

Leaner, standalone companion to shell_bisector_t_surface.py (same repo,
projects/shell-bisector-t-surface/): loop over as many face-pair junctions
as needed in one run (same Esc-to-finish pattern as that script's Step 4),
building a bisecting surface between each pair, offsetting it both
directions by a shared offset distance, and intersecting each offset
surface against the two faces the bisector was built from (nothing else).
Each junction's outputs are grouped separately so multiple junctions in
one run stay distinguishable.

Still out of scope, unlike the full pipeline script: no T-fin
construction, no final connecting loft, no per-face topological-index
mapping-back to the original shell (moot here regardless - this script
never offsets the whole shell, so there is no offset-copy face that would
need mapping back to an original one). See this project's README for the
reasoning.

ENGINE: targets Python 3 (CPython, via Rhino 8/9's PythonNet bridge). Run
via Rhino's ScriptEditor command (type ScriptEditor, open this file, press
F5) - NOT RunPythonScript, which always invokes the legacy IronPython 2
engine regardless of what the script contains and will fail on this file
(confirmed in this repo's sibling project, 2026-07-22 - see its README).
Also not a Grasshopper component - this script gathers its own input via
interactive command-line prompts (rs.GetObject / rs.GetReal), it does not
expect GH-injected globals.

CORRECTED 2026-07-23 (real-Rhino run, owner feedback) - two fixes from the
first draft, both now confirmed, not guesses:
1. The first draft baked a duplicate copy of the whole original shell as
   a QA reference. The owner does not want that - removed entirely. This
   script no longer selects, extracts, or bakes the whole shell at all;
   it only ever touches the two faces picked per junction.
2. The first draft intersected each offset surface against the whole
   original shell - flagged at the time as an unconfirmed guess. Owner
   corrected: each offset surface must intersect ONLY against the two
   faces the bisector surface for that junction was built from (face1 and
   face2 from that junction's picks) - not the whole shell, not the two
   offsets against each other.
"""

import System
import rhinoscriptsyntax as rs
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc
from Rhino.Geometry.Intersect import Intersection


SAMPLES = 30  # seam-curve subdivision count for the bisector loft


def debug_log(step_name, status, details=""):
    """Prints diagnostic information to the Rhino Command Line."""
    msg = "[SHELL BISECTOR LINES] [{0}] {1}".format(step_name, status)
    if details:
        msg += " | {0}".format(details)
    print(msg)


def get_surface_subobject(prompt):
    """Prompts user to select a single Brep face (subobject) from a polysurface.

    rs.GetObject with a surface filter cannot pick individual faces off a
    joined polysurface - this needs raw Rhino.Input.Custom.GetObject with
    SubObjectSelect = True. Reused verbatim from
    shell_bisector_t_surface.py's get_surface_subobject().
    """
    rs.UnselectAllObjects()
    sc.doc.Objects.UnselectAll()
    sc.doc.Views.Redraw()

    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt(prompt)
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Surface
    go.SubObjectSelect = True
    go.EnablePreSelect(False, True)

    res = go.Get()
    if res != Rhino.Input.GetResult.Object:
        debug_log("Selection", "ABORTED", "No sub-object face selected")
        return None, None

    obj_ref = go.Object(0)
    face = obj_ref.Face()
    if face:
        debug_log("Selection", "SUCCESS", "Extracted BrepFace subobject (Index: {0})".format(face.FaceIndex))
        return face.DuplicateFace(False), face.FaceIndex

    obj = obj_ref.Object()
    if obj and isinstance(obj.Geometry, rg.Brep):
        brep = obj.Geometry
        if brep.Faces.Count > 0:
            debug_log("Selection", "SUCCESS", "Fallback face 0 selected")
            return brep.Faces[0].DuplicateFace(False), 0

    debug_log("Selection", "FAILED", "Could not extract face geometry")
    return None, None


def compute_bisector_surface(face1_brep, face2_brep, reach_distance, samples, tolerance):
    """Finds the shared seam edge between two single-face Breps, averages
    the two face normals along it, and projects outward by reach_distance
    to build a lofted bisector surface.

    Reused from shell_bisector_t_surface.py's compute_bisector_surface(),
    with the side-extension step dropped (not in this script's scope).
    """
    if not face1_brep or not face2_brep:
        debug_log("Bisector", "FAILED", "Missing face geometry")
        return None
    if face1_brep.Faces.Count == 0 or face2_brep.Faces.Count == 0:
        debug_log("Bisector", "FAILED", "Empty brep faces")
        return None

    face1 = face1_brep.Faces[0]
    face2 = face2_brep.Faces[0]

    ok, int_curves, int_points = Intersection.BrepBrep(face1_brep, face2_brep, tolerance)
    joint_curve = None
    if ok and int_curves:
        crv_list = [c for c in int_curves if c is not None]
        if crv_list:
            joint_curve = max(crv_list, key=lambda c: c.GetLength())

    if not joint_curve or joint_curve.GetLength() <= tolerance:
        debug_log("Bisector", "FAILED", "No shared seam edge found between the two selected faces")
        return None

    debug_log("Bisector", "Seam Edge Found", "Length: {0:.3f}".format(joint_curve.GetLength()))

    t_vals = joint_curve.DivideByCount(samples, True)
    if not t_vals:
        debug_log("Bisector", "FAILED", "Could not subdivide seam curve")
        return None

    pts_start = []
    pts_end = []

    for t in t_vals:
        pt = joint_curve.PointAt(t)

        ok1, u1, v1 = face1.ClosestPoint(pt)
        n1 = face1.NormalAt(u1, v1) if ok1 else rg.Vector3d.ZAxis

        ok2, u2, v2 = face2.ClosestPoint(pt)
        n2 = face2.NormalAt(u2, v2) if ok2 else rg.Vector3d.ZAxis

        n1.Unitize()
        n2.Unitize()

        bisect_vec = n1 + n2
        if bisect_vec.Length < 1e-6:
            tangent = joint_curve.TangentAt(t)
            bisect_vec = rg.Vector3d.CrossProduct(tangent, n1)
        bisect_vec.Unitize()

        pts_start.append(pt)
        pts_end.append(pt + (bisect_vec * reach_distance))

    crv_start = rg.NurbsCurve.CreateInterpolatedCurve(pts_start, 3)
    crv_end = rg.NurbsCurve.CreateInterpolatedCurve(pts_end, 3)
    if not crv_start or not crv_end:
        debug_log("Bisector", "FAILED", "Could not interpolate seam/projected curves")
        return None

    lofts = rg.Brep.CreateFromLoft(
        [crv_start, crv_end], rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Normal, False
    )
    loft_array = lofts[0] if isinstance(lofts, tuple) else lofts
    if loft_array:
        loft_list = [b for b in loft_array if b is not None]
        if loft_list:
            debug_log("Bisector", "SUCCESS", "Generated bisector surface (reach={0})".format(reach_distance))
            return loft_list[0]

    debug_log("Bisector", "FAILED", "Loft operation failed")
    return None


def offset_brep(source_brep, distance, tolerance):
    """Offsets a brep by a signed distance, with a face-by-face fallback if
    the whole-brep offset fails. Reused (renamed) from
    shell_bisector_t_surface.py's offset_shell(), confirmed working on the
    real hull 2026-07-22 - not re-verified live this session.
    """
    if not source_brep or not source_brep.IsValid:
        debug_log("Offset", "FAILED", "Invalid input brep")
        return None

    offset_res = rg.Brep.CreateOffsetBrep(source_brep, distance, False, True, tolerance)
    if offset_res:
        brep_array = offset_res[0] if isinstance(offset_res, tuple) else offset_res
        if brep_array:
            brep_list = [b for b in brep_array if b is not None]
            if brep_list:
                debug_log("Offset", "SUCCESS", "distance={0}".format(distance))
                return brep_list[0]

    # Fallback: offset each face individually and rejoin.
    face_offsets = []
    for i in range(source_brep.Faces.Count):
        srf = source_brep.Faces[i].DuplicateSurface()
        off = srf.Offset(distance, tolerance)
        if off:
            face_offsets.append(off.ToBrep())

    if face_offsets:
        joined = rg.Brep.JoinBreps(face_offsets, tolerance)
        joined_array = joined[0] if isinstance(joined, tuple) else joined
        if joined_array:
            joined_list = [b for b in joined_array if b is not None]
            if joined_list:
                debug_log("Offset", "SUCCESS (Fallback)", "distance={0}".format(distance))
                return joined_list[0]

    debug_log("Offset", "FAILED", "distance={0}".format(distance))
    return None


def intersect_breps(brep_a, brep_b, tolerance):
    """Intersects two breps and returns any resulting intersection curves.

    Intersection.BrepBrep returns a 3-tuple (bool success, Curve[] curves,
    Point3d[] points) under PythonNet - confirmed via this repo's prior
    debugging history (shell-bisector-t-surface project), not re-verified
    live this session.
    """
    if not brep_a or not brep_b:
        return []

    ok, curves, points = Intersection.BrepBrep(brep_a, brep_b, tolerance)
    if not ok or not curves:
        return []

    return [c for c in curves if c is not None]


def get_or_create_layer(layer_name, color):
    """Creates a color-coded layer in the document (or returns the existing one)."""
    layer_idx = sc.doc.Layers.Find(layer_name, True)
    if layer_idx < 0:
        new_layer = Rhino.DocObjects.Layer()
        new_layer.Name = layer_name
        new_layer.Color = color
        layer_idx = sc.doc.Layers.Add(new_layer)
    return layer_idx


def bake_item(geom, layer_name, color):
    """Bakes a geometry object to a dedicated color-coded layer. Returns
    System.Guid.Empty on failure so callers can filter it out of group
    membership lists without a None check.
    """
    if not geom:
        return System.Guid.Empty

    layer_idx = get_or_create_layer(layer_name, color)
    attr = Rhino.DocObjects.ObjectAttributes()
    attr.LayerIndex = layer_idx

    if isinstance(geom, rg.Brep):
        return sc.doc.Objects.AddBrep(geom, attr)
    elif isinstance(geom, rg.Curve):
        return sc.doc.Objects.AddCurve(geom, attr)
    return System.Guid.Empty


def main():
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance

    print("==========================================")
    print("RHINO SHELL BISECTOR LINES TOOL")
    print("==========================================")

    # Step 1: Reach/extent distance and offset distance - once for the
    # whole run, applied to every junction. No whole-shell selection here -
    # this script only ever touches the faces picked per junction below.
    reach_distance = rs.GetReal("Enter bisector reach/extent distance", 5.0, 0.001, 1000.0)
    if reach_distance is None:
        debug_log("Step 1", "ABORTED", "Reach distance entry canceled")
        return

    offset_distance = rs.GetReal("Enter offset distance (applied both +/- from the bisector)", 0.5, 0.001, 1000.0)
    if offset_distance is None:
        debug_log("Step 1", "ABORTED", "Offset distance entry canceled")
        return

    # Step 2: loop over as many junctions as needed. Cancel ("Esc") on the
    # FIRST-face prompt of a pair stops the run - reused directly from
    # shell_bisector_t_surface.py's Step 4 loop.
    junction_count = 0

    while True:
        attempt_num = junction_count + 1
        print("\n--- SELECT FACES FOR JUNCTION {0} (Esc on first pick to finish) ---".format(attempt_num))

        face1_brep, idx1 = get_surface_subobject(
            "Select FIRST face for junction {0} (Esc when finished with all junctions)".format(attempt_num)
        )
        if not face1_brep:
            debug_log("Step 2", "DONE", "No more junctions selected")
            break

        face2_brep, idx2 = get_surface_subobject("Select SECOND face for junction {0}".format(attempt_num))
        if not face2_brep:
            debug_log("Step 2", "ABORTED", "Second face selection canceled for junction {0}".format(attempt_num))
            break

        if idx1 is not None and idx2 is not None and idx1 == idx2:
            debug_log(
                "Junction {0}".format(attempt_num),
                "FAILED",
                "Same face picked twice - select two different faces that share an edge, try again",
            )
            continue

        junction_count = attempt_num
        undo_rec = doc.BeginUndoRecord("Shell Bisector Lines - Junction {0}".format(junction_count))
        result_ids = []

        try:
            # 2a: compute + bake the bisector surface for this junction.
            bisector_brep = compute_bisector_surface(face1_brep, face2_brep, reach_distance, SAMPLES, tol)
            if not bisector_brep:
                debug_log("Junction {0}".format(junction_count), "FAILED", "Could not compute bisector surface - skipping junction")
            else:
                bis_id = bake_item(bisector_brep, "01_Bisector", System.Drawing.Color.Yellow)
                if bis_id != System.Guid.Empty:
                    result_ids.append(bis_id)

                # 2b: offset the bisector both directions and bake each.
                offset_pos = offset_brep(bisector_brep, offset_distance, tol)
                offset_neg = offset_brep(bisector_brep, -offset_distance, tol)

                if offset_pos:
                    id_p = bake_item(offset_pos, "02_Offset_Pos", System.Drawing.Color.Orange)
                    if id_p != System.Guid.Empty:
                        result_ids.append(id_p)
                else:
                    debug_log("Junction {0}".format(junction_count), "WARNING", "Positive offset failed - skipping its intersections")

                if offset_neg:
                    id_n = bake_item(offset_neg, "02_Offset_Neg", System.Drawing.Color.Purple)
                    if id_n != System.Guid.Empty:
                        result_ids.append(id_n)
                else:
                    debug_log("Junction {0}".format(junction_count), "WARNING", "Negative offset failed - skipping its intersections")

                # 2c: intersect each offset surface against ONLY the two
                # faces this junction's bisector was built from - face1 and
                # face2 - not the whole shell, not the offsets against each
                # other. Confirmed by the owner 2026-07-23 (see docstring).
                offset_variants = [("Offset_Pos", offset_pos), ("Offset_Neg", offset_neg)]
                ref_faces = [("Face1", face1_brep), ("Face2", face2_brep)]

                curves_all = []
                for offset_label, offset_geom in offset_variants:
                    if not offset_geom:
                        continue
                    for face_label, ref_brep in ref_faces:
                        found = intersect_breps(offset_geom, ref_brep, tol)
                        if found:
                            debug_log(
                                "Junction {0}".format(junction_count),
                                "Intersection",
                                "{0} vs {1}: {2} curve(s)".format(offset_label, face_label, len(found)),
                            )
                        curves_all.extend(found)

                for c in curves_all:
                    cid = bake_item(c, "03_Intersections", System.Drawing.Color.Red)
                    if cid != System.Guid.Empty:
                        result_ids.append(cid)

                debug_log(
                    "Junction {0}".format(junction_count),
                    "COMPLETE",
                    "{0} intersection curve(s) baked".format(len(curves_all)),
                )

            # 2d: group this junction's outputs so multiple junctions in
            # one run stay visually distinguishable. AddObjectsToGroup only
            # adds to an EXISTING group - it does not create one - so the
            # group must be created first (per shell_bisector_t_surface.py's
            # own documented fix for this exact silent-no-op bug).
            if result_ids:
                group_name = "ShellBisectorLines_Junction_{0:02d}".format(junction_count)
                rs.AddGroup(group_name)
                rs.AddObjectsToGroup(result_ids, group_name)
                debug_log("Group", "SUCCESS", "{0} object(s) grouped as '{1}'".format(len(result_ids), group_name))

        except Exception as e:
            debug_log("Junction {0}".format(junction_count), "ERROR", str(e))
        finally:
            doc.Views.Redraw()
            doc.EndUndoRecord(undo_rec)

    print("\n==========================================")
    debug_log("Execution", "COMPLETE", "Processed {0} junction(s). Check baked layers 01 through 03.".format(junction_count))
    print("==========================================")


if __name__ == "__main__":
    main()
