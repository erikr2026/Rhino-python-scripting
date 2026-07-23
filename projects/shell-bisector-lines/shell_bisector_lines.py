"""
shell_bisector_lines.py

Leaner, standalone companion to shell_bisector_t_surface.py (same repo,
projects/shell-bisector-t-surface/): select a shell, then loop over as
many face-pair junctions as needed in one run (same Esc-to-finish pattern
as that script's Step 4), building a bisecting surface between each pair,
offsetting it both directions by a shared offset distance, and
intersecting each offset against the original shell to produce reference/
cut lines. Each junction's outputs are grouped separately so multiple
junctions in one run stay distinguishable.

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

ASSUMPTION FLAGGED FOR OWNER REVIEW - NOT CONFIRMED:
Step 5d below intersects EACH of the two offset surfaces, per junction,
against the ORIGINAL, unmodified shell - not against each other. The
source request said only "intersect the offset surfaces" without saying
against what; a clarifying question went unanswered this session, so this
is a best-guess implementation, not a confirmed spec. If the owner
actually meant the two offset surfaces intersected against EACH OTHER
instead, that's a small change: call
intersect_brep_with_shell(offset_pos, offset_neg, tol) instead of passing
shell_brep as the second argument (see main(), inside the junction loop).

No RhinoCommon/rhinoscriptsyntax signature in this file was freshly
verified via live docs or a console help() call this session. Every call
touching a non-trivial C# signature (Brep.CreateOffsetBrep,
Intersection.BrepBrep, Brep.CreateFromLoft, Brep.JoinBreps) is reused
verbatim or near-verbatim from shell_bisector_t_surface.py, which the
owner confirmed running successfully end-to-end on the real hull on
2026-07-22 - that prior confirmation is the basis for trusting these calls
here, not a fresh verification pass this session.
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


def extract_brep(obj_id):
    """Converts a Rhino document object GUID into a standalone Brep geometry."""
    if not obj_id:
        return None

    rhino_obj = sc.doc.Objects.FindId(obj_id)
    if not rhino_obj:
        return None

    geom = rhino_obj.Geometry
    if isinstance(geom, rg.Brep):
        return geom.DuplicateBrep()
    elif isinstance(geom, rg.Surface):
        return geom.ToBrep()
    return None


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


def intersect_brep_with_shell(offset_brep_geom, target_brep, tolerance):
    """Intersects one offset surface against target_brep and returns any
    resulting intersection curves.

    Intersection.BrepBrep returns a 3-tuple (bool success, Curve[] curves,
    Point3d[] points) under PythonNet - confirmed via this repo's prior
    debugging history (shell-bisector-t-surface project), not re-verified
    live this session.
    """
    if not offset_brep_geom or not target_brep:
        return []

    ok, curves, points = Intersection.BrepBrep(offset_brep_geom, target_brep, tolerance)
    if not ok or not curves:
        return []

    result = [c for c in curves if c is not None]
    debug_log("Intersection", "Result", "{0} curve(s) found".format(len(result)))
    return result


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

    # Step 1: Select the shell polysurface.
    shell_id = rs.GetObject("Select the shell polysurface", rs.filter.surface | rs.filter.polysurface)
    if not shell_id:
        debug_log("Step 1", "ABORTED", "No shell selected")
        return

    shell_brep = extract_brep(shell_id)
    if not shell_brep or not shell_brep.IsValid:
        debug_log("Step 1", "FAILED", "Selected object is not a valid surface/polysurface")
        return
    debug_log("Step 1", "Shell Loaded", "GUID: {0}".format(shell_id))

    # Step 2: Reach/extent distance and offset distance - once for the
    # whole run, applied to every junction.
    reach_distance = rs.GetReal("Enter bisector reach/extent distance", 5.0, 0.001, 1000.0)
    if reach_distance is None:
        debug_log("Step 2", "ABORTED", "Reach distance entry canceled")
        return

    offset_distance = rs.GetReal("Enter offset distance (applied both +/- from the bisector)", 0.5, 0.001, 1000.0)
    if offset_distance is None:
        debug_log("Step 2", "ABORTED", "Offset distance entry canceled")
        return

    # Step 3: bake the original shell once, unmodified, as a QA reference
    # copy - it doesn't change per junction.
    undo_shell = doc.BeginUndoRecord("Shell Bisector Lines - Original Shell Reference")
    try:
        bake_item(shell_brep.DuplicateBrep(), "01_Original_Shell", System.Drawing.Color.Gainsboro)
        debug_log("Step 3", "Original Shell Baked", "Reference copy on layer 01_Original_Shell")
    finally:
        doc.Views.Redraw()
        doc.EndUndoRecord(undo_shell)

    # Step 4: loop over as many junctions as needed. Cancel ("Esc") on the
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
            debug_log("Step 4", "DONE", "No more junctions selected")
            break

        face2_brep, idx2 = get_surface_subobject("Select SECOND face for junction {0}".format(attempt_num))
        if not face2_brep:
            debug_log("Step 4", "ABORTED", "Second face selection canceled for junction {0}".format(attempt_num))
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
            # 4a: compute + bake the bisector surface for this junction.
            bisector_brep = compute_bisector_surface(face1_brep, face2_brep, reach_distance, SAMPLES, tol)
            if not bisector_brep:
                debug_log("Junction {0}".format(junction_count), "FAILED", "Could not compute bisector surface - skipping junction")
            else:
                bis_id = bake_item(bisector_brep, "02_Bisector", System.Drawing.Color.Yellow)
                if bis_id != System.Guid.Empty:
                    result_ids.append(bis_id)

                # 4b: offset the bisector both directions and bake each.
                offset_pos = offset_brep(bisector_brep, offset_distance, tol)
                offset_neg = offset_brep(bisector_brep, -offset_distance, tol)

                if offset_pos:
                    id_p = bake_item(offset_pos, "03_Offset_Pos", System.Drawing.Color.Orange)
                    if id_p != System.Guid.Empty:
                        result_ids.append(id_p)
                else:
                    debug_log("Junction {0}".format(junction_count), "WARNING", "Positive offset failed - skipping its intersection")

                if offset_neg:
                    id_n = bake_item(offset_neg, "03_Offset_Neg", System.Drawing.Color.Purple)
                    if id_n != System.Guid.Empty:
                        result_ids.append(id_n)
                else:
                    debug_log("Junction {0}".format(junction_count), "WARNING", "Negative offset failed - skipping its intersection")

                # 4c: intersect each offset surface against the ORIGINAL
                # shell. See the module docstring / README for why this is
                # flagged as an unconfirmed assumption, and how to swap to
                # the other reading (offsets against each other instead).
                curves_pos = intersect_brep_with_shell(offset_pos, shell_brep, tol) if offset_pos else []
                curves_neg = intersect_brep_with_shell(offset_neg, shell_brep, tol) if offset_neg else []

                for c in curves_pos + curves_neg:
                    cid = bake_item(c, "04_Intersections", System.Drawing.Color.Red)
                    if cid != System.Guid.Empty:
                        result_ids.append(cid)

                debug_log(
                    "Junction {0}".format(junction_count),
                    "COMPLETE",
                    "{0} positive + {1} negative intersection curve(s) baked".format(len(curves_pos), len(curves_neg)),
                )

            # 4d: group this junction's outputs so multiple junctions in
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
    debug_log("Execution", "COMPLETE", "Processed {0} junction(s). Check baked layers 01 through 04.".format(junction_count))
    print("==========================================")


if __name__ == "__main__":
    main()
