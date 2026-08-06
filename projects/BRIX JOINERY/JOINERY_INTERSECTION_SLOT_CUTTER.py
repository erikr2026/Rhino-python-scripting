# -*- coding: utf-8 -*-

"""
Rhino Python Script (Rhino 8 & 9)
BRIX JOINERY - Intersection Slot Cutter.

Cuts notch/dado slots into a first set of zero-thickness surfaces ("1st
set"), sized to receive a second set of zero-thickness "cutting" surfaces
("2nd set") that pass through them. Standard BRIX flat-panel joinery: each
1st-set panel gets a slot that opens at its nearest boundary edge and
terminates inside the panel with a semicircular rounded end at the point
where the 2nd-set panel actually crosses it. If a 2nd-set panel passes
fully through a 1st-set panel (enters and exits through two boundary
edges), a straight full-width channel is cut instead - no semicircle.

Both sets may be single surfaces OR polysurfaces (multi-face Breps) - each
S1/S2 pair is intersected as whole Breps (Intersection.BrepBrep), and each
resulting intersection curve is matched back to the specific S1 face it
lies on (Brep.ClosestPoint) so the slot outline is built in that face's own
plane. The final cut is a single whole-Brep split (Brep.Split(curves,
tolerance)) across all of S1's faces at once, not a per-face split - this
sidesteps face-index reshuffling when a polysurface needs more than one
face cut.

Workflow: select 1st-set surfaces, then 2nd-set (cutting) surfaces, then
enter the 2nd-set material thickness. Slot width = thickness + 1/16"
oversize (converted to the document's model unit system, not hardcoded
assuming inches).

Engine: Python 3 (CPython, via ScriptEditor / F5) or IronPython 2
(RunPythonScript) - this script uses no syntax specific to either engine
and no non-ASCII source bytes, so it runs unmodified under both. Written
for Rhino 8/9's CPython bridge; every RhinoCommon call below (in
particular the out/ref-parameter tuple returns from
Intersection.BrepBrep, Brep.ClosestPoint, Curve.JoinCurves, and
Rhino.Input.RhinoGet.GetNumber, plus Brep.Split's array-of-pieces return
and Curve.Contains returning a PointContainment enum rather than a bool)
was checked against a live pull of developer.rhino3d.com's RhinoCommon
API JSON data source this session - not against a running Rhino instance,
since no Rhino install is available in this authoring environment.

*** NOT TESTED AGAINST LIVE RHINO GEOMETRY. ***
This script has only been checked for Python syntax validity and API
signatures against live docs - it has never been run inside Rhino. See
this project's CHANGELOG.md for the specific parts most likely to need
real-world correction: the Brep.Split() / piece-removal pass (step 7 of
the algorithm), the Brep.ClosestPoint face-matching for multi-face
polysurfaces, and the ray-cast boundary-crossing search used when neither
end of an intersection curve starts near a naked edge.
"""

import Rhino
import Rhino.Geometry as rg
from Rhino.Geometry.Intersect import Intersection
import rhinoscriptsyntax as rs
import scriptcontext as sc


# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# 1/16" oversize on slot width, converted from inches to the document's
# actual model unit system (never assume the document is in inches).
OVERSIZE_INCHES = 1.0 / 16.0

# Default 2nd-set material thickness offered in the number prompt (inches
# worth of "quarter inch ply" is a common BRIX default; converted below).
DEFAULT_THICKNESS_INCHES = 0.25

# How many multiples of the document's absolute tolerance an intersection
# curve endpoint must be within to be treated as "already on the boundary"
# rather than needing a ray-cast extension. Not verified against real
# fabrication geometry - a development placeholder like the ones flagged
# in this repo's other BRIX scripts.
BOUNDARY_SNAP_MULTIPLE = 25.0

# How many multiples of tolerance to overshoot the true boundary point by,
# so the closed slot outline reliably removes material all the way to the
# panel edge despite floating-point mismatch at the boundary.
EDGE_OVERSHOOT_MULTIPLE = 10.0


def prompt_for_surfaces(prompt_text, exclude_ids=None):
    """Prompt for one or more whole Surface/Brep objects (single-face or
    polysurface - either is fine). Returns a list of (Guid, RhinoObject)
    tuples, or an empty list if the user cancelled or picked nothing
    usable."""

    exclude_ids = exclude_ids or set()

    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt(prompt_text)
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Surface | Rhino.DocObjects.ObjectType.Brep
    go.SubObjectSelect = False
    go.EnablePreSelect(True, True)
    go.GetMultiple(1, 0)

    if go.CommandResult() != Rhino.Commands.Result.Success:
        print("Selection cancelled.")
        return []

    obj_refs = go.Objects()
    if not obj_refs:
        print("No surfaces selected.")
        return []

    picked = []
    seen = set()
    skipped_excluded = 0
    for ref in obj_refs:
        rh_obj = ref.Object()
        if not rh_obj:
            continue
        obj_id = rh_obj.Id
        if obj_id in seen:
            continue
        seen.add(obj_id)
        if obj_id in exclude_ids:
            skipped_excluded += 1
            continue
        picked.append((obj_id, rh_obj))

    if skipped_excluded:
        print("Skipped {0} object(s) already used in the 1st-set selection.".format(skipped_excluded))

    sc.doc.Objects.UnselectAll()
    return picked


def geometry_to_brep(rh_obj):
    """Convert a selected RhinoObject's geometry to a Brep (single-face or
    polysurface, either is fine), or return None if it isn't a
    zero-thickness Surface/Brep."""

    geom = rh_obj.Geometry
    if isinstance(geom, rg.Brep):
        return geom.DuplicateBrep()
    if isinstance(geom, rg.Surface):
        return geom.ToBrep()
    return None


def get_boundary_proximity(point, naked_curves):
    """Return (min_distance, closest_point_on_boundary) of `point` against
    the naked boundary curves, or (None, None) if there are none."""

    best_dist = None
    best_pt = None
    for nc in naked_curves:
        ok, t = nc.ClosestPoint(point)
        if not ok:
            continue
        cp = nc.PointAt(t)
        d = point.DistanceTo(cp)
        if best_dist is None or d < best_dist:
            best_dist = d
            best_pt = cp
    return best_dist, best_pt


def find_boundary_crossing(near_point, far_point, naked_curves, search_length, tolerance):
    """Cast a ray from far_point through near_point and beyond by
    search_length; return the boundary-curve crossing point nearest to
    near_point, or None if no crossing is found.

    This is the least-verified part of the algorithm's geometry - see the
    module docstring / CHANGELOG for the flag."""

    direction = near_point - far_point
    if direction.Length < tolerance:
        return None
    direction.Unitize()

    ray_end = near_point + direction * search_length
    line_curve = rg.LineCurve(far_point, ray_end)

    best_pt = None
    best_dist = None
    for nc in naked_curves:
        events = Intersection.CurveCurve(line_curve, nc, tolerance, tolerance)
        if events is None or events.Count == 0:
            continue
        for ev in events:
            if not ev.IsPoint:
                continue
            pt = ev.PointA
            d = pt.DistanceTo(near_point)
            if best_dist is None or d < best_dist:
                best_dist = d
                best_pt = pt

    return best_pt


def build_capped_outline(open_pt, interior_pt, plane_normal, half_width, edge_overshoot, join_tolerance):
    """Build the closed slot outline for a slot that opens at `open_pt` on
    the boundary and terminates inside the panel at `interior_pt` with a
    semicircular cap. Returns a closed Curve, or None on failure."""

    forward = interior_pt - open_pt
    if forward.Length < join_tolerance:
        return None
    forward.Unitize()

    perp = rg.Vector3d.CrossProduct(plane_normal, forward)
    if perp.Length < 1e-9:
        return None
    perp.Unitize()

    ext_open = open_pt - forward * edge_overshoot

    side1_start = ext_open + perp * half_width
    side1_end = interior_pt + perp * half_width
    side2_start = ext_open - perp * half_width
    side2_end = interior_pt - perp * half_width

    try:
        seg1 = rg.LineCurve(side1_start, side1_end)
        cap_arc = rg.Arc(side1_end, forward, side2_end)
        seg2 = rg.ArcCurve(cap_arc)
        seg3 = rg.LineCurve(side2_end, side2_start)
        seg4 = rg.LineCurve(side2_start, side1_start)
    except Exception:
        return None

    joined = rg.Curve.JoinCurves([seg1, seg2, seg3, seg4], join_tolerance)
    if not joined or len(joined) != 1 or not joined[0].IsClosed:
        return None
    return joined[0]


def build_full_channel_outline(open_pt_a, open_pt_b, plane_normal, half_width, edge_overshoot, join_tolerance):
    """Build the closed slot outline for a slot where the 2nd-set surface
    passes fully through the 1st-set panel (both ends open on the
    boundary) - a straight full-width channel, no semicircular cap."""

    forward = open_pt_b - open_pt_a
    if forward.Length < join_tolerance:
        return None
    forward.Unitize()

    perp = rg.Vector3d.CrossProduct(plane_normal, forward)
    if perp.Length < 1e-9:
        return None
    perp.Unitize()

    ext_a = open_pt_a - forward * edge_overshoot
    ext_b = open_pt_b + forward * edge_overshoot

    side1_a = ext_a + perp * half_width
    side1_b = ext_b + perp * half_width
    side2_a = ext_a - perp * half_width
    side2_b = ext_b - perp * half_width

    try:
        seg1 = rg.LineCurve(side1_a, side1_b)
        seg2 = rg.LineCurve(side1_b, side2_b)
        seg3 = rg.LineCurve(side2_b, side2_a)
        seg4 = rg.LineCurve(side2_a, side1_a)
    except Exception:
        return None

    joined = rg.Curve.JoinCurves([seg1, seg2, seg3, seg4], join_tolerance)
    if not joined or len(joined) != 1 or not joined[0].IsClosed:
        return None
    return joined[0]


def face_and_plane_for_curve(brep, curve, tolerance, label):
    """Find which face of `brep` an intersection curve actually lies on
    (by its midpoint) and that face's plane. Returns (face_index, Plane),
    or (None, None) with a printed warning if the face can't be matched or
    isn't planar.

    Needed because a polysurface's faces can have different planes - the
    slot outline for a given intersection curve has to be built in the
    plane of the specific face it crosses, not some single plane for the
    whole S1 object."""

    mid_pt = curve.PointAtNormalizedLength(0.5)
    ok, closest_pt, ci, s, t, normal = brep.ClosestPoint(mid_pt, 0.0)
    if not ok or ci.ComponentIndexType != rg.ComponentIndexType.BrepFace:
        print("  Skipped an intersection on {0} - could not match it to a single planar face.".format(label))
        return None, None

    face = brep.Faces[ci.Index]
    plane_ok, plane = face.TryGetPlane(tolerance)
    if not plane_ok:
        print("  Skipped an intersection on {0} - the face it crosses is not planar.".format(label))
        return None, None

    return ci.Index, plane


def outlines_for_intersection_curve(curve, naked_curves, snap_tol, edge_overshoot,
                                     plane_normal, half_width, join_tolerance,
                                     search_length, tolerance, label):
    """Classify one S1/S2 intersection curve's endpoints against S1's
    boundary and build the resulting slot outline. Returns a Curve, or
    None with a printed warning if it couldn't be built."""

    if curve.GetLength() < tolerance:
        print("  Skipped a degenerate (near-zero-length) intersection on {0}.".format(label))
        return None

    p_start = curve.PointAtStart
    p_end = curve.PointAtEnd

    dist_start, proj_start = get_boundary_proximity(p_start, naked_curves)
    dist_end, proj_end = get_boundary_proximity(p_end, naked_curves)

    start_near = dist_start is not None and dist_start <= snap_tol
    end_near = dist_end is not None and dist_end <= snap_tol

    if start_near and end_near:
        # 2nd-set surface passes fully through S1 - full-width channel.
        return build_full_channel_outline(proj_start, proj_end, plane_normal,
                                           half_width, edge_overshoot, join_tolerance)

    if start_near and not end_near:
        return build_capped_outline(proj_start, p_end, plane_normal,
                                     half_width, edge_overshoot, join_tolerance)

    if end_near and not start_near:
        return build_capped_outline(proj_end, p_start, plane_normal,
                                     half_width, edge_overshoot, join_tolerance)

    # Neither endpoint is near a boundary - extend from whichever end is
    # closer to one, ray-casting out to find the true boundary crossing.
    if dist_start is None and dist_end is None:
        print("  Skipped an intersection on {0} - S1 has no boundary edges to reference.".format(label))
        return None

    if dist_start is None:
        near_pt, far_pt = p_end, p_start
    elif dist_end is None:
        near_pt, far_pt = p_start, p_end
    elif dist_start <= dist_end:
        near_pt, far_pt = p_start, p_end
    else:
        near_pt, far_pt = p_end, p_start

    open_pt = find_boundary_crossing(near_pt, far_pt, naked_curves, search_length, tolerance)
    if open_pt is None:
        print("  Skipped an intersection on {0} - could not ray-cast to a boundary edge.".format(label))
        return None

    return build_capped_outline(open_pt, far_pt, plane_normal, half_width, edge_overshoot, join_tolerance)


def main():
    """Select 1st-set surfaces, then 2nd-set cutting surfaces, prompt for
    2nd-set thickness, and cut intersection slots into every 1st-set
    surface in a single undo step."""

    tolerance = sc.doc.ModelAbsoluteTolerance
    if tolerance <= 0:
        print("Document absolute tolerance is not set to a positive value. Aborting.")
        return

    snap_tol = tolerance * BOUNDARY_SNAP_MULTIPLE
    edge_overshoot = tolerance * EDGE_OVERSHOOT_MULTIPLE

    set1_picked = prompt_for_surfaces("Select 1st-set surfaces (get cutouts)")
    if not set1_picked:
        return

    set1_ids = set(obj_id for obj_id, _ in set1_picked)

    set2_picked = prompt_for_surfaces("Select 2nd-set cutting surfaces", exclude_ids=set1_ids)
    if not set2_picked:
        return

    unit_scale = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Inches, sc.doc.ModelUnitSystem)
    default_thickness = DEFAULT_THICKNESS_INCHES * unit_scale

    thickness = default_thickness
    rc, thickness = Rhino.Input.RhinoGet.GetNumber(
        "2nd-set material thickness", False, thickness, 1e-6, 1e6)
    if rc != Rhino.Commands.Result.Success:
        print("Thickness entry cancelled.")
        return
    if thickness <= 0:
        print("Thickness must be a positive value. Aborting.")
        return

    oversize = OVERSIZE_INCHES * unit_scale
    slot_width = thickness + oversize
    half_width = slot_width / 2.0

    # Build Brep working copies up front, keyed by object id. Either
    # single-face or polysurface Breps are accepted for both sets.
    set1_breps = {}
    for obj_id, rh_obj in set1_picked:
        brep = geometry_to_brep(rh_obj)
        if brep is None:
            print("Skipped '{0}' - not a Surface or Brep object.".format(rh_obj.Name or str(obj_id)))
            continue
        set1_breps[obj_id] = (rh_obj, brep)

    set2_breps = {}
    for obj_id, rh_obj in set2_picked:
        brep = geometry_to_brep(rh_obj)
        if brep is None:
            print("Skipped '{0}' - not a Surface or Brep object.".format(rh_obj.Name or str(obj_id)))
            continue
        set2_breps[obj_id] = (rh_obj, brep)

    if not set1_breps:
        print("No usable 1st-set surfaces (Surface or Brep objects). Aborting.")
        return
    if not set2_breps:
        print("No usable 2nd-set surfaces (Surface or Brep objects). Aborting.")
        return

    undo_record = sc.doc.BeginUndoRecord("BRIX Joinery - Cut Intersection Slots")
    rs.EnableRedraw(False)

    total_slots = 0
    surfaces_modified = 0

    try:
        for obj_id, (rh_obj, brep1) in set1_breps.items():
            label = rh_obj.Name or str(obj_id)

            naked_curves = brep1.DuplicateNakedEdgeCurves(True, False)
            if not naked_curves:
                print("Skipped '{0}' - no boundary (naked) edges found.".format(label))
                continue

            search_length = brep1.GetBoundingBox(True).Diagonal.Length * 2.0
            if search_length < tolerance:
                search_length = 1.0

            # (outline curve, plane it was built in) pairs, across every
            # face of S1 and every S2 it intersects.
            all_outlines = []

            for obj_id2, (rh_obj2, brep2) in set2_breps.items():
                success, curves, points = Intersection.BrepBrep(brep1, brep2, tolerance)
                if not success or not curves:
                    continue

                for curve in curves:
                    face_idx, plane = face_and_plane_for_curve(brep1, curve, tolerance, label)
                    if plane is None:
                        continue

                    outline = outlines_for_intersection_curve(
                        curve, naked_curves, snap_tol, edge_overshoot,
                        plane.Normal, half_width, tolerance, search_length,
                        tolerance, label)
                    if outline is not None:
                        all_outlines.append((outline, plane))

            if not all_outlines:
                continue

            outline_curves = [pair[0] for pair in all_outlines]
            pieces = brep1.Split(outline_curves, tolerance)
            if not pieces:
                print("Skipped '{0}' - Split() failed to produce a result.".format(label))
                continue

            kept_pieces = []
            for piece in pieces:
                amp = rg.AreaMassProperties.Compute(piece)
                if amp is None:
                    kept_pieces.append(piece)
                    continue
                centroid = amp.Centroid

                is_slot_piece = False
                for outline, plane in all_outlines:
                    if outline.Contains(centroid, plane, tolerance) == rg.PointContainment.Inside:
                        is_slot_piece = True
                        break

                if not is_slot_piece:
                    kept_pieces.append(piece)

            if not kept_pieces:
                print("Skipped replacing '{0}' - slot removal left no material.".format(label))
                continue

            if len(kept_pieces) == 1:
                result_brep = kept_pieces[0]
            else:
                joined = rg.Brep.JoinBreps(kept_pieces, tolerance)
                if not joined:
                    print("Skipped replacing '{0}' - could not rejoin remaining material pieces.".format(label))
                    continue
                result_brep = joined[0]
                if len(joined) > 1:
                    print("  Warning: slots on '{0}' split it into {1} disconnected pieces; keeping only the first.".format(
                        label, len(joined)))

            if sc.doc.Objects.Replace(obj_id, result_brep):
                surfaces_modified += 1
                total_slots += len(all_outlines)
            else:
                print("Failed to replace '{0}' in the document.".format(label))

    except Exception as ex:
        print("An error occurred during execution: {0}".format(str(ex)))

    finally:
        sc.doc.Objects.UnselectAll()
        sc.doc.EndUndoRecord(undo_record)
        rs.EnableRedraw(True)
        sc.doc.Views.Redraw()

    print("Cut {0} slot(s) across {1} surface(s).".format(total_slots, surfaces_modified))


if __name__ == "__main__":
    main()
