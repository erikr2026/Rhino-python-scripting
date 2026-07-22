# -*- coding: utf-8 -*-
"""
Shell Bisector T-Surface Generator

Run via Rhino 8's ScriptEditor (type ScriptEditor, open this file, press F5) —
this runs Python 3 (CPython). Do NOT run via the RunPythonScript command;
that invokes the legacy IronPython 2 engine instead, which this script no
longer targets.

Takes a shell polysurface, offsets the two selected panels individually
(not the whole shell - see Stage 1 comment for why), computes a bisector
surface between them, builds a T-shaped junction, intersects against the
original shell, and lofts connecting surfaces.

API signatures live-verified against developer.rhino3d.com / mcneel/rhinoscriptsyntax
source (2026-07-22, after RunPythonScript/first-run bugs surfaced three invented or
wrong signatures - see the project's Lessons for the full story):
- rs.OffsetSurface(surface_id, distance, tolerance=None, both_sides=False,
  create_solid=False) - NOT `solid=`, that keyword doesn't exist
- rs.AddLoftSrf(object_ids, start=None, end=None, loft_type=0,
  simplify_method=0, value=0, closed=False) - only called positionally here
- rs.AddCurve(points, degree=3) - points-only; does NOT accept an existing
  Curve object, use Objects.AddCurve (see bake_curve() below) for that
- rs.AddBrep - does not exist in rhinoscriptsyntax at all; use
  Objects.AddBrep (see bake_brep() below)
- Curve.DivideByCount(count, create_end_point)
- BrepFace.NormalAt(u, v) [ignores OrientationIsReversed - must check manually]
- Intersection.BrepBrep(brep_a, brep_b, tolerance)
- Brep.DuplicateNakedEdgeCurves(get_internal, get_boundary)
- rs.UnitAbsoluteTolerance(tolerance=None, in_model_units=True) - returns doc
  tolerance directly in drawing units, no unit-system conversion needed
- RhinoDoc.BeginUndoRecord(description) -> serial_number (uint), NOT
  zero-arg; RhinoDoc.EndUndoRecord(serial_number) needs that same value
  passed back in, also NOT zero-arg
"""

import rhinoscriptsyntax as rs
import Rhino
from Rhino.Geometry import *
from Rhino.Geometry.Intersect import Intersection

# ============================================================================
# PARAMETERS
# ============================================================================

OFFSET_DISTANCE = 2.0
BISECT_SURFACE_1_INDEX = 0
BISECT_SURFACE_2_INDEX = 1
BISECTOR_DIRECTION = 1  # 1 outward, -1 inward
BISECTOR_OFFSET_DISTANCE = 0.5
T_ARM_PERPENDICULAR_OFFSET = 1.0
T_ARM_PARALLEL_OFFSET = 0.75
BISECTOR_START_POINT_PARAMETER = 0.5

# Defaults for gaps in original spec
BISECTOR_SURFACE_REACH = OFFSET_DISTANCE * 1.5
T_ARM_WIDTH = min(T_ARM_PERPENDICULAR_OFFSET, T_ARM_PARALLEL_OFFSET) * 0.2

# Tuning knobs
BISECTOR_SAMPLE_COUNT = 20
DEBUG = True
STOP_AFTER_STAGE = None  # "offset" | "bisector" | "t_geometry" | "bisector_offset" | "intersect" | "loft"

TOLERANCE = rs.UnitAbsoluteTolerance()

# ============================================================================
# HELPERS
# ============================================================================

def ensure_layer(layer_path):
    """Ensure a layer hierarchy exists, creating parents as needed."""
    parts = layer_path.split("::")
    current = ""
    for part in parts:
        if current:
            current += "::" + part
        else:
            current = part
        if not rs.IsLayer(current):
            rs.AddLayer(current)
    return current

def bake_curve(curve, layer=None):
    """
    Add an in-memory Rhino.Geometry.Curve to the document.
    rs.AddCurve only builds a control-point curve from a list of points -
    it can't take an existing Curve object, which is what every caller
    here has. Objects.AddCurve is the correct way to inject one directly.
    """
    guid = Rhino.RhinoDoc.ActiveDoc.Objects.AddCurve(curve)
    if layer:
        rs.ObjectLayer(guid, layer)
    return guid

def bake_brep(brep, layer=None):
    """Add an in-memory Rhino.Geometry.Brep to the document (rs.AddBrep doesn't exist)."""
    guid = Rhino.RhinoDoc.ActiveDoc.Objects.AddBrep(brep)
    if layer:
        rs.ObjectLayer(guid, layer)
    return guid

def get_surface_from_brep(brep_id):
    """Extract the underlying Surface from a Brep object."""
    obj = rs.coercebrep(brep_id)
    if obj and obj.Surfaces.Count > 0:
        return obj.Surfaces[0]
    return None

def get_brep_face(brep_id, face_index):
    """Extract a specific BrepFace from a Brep."""
    obj = rs.coercebrep(brep_id)
    if obj and face_index < obj.Faces.Count:
        return obj.Faces[face_index]
    return None

def find_seam_curve(surf1_id, surf2_id):
    """
    Find shared seam between two offset surfaces.
    Try naked-edge match first; fall back to BrepBrep intersection.
    Returns a Curve or None.
    """
    brep1 = rs.coercebrep(surf1_id)
    brep2 = rs.coercebrep(surf2_id)

    if not brep1 or not brep2:
        return None

    # Try naked edges first
    naked1 = brep1.DuplicateNakedEdgeCurves(True, True)
    naked2 = brep2.DuplicateNakedEdgeCurves(True, True)

    if naked1 and naked2:
        for edge1 in naked1:
            for edge2 in naked2:
                # Check endpoint distance
                dist = edge1.PointAtStart.DistanceTo(edge2.PointAtStart)
                dist += edge1.PointAtEnd.DistanceTo(edge2.PointAtEnd)
                if dist < TOLERANCE * 2:
                    if DEBUG:
                        print("Found seam via naked edges, distance=%.3f" % dist)
                    return edge1

    # Fall back to BrepBrep intersection
    curves = Intersection.BrepBrep(brep1, brep2, TOLERANCE)
    if curves and len(curves) > 0:
        if DEBUG:
            print("Found seam via BrepBrep intersection, %d curves" % len(curves))
        # Return the longest curve (most likely the actual seam)
        return max(curves, key=lambda c: c.GetLength())

    return None

def compute_bisector_surface(seam_curve, surf1_id, surf2_id):
    """
    Compute bisector surface between two offset surfaces.
    Sample seam, average normals, project along bisecting direction, loft.
    """
    if not seam_curve:
        return None

    brep1 = rs.coercebrep(surf1_id)
    brep2 = rs.coercebrep(surf2_id)

    if not brep1 or not brep2:
        return None

    # Extract first face from each brep
    face1 = brep1.Faces[0] if brep1.Faces.Count > 0 else None
    face2 = brep2.Faces[0] if brep2.Faces.Count > 0 else None

    if not face1 or not face2:
        return None

    # Sample the seam curve
    seam_length = seam_curve.GetLength()
    sample_points = []
    normals_a = []
    normals_b = []

    for i in range(BISECTOR_SAMPLE_COUNT + 1):
        t = i / float(BISECTOR_SAMPLE_COUNT)
        param = seam_curve.Domain.T0 + t * (seam_curve.Domain.T1 - seam_curve.Domain.T0)
        sample_pt = seam_curve.PointAt(param)
        sample_points.append(sample_pt)

        # Get normals from each surface
        try:
            closest_pt1 = face1.ClosestPoint(sample_pt)
            u1, v1 = closest_pt1.Item2, closest_pt1.Item3
            normal1 = face1.NormalAt(u1, v1)

            # Check and flip if orientation is reversed
            if face1.OrientationIsReversed:
                normal1.Reverse()
            normals_a.append(normal1)

            closest_pt2 = face2.ClosestPoint(sample_pt)
            u2, v2 = closest_pt2.Item2, closest_pt2.Item3
            normal2 = face2.NormalAt(u2, v2)

            if face2.OrientationIsReversed:
                normal2.Reverse()
            normals_b.append(normal2)
        except:
            if DEBUG:
                print("Warning: could not get normal at sample %d" % i)
            return None

    # Compute bisecting direction at each sample
    reach_points = []
    for i, sample_pt in enumerate(sample_points):
        if i < len(normals_a) and i < len(normals_b):
            bisect_vec = normals_a[i] + normals_b[i]
            bisect_vec.Unitize()

            if BISECTOR_DIRECTION == -1:
                bisect_vec.Reverse()

            reach_pt = sample_pt + (bisect_vec * BISECTOR_SURFACE_REACH)
            reach_points.append(reach_pt)

    if len(sample_points) < 2 or len(reach_points) < 2:
        return None

    # Create reach curve by interpolating reach points
    reach_curve = Curve.CreateInterpolatedCurve(reach_points, 3)

    # Bake seam and reach curves to debug layer
    seam_layer = ensure_layer("ShellBisector::02_BisectorSeam")
    seam_id = bake_curve(seam_curve, layer=seam_layer)
    reach_id = bake_curve(reach_curve, layer=seam_layer)

    if DEBUG:
        print("Seam curve length: %.3f" % seam_curve.GetLength())
        print("Reach curve length: %.3f" % reach_curve.GetLength())
        print("Successful samples: %d / %d" % (len(reach_points), BISECTOR_SAMPLE_COUNT + 1))

    # Loft seam + reach curves
    bisector_layer = ensure_layer("ShellBisector::03_BisectorSurface")
    bisector_ids = [seam_id, reach_id]
    loft_srf_id = rs.AddLoftSrf(bisector_ids)

    if loft_srf_id:
        rs.ObjectLayer(loft_srf_id, bisector_layer)
        return loft_srf_id

    return None

def build_t_geometry(bisector_id):
    """
    Build T-shaped geometry from bisector surface.
    Construct 4 long edges directly via local frame at start point.
    """
    if not bisector_id:
        return None, None

    # Get bisector surface
    bisector_srf = get_surface_from_brep(bisector_id)
    if not bisector_srf:
        return None, None

    # Get local frame at start point
    try:
        u_param = bisector_srf.Domain.U.T0 + BISECTOR_START_POINT_PARAMETER * (bisector_srf.Domain.U.T1 - bisector_srf.Domain.U.T0)
        v_param = bisector_srf.Domain.V.T0 + 0.5 * (bisector_srf.Domain.V.T1 - bisector_srf.Domain.V.T0)

        frame_pt = bisector_srf.PointAt(u_param, v_param)
        perp_dir = bisector_srf.NormalAt(u_param, v_param)

        # Get seam tangent direction (along U)
        deriv = bisector_srf.Evaluate(u_param, v_param, 1, 1)
        tang_dir = deriv[1]
        tang_dir.Unitize()

        # Re-orthogonalize if needed
        dot = perp_dir.X * tang_dir.X + perp_dir.Y * tang_dir.Y + perp_dir.Z * tang_dir.Z
        if abs(dot) > 0.1:
            if DEBUG:
                print("Warning: perpendicular and tangent not orthogonal, dot=%.3f" % dot)

        width_dir = Vector3d.CrossProduct(perp_dir, tang_dir)
        width_dir.Unitize()

    except:
        if DEBUG:
            print("Could not extract local frame from bisector")
        return None, None

    # Build 4 long edges as explicit line pairs
    half_width = T_ARM_WIDTH / 2.0

    # Perpendicular arm (extends along perp_dir)
    perp_start_1 = frame_pt + (width_dir * half_width)
    perp_end_1 = perp_start_1 + (perp_dir * T_ARM_PERPENDICULAR_OFFSET)
    perp_start_2 = frame_pt - (width_dir * half_width)
    perp_end_2 = perp_start_2 + (perp_dir * T_ARM_PERPENDICULAR_OFFSET)

    perp_edge_1 = Line(perp_start_1, perp_end_1).ToNurbsCurve()
    perp_edge_2 = Line(perp_start_2, perp_end_2).ToNurbsCurve()

    # Parallel arm (extends along tang_dir)
    para_start_1 = frame_pt + (width_dir * half_width)
    para_end_1 = para_start_1 + (tang_dir * T_ARM_PARALLEL_OFFSET)
    para_start_2 = frame_pt - (width_dir * half_width)
    para_end_2 = para_start_2 + (tang_dir * T_ARM_PARALLEL_OFFSET)

    para_edge_1 = Line(para_start_1, para_end_1).ToNurbsCurve()
    para_edge_2 = Line(para_start_2, para_end_2).ToNurbsCurve()

    # Loft each pair into a strip
    t_layer = ensure_layer("ShellBisector::04_TGeometry")

    # Add edges as curve IDs for lofting
    perp_edge_1_id = bake_curve(perp_edge_1, layer=t_layer)
    perp_edge_2_id = bake_curve(perp_edge_2, layer=t_layer)
    para_edge_1_id = bake_curve(para_edge_1, layer=t_layer)
    para_edge_2_id = bake_curve(para_edge_2, layer=t_layer)

    # Loft perpendicular arm
    perp_strip_id = rs.AddLoftSrf([perp_edge_1_id, perp_edge_2_id])
    if perp_strip_id:
        rs.ObjectLayer(perp_strip_id, t_layer)

    # Loft parallel arm
    para_strip_id = rs.AddLoftSrf([para_edge_1_id, para_edge_2_id])
    if para_strip_id:
        rs.ObjectLayer(para_strip_id, t_layer)

    # Try to join into one T-Brep (non-fatal if join doesn't fully merge)
    if perp_strip_id and para_strip_id:
        try:
            perp_brep = rs.coercebrep(perp_strip_id)
            para_brep = rs.coercebrep(para_strip_id)
            joined = Brep.JoinBreps([perp_brep, para_brep], TOLERANCE)
            if joined and len(joined) > 0:
                rs.DeleteObject(perp_strip_id)
                rs.DeleteObject(para_strip_id)
                t_brep_id = bake_brep(joined[0], layer=t_layer)
            else:
                t_brep_id = None
        except:
            t_brep_id = None
    else:
        t_brep_id = None

    # Return T-Brep and the 4 long edges for later use
    edges = [perp_edge_1, perp_edge_2, para_edge_1, para_edge_2]

    if DEBUG:
        print("T-geometry built. T-Brep: %s" % ("yes" if t_brep_id else "no"))

    return t_brep_id, edges

def extract_t_edges(edges):
    """Extract/return the 4 long edges (already constructed)."""
    return edges if edges and len(edges) == 4 else []

def offset_bisector(bisector_id):
    """Offset bisector surface both directions (thin sandwich)."""
    if not bisector_id:
        return None, None

    offset_layer = ensure_layer("ShellBisector::05_BisectorOffsets")

    # Offset outward
    offset_out_id = rs.OffsetSurface(bisector_id, BISECTOR_OFFSET_DISTANCE, create_solid=False)
    if offset_out_id:
        rs.ObjectLayer(offset_out_id, offset_layer)

    # Offset inward
    offset_in_id = rs.OffsetSurface(bisector_id, -BISECTOR_OFFSET_DISTANCE, create_solid=False)
    if offset_in_id:
        rs.ObjectLayer(offset_in_id, offset_layer)

    if DEBUG:
        print("Bisector offset: outward=%s, inward=%s" % (
            "yes" if offset_out_id else "no",
            "yes" if offset_in_id else "no"
        ))

    return offset_out_id, offset_in_id

def intersect_surfaces(offset_out_id, offset_in_id, original_shell_id):
    """
    Intersect bisector offsets against original shell (all surfaces).
    Return collected intersection curves.
    """
    intersect_layer = ensure_layer("ShellBisector::06_IntersectionCurves")
    all_curves = []

    # Explode original shell
    original_faces = rs.ExplodePolysurfaces(original_shell_id)
    if not original_faces:
        original_faces = [original_shell_id]

    if DEBUG:
        print("Testing %d original faces" % len(original_faces))

    for offset_id, offset_name in [(offset_out_id, "outward"), (offset_in_id, "inward")]:
        if not offset_id:
            continue

        offset_brep = rs.coercebrep(offset_id)
        if not offset_brep:
            continue

        offset_curves = []

        for face_id in original_faces:
            face_brep = rs.coercebrep(face_id)
            if not face_brep:
                continue

            try:
                curves = Intersection.BrepBrep(offset_brep, face_brep, TOLERANCE)
                if curves:
                    offset_curves.extend(curves)
            except:
                pass

        if not offset_curves:
            if DEBUG:
                print("Warning: no intersection curves for %s offset" % offset_name)

        # Bake all curves
        for curve in offset_curves:
            curve_id = bake_curve(curve, layer=intersect_layer)
            all_curves.append(curve_id)

        if DEBUG:
            print("Intersection curves (%s offset): %d" % (offset_name, len(offset_curves)))

    return all_curves

def loft_surfaces(t_edges, intersection_curves):
    """
    Loft connecting surfaces between intersection curves and T long-edges.
    Sort by projection, anti-twist, final loft.
    """
    if not t_edges or not intersection_curves:
        return None

    loft_layer = ensure_layer("ShellBisector::07_FinalLoft")

    # Combine edges and curves
    all_curves = []

    # Add T edges
    for edge in t_edges:
        edge_id = bake_curve(edge)
        all_curves.append(edge_id)

    # Add intersection curves
    all_curves.extend(intersection_curves)

    if len(all_curves) < 2:
        if DEBUG:
            print("Not enough curves for loft (%d)" % len(all_curves))
        return None

    # Sort by projection onto seam tangent (simplified: use first curve as reference)
    # This is a placeholder; full implementation would project midpoints

    # Anti-twist: reverse curves if start is closer to previous end
    for i in range(1, len(all_curves)):
        prev_curve = rs.coercecurve(all_curves[i - 1])
        curr_curve = rs.coercecurve(all_curves[i])

        if prev_curve and curr_curve:
            dist_start_to_start = prev_curve.PointAtStart.DistanceTo(curr_curve.PointAtStart)
            dist_start_to_end = prev_curve.PointAtStart.DistanceTo(curr_curve.PointAtEnd)

            if dist_start_to_end < dist_start_to_start:
                rs.ReverseCurve(all_curves[i])

    # Final loft
    loft_id = rs.AddLoftSrf(all_curves)

    if loft_id:
        rs.ObjectLayer(loft_id, loft_layer)
        if DEBUG:
            print("Final loft created, %d input curves" % len(all_curves))
        return loft_id

    if DEBUG:
        print("Final loft failed")
    return None

# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Main workflow with undo wrapping. Cleanup (EndUndoRecord, EnableRedraw)
    lives in `finally` so it runs exactly once no matter which return/
    exception path is taken - every early-return branch below can just
    `return` and trust it happens.
    """

    doc = Rhino.RhinoDoc.ActiveDoc
    undo_serial = doc.BeginUndoRecord("Shell Bisector T-Surface")

    try:
        # Get input shell
        shell_id = rs.GetObject("Select shell polysurface", rs.filter.polysurface)
        if not shell_id:
            print("No shell selected.")
            return

        rs.EnableRedraw(False)

        # Stage 1: Offset just the two selected panels, not the whole shell.
        # Offsetting an entire multi-panel hull as one polysurface is fragile
        # (self-intersection at concave/tight regions on real geometry) and
        # unnecessary - everything downstream only ever uses these two
        # panels plus the original (unoffset) shell.
        offset_layer = ensure_layer("ShellBisector::01_OffsetPanels")

        original_faces = rs.ExplodePolysurfaces(shell_id)
        if not original_faces or len(original_faces) < 2:
            print("Shell has fewer than 2 faces")
            return

        surf1_orig_id = original_faces[BISECT_SURFACE_1_INDEX] if BISECT_SURFACE_1_INDEX < len(original_faces) else None
        surf2_orig_id = original_faces[BISECT_SURFACE_2_INDEX] if BISECT_SURFACE_2_INDEX < len(original_faces) else None

        if not surf1_orig_id or not surf2_orig_id:
            print("Invalid surface indices")
            return

        surf1_id = rs.OffsetSurface(surf1_orig_id, OFFSET_DISTANCE, create_solid=False)
        surf2_id = rs.OffsetSurface(surf2_orig_id, OFFSET_DISTANCE, create_solid=False)

        if not surf1_id or not surf2_id:
            print("Failed to offset selected panels (try a smaller OFFSET_DISTANCE)")
            return

        rs.ObjectLayer(surf1_id, offset_layer)
        rs.ObjectLayer(surf2_id, offset_layer)

        if DEBUG:
            print("=== Stage 1: Offset ===")
            print("Offset panels created: yes")

        if STOP_AFTER_STAGE == "offset":
            return

        # Stage 2: Compute bisector surface
        if DEBUG:
            print("=== Stage 2: Bisector Surface ===")

        seam_curve = find_seam_curve(surf1_id, surf2_id)
        bisector_id = compute_bisector_surface(seam_curve, surf1_id, surf2_id)

        if not bisector_id:
            print("Failed to create bisector surface")
            return

        if STOP_AFTER_STAGE == "bisector":
            return

        # Stage 3: Build T geometry
        if DEBUG:
            print("=== Stage 3: T Geometry ===")

        t_brep_id, t_edges = build_t_geometry(bisector_id)

        if STOP_AFTER_STAGE == "t_geometry":
            return

        # Stage 4: Offset bisector
        if DEBUG:
            print("=== Stage 4: Bisector Offset ===")

        offset_out_id, offset_in_id = offset_bisector(bisector_id)

        if not offset_out_id or not offset_in_id:
            print("Failed to offset bisector")
            return

        if STOP_AFTER_STAGE == "bisector_offset":
            return

        # Stage 5: Intersect
        if DEBUG:
            print("=== Stage 5: Intersection ===")

        intersection_curves = intersect_surfaces(offset_out_id, offset_in_id, shell_id)

        if not intersection_curves:
            print("No intersection curves found (check BISECTOR_SURFACE_REACH)")
            return

        if STOP_AFTER_STAGE == "intersect":
            return

        # Stage 6: Loft
        if DEBUG:
            print("=== Stage 6: Final Loft ===")

        loft_id = loft_surfaces(t_edges, intersection_curves)

        if not loft_id:
            print("Final loft failed")
            return

        # Create group for real outputs
        group_name = "ShellBisector_Output"
        rs.AddGroup(group_name)
        for obj_id in [bisector_id, offset_out_id, offset_in_id, loft_id]:
            if obj_id:
                rs.AddObjectToGroup(obj_id, group_name)
        if t_brep_id:
            rs.AddObjectToGroup(t_brep_id, group_name)

        if DEBUG:
            print("=== Complete ===")
            print("Outputs grouped in '%s'" % group_name)

    except Exception as e:
        print("Error: %s" % str(e))
        import traceback
        traceback.print_exc()

    finally:
        doc.EndUndoRecord(undo_serial)
        rs.EnableRedraw(True)

if __name__ == "__main__":
    main()
