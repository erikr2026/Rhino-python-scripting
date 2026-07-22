import math
import System
import rhinoscriptsyntax as rs
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc


def debug_log(step_name, status, details=""):
    """Prints diagnostic information to the Rhino Command Line."""
    msg = "[SHELL BISECTOR] [{0}] {1}".format(step_name, status)
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
    """Prompts user to select a single Brep face (subobject) from a polysurface."""
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


def get_corresponding_original_face(orig_brep, offset_sub_brep, face_idx):
    """Finds the BrepFace on the original shell corresponding to face_idx or spatial proximity."""
    if not orig_brep or not offset_sub_brep:
        return None

    # Primary check: Topological index matching
    if face_idx is not None and 0 <= face_idx < orig_brep.Faces.Count:
        cand_face = orig_brep.Faces[face_idx]
        face_bb = offset_sub_brep.GetBoundingBox(True)
        pt_center = face_bb.Center
        ok, u, v = cand_face.ClosestPoint(pt_center)
        if ok:
            pt_on_cand = cand_face.PointAt(u, v)
            if pt_center.DistanceTo(pt_on_cand) < 100.0:
                debug_log("Face Mapping", "Matched by Index", "Face Index: {0}".format(face_idx))
                return cand_face.DuplicateFace(False)

    # Fallback: Spatial proximity matching across original faces
    face_bb = offset_sub_brep.GetBoundingBox(True)
    pt_center = face_bb.Center
    best_face = None
    min_d = float('inf')

    for i in range(orig_brep.Faces.Count):
        f = orig_brep.Faces[i]
        ok, u, v = f.ClosestPoint(pt_center)
        if ok:
            d = pt_center.DistanceTo(f.PointAt(u, v))
            if d < min_d:
                min_d = d
                best_face = f

    if best_face:
        debug_log("Face Mapping", "Matched by Distance", "Min Dist: {0:.3f}".format(min_d))
        return best_face.DuplicateFace(False)

    return None


def intersect_with_shell(offset_bisector_brep, target_orig_breps, tolerance):
    """Intersects offset bisector surface ONLY with the corresponding target faces of the original shell."""
    if not offset_bisector_brep or not target_orig_breps:
        return []

    all_curves = []
    for orig_sub in target_orig_breps:
        if not orig_sub:
            continue
        res = rg.Intersect.Intersection.BrepBrep(offset_bisector_brep, orig_sub, tolerance)
        if isinstance(res, tuple) and len(res) >= 2:
            ok, curves = res[0], res[1]
            if ok and curves:
                crv_list = [c for c in curves if c is not None]
                all_curves.extend(crv_list)

    debug_log("Intersection", "Result", "Found {0} intersection curves on target original faces".format(len(all_curves)))
    return all_curves


def prompt_parameters():
    """Prompts user for shell offset distance, direction, bisector side extension, and fin parameters."""
    print("\n--- PARAMETER SETUP ---")

    dist = rs.GetReal("Enter Shell Offset Distance", 2.0, 0.001, 1000.0)
    if dist is None:
        return None

    dir_opt = rs.GetBoolean("Select Shell Offset Direction", [("Direction", "Inward", "Outward")], [True])
    if dir_opt is None:
        return None

    is_outward = dir_opt[0]
    signed_dist = dist if is_outward else -dist

    bisect_len = rs.GetReal("Enter Bisector Surface Extension Length", 5.0, 0.01, 1000.0)
    if bisect_len is None:
        return None

    side_ext = rs.GetReal("Enter Bisector Side Extension Distance (at open edges)", 12.0, 0.0, 1000.0)
    if side_ext is None:
        return None

    fin_dist1 = rs.GetReal("Enter T-Fin Side 1 Offset Distance", 1.0, 0.01, 1000.0)
    if fin_dist1 is None:
        return None

    fin_dist2 = rs.GetReal("Enter T-Fin Side 2 Offset Distance", 1.0, 0.01, 1000.0)
    if fin_dist2 is None:
        return None

    off_pos = rs.GetReal("Enter Positive Bisector Offset Distance", 0.5, 0.001, 1000.0)
    if off_pos is None:
        return None

    off_neg = rs.GetReal("Enter Negative Bisector Offset Distance", 0.8, 0.001, 1000.0)
    if off_neg is None:
        return None

    params = {
        "shell_offset": signed_dist,
        "bisector_len": bisect_len,
        "side_ext": side_ext,
        "fin_dist1": fin_dist1,
        "fin_dist2": fin_dist2,
        "off_pos": off_pos,
        "off_neg": off_neg
    }

    return params


def offset_shell(original_brep, distance, tolerance):
    """Offsets original shell polysurface handling PythonNet tuple returns in Rhino 8/9."""
    if not original_brep or not original_brep.IsValid:
        debug_log("Offset Shell", "FAILED", "Invalid input brep")
        return None

    offset_res = rg.Brep.CreateOffsetBrep(original_brep, distance, False, True, tolerance)
    if offset_res:
        if isinstance(offset_res, tuple) and len(offset_res) > 0:
            brep_array = offset_res[0]
        else:
            brep_array = offset_res

        if brep_array:
            brep_list = [b for b in brep_array if b is not None]
            if len(brep_list) > 0:
                res = brep_list[0]
                debug_log("Offset Shell", "SUCCESS", "Faces count: {0}".format(res.Faces.Count))
                return res

    # Fallback face-by-face offset
    face_offsets = []
    for i in range(original_brep.Faces.Count):
        f = original_brep.Faces[i]
        srf = f.DuplicateSurface()
        off = srf.Offset(distance, tolerance)
        if off:
            face_offsets.append(off.ToBrep())

    if face_offsets:
        joined = rg.Brep.JoinBreps(face_offsets, tolerance)
        if joined:
            if isinstance(joined, tuple) and len(joined) > 0:
                joined_array = joined[0]
            else:
                joined_array = joined
            if joined_array:
                joined_list = [b for b in joined_array if b is not None]
                if len(joined_list) > 0:
                    debug_log("Offset Shell", "SUCCESS (Fallback)", "Joined faces: {0}".format(len(face_offsets)))
                    return joined_list[0]

    debug_log("Offset Shell", "FAILED", "Offset calculation returned empty result")
    return None


def compute_bisector_surface(srf1_brep, srf2_brep, length, side_ext, samples, tolerance):
    """Computes a bisector surface along the shared intersection edge, extending side edges by side_ext."""
    if not srf1_brep or not srf2_brep:
        debug_log("Bisector", "FAILED", "Null input face geometry")
        return None, None

    if srf1_brep.Faces.Count == 0 or srf2_brep.Faces.Count == 0:
        debug_log("Bisector", "FAILED", "Empty brep faces")
        return None, None

    face1 = srf1_brep.Faces[0]
    face2 = srf2_brep.Faces[0]

    # Intersect two faces to extract joint edge
    res = rg.Intersect.Intersection.BrepBrep(srf1_brep, srf2_brep, tolerance)
    joint_curve = None
    if isinstance(res, tuple) and len(res) >= 2:
        ok, int_curves = res[0], res[1]
        if ok and int_curves:
            crv_list = [c for c in int_curves if c is not None]
            if len(crv_list) > 0:
                joint_curve = max(crv_list, key=lambda c: c.GetLength())

    if not joint_curve or joint_curve.GetLength() <= tolerance:
        debug_log("Bisector", "FAILED", "No shared intersection edge found between selected faces")
        return None, None

    debug_log("Bisector", "Joint Edge Found", "Length: {0:.3f}".format(joint_curve.GetLength()))

    t_vals = joint_curve.DivideByCount(samples, True)
    if not t_vals:
        return None, None

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
        pt_end = pt + (bisect_vec * length)

        pts_start.append(pt)
        pts_end.append(pt_end)

    crv_start = rg.NurbsCurve.CreateInterpolatedCurve(pts_start, 3)
    crv_end = rg.NurbsCurve.CreateInterpolatedCurve(pts_end, 3)

    if side_ext > 1e-6 and crv_start and crv_end:
        ext_start = crv_start.Extend(rg.CurveEnd.Both, side_ext, rg.CurveExtensionStyle.Line)
        ext_end = crv_end.Extend(rg.CurveEnd.Both, side_ext, rg.CurveExtensionStyle.Line)
        if ext_start and ext_end:
            crv_start = ext_start
            crv_end = ext_end
            debug_log("Bisector", "Side Extension", "Extended edges by {0:.2f} units".format(side_ext))

    if crv_start and crv_end:
        lofts = rg.Brep.CreateFromLoft([crv_start, crv_end], rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Normal, False)
        if lofts:
            if isinstance(lofts, tuple) and len(lofts) > 0:
                loft_array = lofts[0]
            else:
                loft_array = lofts
            loft_list = [b for b in loft_array if b is not None]
            if len(loft_list) > 0:
                debug_log("Bisector", "SUCCESS", "Generated bisector surface with extended side edges")
                return loft_list[0], crv_start

    debug_log("Bisector", "FAILED", "Loft operation failed")
    return None, None


def build_t_fin_surface(bisector_brep, primary_edge, dist1, dist2, samples, tolerance):
    """Generates a perpendicular T-fin surface along the primary edge of the bisector."""
    if not bisector_brep or not primary_edge or bisector_brep.Faces.Count == 0:
        debug_log("T-Fin", "FAILED", "Missing bisector or edge curve")
        return None, None, None

    face = bisector_brep.Faces[0]
    t_vals = primary_edge.DivideByCount(samples, True)
    if not t_vals:
        return None, None, None

    pts1 = []
    pts2 = []

    for t in t_vals:
        pt = primary_edge.PointAt(t)
        ok, u, v = face.ClosestPoint(pt)
        normal = face.NormalAt(u, v) if ok else rg.Vector3d.ZAxis
        normal.Unitize()

        pts1.append(pt + (normal * dist1))
        pts2.append(pt - (normal * dist2))

    crv1 = rg.NurbsCurve.CreateInterpolatedCurve(pts1, 3)
    crv2 = rg.NurbsCurve.CreateInterpolatedCurve(pts2, 3)

    if crv1 and crv2:
        lofts = rg.Brep.CreateFromLoft([crv1, crv2], rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Normal, False)
        if lofts:
            if isinstance(lofts, tuple) and len(lofts) > 0:
                loft_array = lofts[0]
            else:
                loft_array = lofts
            loft_list = [b for b in loft_array if b is not None]
            if len(loft_list) > 0:
                debug_log("T-Fin", "SUCCESS", "Generated fin surface")
                return loft_list[0], crv1, crv2

    debug_log("T-Fin", "FAILED", "Fin loft calculation failed")
    return None, None, None


def loft_fin_to_shell(fin_edge, int_curves, tolerance):
    """Lofts a connecting surface between a T-fin edge and the matching shell intersection curve."""
    if not fin_edge or not int_curves:
        debug_log("Loft", "SKIPPED", "Missing fin edge or intersection curves")
        return None

    pt_start = fin_edge.PointAtStart
    best_crv = None
    min_dist = float("inf")

    for crv in int_curves:
        if not crv:
            continue
        ok, t = crv.ClosestPoint(pt_start)
        if ok:
            d = pt_start.DistanceTo(crv.PointAt(t))
            if d < min_dist:
                min_dist = d
                best_crv = crv

    if not best_crv:
        debug_log("Loft", "FAILED", "No matching intersection curve found")
        return None

    crv1 = fin_edge.DuplicateCurve()
    crv2 = best_crv.DuplicateCurve()

    # Align curve directions before lofting to avoid twisting
    if not rg.Curve.DoDirectionsMatch(crv1, crv2):
        crv2.Reverse()

    lofts = rg.Brep.CreateFromLoft([crv1, crv2], rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Normal, False)
    if lofts:
        if isinstance(lofts, tuple) and len(lofts) > 0:
            loft_array = lofts[0]
        else:
            loft_array = lofts
        if loft_array:
            loft_list = [b for b in loft_array if isinstance(b, rg.Brep)]
            if loft_list:
                debug_log("Loft", "SUCCESS", "Lofted connecting surface generated (Dist: {0:.3f})".format(min_dist))
                return loft_list[0]

    debug_log("Loft", "FAILED", "Loft calculation returned empty")
    return None


def get_or_create_layer(layer_name, color):
    """Creates a color-coded layer in the document."""
    layer_idx = sc.doc.Layers.Find(layer_name, True)
    if layer_idx < 0:
        new_layer = Rhino.DocObjects.Layer()
        new_layer.Name = layer_name
        new_layer.Color = color
        layer_idx = sc.doc.Layers.Add(new_layer)
    return layer_idx


def bake_item(geom, layer_name, color):
    """Bakes geometry object to a dedicated color-coded layer."""
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
    print("RHINO SHELL BISECTOR & T-SURFACE TOOL")
    print("==========================================")

    # Step 1: Select Original Shell
    orig_id = rs.GetObject("Select ORIGINAL shell polysurface", rs.filter.surface | rs.filter.polysurface)
    if not orig_id:
        debug_log("Step 1", "ABORTED", "No original shell selected")
        return

    orig_brep = extract_brep(orig_id)
    debug_log("Step 1", "Original Shell Loaded", "GUID: {0}".format(orig_id))

    # Step 2: Prompt Parameters
    params = prompt_parameters()
    if not params:
        debug_log("Step 2", "ABORTED", "Parameter setup canceled")
        return

    # Step 3: Compute & Bake Shell Offset
    offset_brep = offset_shell(orig_brep, params["shell_offset"], tol)
    if not offset_brep:
        debug_log("Step 3", "FAILED", "Could not offset original shell")
        return

    offset_id = bake_item(offset_brep, "02_Shell_Offset", System.Drawing.Color.Cyan)
    doc.Views.Redraw()
    debug_log("Step 3", "Shell Offset Created", "GUID: {0}".format(offset_id))

    # Step 4: Select 2 Surfaces on Shell Offset
    print("\n--- SELECT SURFACES ON SHELL OFFSET ---")
    srf1_brep, idx1 = get_surface_subobject("Select FIRST surface on the created shell offset")
    if not srf1_brep:
        debug_log("Step 4", "ABORTED", "First surface selection canceled")
        return

    srf2_brep, idx2 = get_surface_subobject("Select SECOND surface on the created shell offset")
    if not srf2_brep:
        debug_log("Step 4", "ABORTED", "Second surface selection canceled")
        return

    # Map selected offset faces to target corresponding faces on original shell
    orig_srf1 = get_corresponding_original_face(orig_brep, srf1_brep, idx1)
    orig_srf2 = get_corresponding_original_face(orig_brep, srf2_brep, idx2)
    target_orig_faces = [f for f in [orig_srf1, orig_srf2] if f is not None]

    undo_rec = doc.BeginUndoRecord("Shell Bisector & T-Surface")

    try:
        sample_count = 30

        # Step 5: Compute Bisector Surface (with side extension)
        bisector_brep, primary_edge = compute_bisector_surface(
            srf1_brep, srf2_brep, params["bisector_len"], params["side_ext"], sample_count, tol
        )
        if bisector_brep:
            bake_item(bisector_brep, "03_Bisector", System.Drawing.Color.Yellow)

        # Step 6: Build T-Fin Surface
        fin_brep, fin_edge1, fin_edge2 = build_t_fin_surface(
            bisector_brep, primary_edge, params["fin_dist1"], params["fin_dist2"], sample_count, tol
        )
        if fin_brep:
            bake_item(fin_brep, "04_T_Fin", System.Drawing.Color.Magenta)

        # Step 7: Offset Bisector Surface (+ / -)
        bisector_pos = offset_shell(bisector_brep, params["off_pos"], tol)
        bisector_neg = offset_shell(bisector_brep, -params["off_neg"], tol)

        if bisector_pos:
            bake_item(bisector_pos, "05_OffsetBisector_Pos", System.Drawing.Color.Orange)
        if bisector_neg:
            bake_item(bisector_neg, "05_OffsetBisector_Neg", System.Drawing.Color.Purple)

        # Step 8: Intersect Offset Bisectors ONLY with target ORIGINAL shell surfaces
        crvs_pos = intersect_with_shell(bisector_pos, target_orig_faces, tol)
        crvs_neg = intersect_with_shell(bisector_neg, target_orig_faces, tol)

        for c in crvs_pos + crvs_neg:
            bake_item(c, "06_Intersections", System.Drawing.Color.Red)

        # Step 9: Loft Fin Edges to Shell Intersections
        srf_pos = loft_fin_to_shell(fin_edge1, crvs_pos, tol)
        srf_neg = loft_fin_to_shell(fin_edge2, crvs_neg, tol)

        result_ids = []
        if srf_pos:
            id_p = bake_item(srf_pos, "07_FinalLofts", System.Drawing.Color.Green)
            result_ids.append(id_p)
        if srf_neg:
            id_n = bake_item(srf_neg, "07_FinalLofts", System.Drawing.Color.Green)
            result_ids.append(id_n)

        if result_ids:
            rs.AddObjectsToGroup(result_ids, "Shell_Bisector_Result")

        print("\n==========================================")
        debug_log("Execution", "COMPLETE", "Check baked layers 02 through 07 in Rhino viewport.")
        print("==========================================")

    except Exception as e:
        debug_log("Execution", "ERROR", str(e))
    finally:
        doc.Views.Redraw()
        doc.EndUndoRecord(undo_rec)


if __name__ == "__main__":
    main()
