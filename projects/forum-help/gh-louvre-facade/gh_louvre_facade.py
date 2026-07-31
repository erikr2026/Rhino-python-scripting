"""
Louvre facade - Stage 2 helper: random sphere-void subtraction + fabrication tiling.

Forum thread: https://discourse.mcneel.com/t/custom-louvre-facades-script/221044
(posted 2026-07-21, unresolved at time of writing).

LIMITATION - READ THIS FIRST:
I (the assistant that wrote this) could not see the poster's reference image
("ref b") or their Stage 1 .gh file. WebFetch on the thread only returned a
text summary, not image content. Everything below about "matching the
pattern" is therefore a generic, reasonable-default approach to "randomly
placed voids, evenly enough distributed to look intentional" - NOT a
verified match to their specific target look. Treat sphere_radius_min/max,
target_count, and min_spacing as starting points to tune by eye against
their actual reference, not values derived from it.

ENGINE / CONTEXT:
Written for a Grasshopper Python 3 script component (GH1 "GhPython Script"
or GH2 "Script" component set to Python 3). It expects to run INSIDE
Grasshopper, where `louvre_breps`, `x_count`, `y_count`, `sphere_radius_min`,
`sphere_radius_max`, `min_spacing`, `random_seed`, `tile_max_x`,
`tile_max_y`, `tile_max_z`, and `run_boolean` arrive as component inputs
(declared as GH input params, not globals you set yourself). It will NOT
run standalone via RunPythonScript or ScriptEditor as-is - there is no GH
canvas here to supply those inputs. If you want a standalone version, say so
and I'll rewrite the input-gathering with rs.GetReal/rs.GetInteger prompts.

INPUTS (declare these as component inputs, matching types below):
    louvre_breps      : list[Brep]   - the individual louvre solids from Stage 1
    x_count           : int          - jittered-grid columns per louvre (try 6-12)
    y_count           : int          - jittered-grid rows per louvre (try 3-6)
    sphere_radius_min : float        - min void sphere radius (model units)
    sphere_radius_max : float        - max void sphere radius (model units)
    min_spacing       : float        - minimum center-to-center distance kept
                                        between accepted sphere centers (Poisson-
                                        disc-style rejection on top of the jittered
                                        grid, so voids don't overlap/cluster)
    random_seed       : int          - fixed seed so results are reproducible
    tile_max_x        : float        - max panel size in X for fabrication split
    tile_max_y        : float        - max panel size in Y for fabrication split
    tile_max_z        : float        - max panel size in Z for fabrication split
                                        (set huge, e.g. 1e6, to not split that axis)
    run_boolean       : bool         - gate the (slow) boolean step behind a toggle,
                                        since Boolean ops on many breps can be
                                        heavy/flaky - iterate on placement first
                                        with this OFF, then turn it ON.

OUTPUTS:
    voided_breps  : list[Brep]  - louvres with spheres subtracted (or the
                                  originals, unchanged, if run_boolean is False)
    sphere_previews: list[Sphere/Brep] - the void spheres actually placed, for
                                  visual QC against the reference image
    tile_boxes    : list[Box]  - fabrication tile bounding boxes covering the
                                  whole facade's combined bounding box
    tile_breps    : list[Brep] - voided_breps trimmed to each tile (facade split
                                  into fabricatable panels)
    tile_index    : list[int]  - which tile_boxes index each tile_breps entry
                                  belongs to (for labeling/nesting downstream)

APPROACH - WHY THIS SHAPE:
1. Sphere placement: pure `random.uniform` per-louvre tends to clump (birthday-
   paradox clustering) and reads as "random" rather than the fairly even,
   deliberate-looking void patterns typical of louvre/perforated-facade
   reference imagery. Jittered grid (regular grid + per-cell random offset)
   fixes clustering by construction, and a min_spacing rejection pass on top
   gives Poisson-disc-like behavior without the cost of a full Bridson
   sampler - reasonable here since sphere counts per louvre are small
   (dozens, not thousands).
2. Boolean subtraction: `Rhino.Geometry.Brep.CreateBooleanDifference` takes
   Brep collections as arguments (not single breps) and, per its documented
   signature, returns a Brep[] with no ref/out parameters on this overload
   (static Brep[] CreateBooleanDifference(IEnumerable<Brep> firstBreps,
   IEnumerable<Brep> secondBreps, double tolerance)). NOTE: I could not get
   a live fetch of the actual developer.rhino3d.com page content to load
   this turn (the API doc site returned only a bare title, no body) - this
   is stated from training knowledge, not freshly re-verified against the
   docs. Confirm it yourself with a quick `help(Rhino.Geometry.Brep.CreateBooleanDifference)`
   in the ScriptEditor Python console before trusting it blindly, especially
   the "returns empty array on failure rather than raising" behavior, which
   the code below assumes and guards for either way.
3. Fabrication tiling: bounding-box grid split is the simplest thing that
   solves "one giant unfabricatable panel" - compute the combined bounding
   box of the whole facade, lay a grid of boxes sized to tile_max_*, and use
   those boxes as cutters (via Brep.Trim / boolean intersection with a box
   brep) against the voided facade. This does not attempt seam aesthetics,
   overlap/tab joinery, or panel labeling - it's a starting point for "can
   this be one panel or does it need repeating tiles," not a finished
   fabrication drawing tool.

TOLERANCE HANDLING:
Uses rs.UnitAbsoluteTolerance() / doc tolerance for boolean ops rather than
a hardcoded 0.001, since louvre models come in at wildly different unit
scales (mm vs m vs ft) and a hardcoded tolerance either does nothing or
wrecks the operation depending on scale.
"""

import random
import math
import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs


def _get_tolerance():
    tol = rs.UnitAbsoluteTolerance()
    if not tol or tol <= 0:
        tol = 0.001
    return tol


def _jittered_grid_points(brep, u_count, v_count, seed):
    """
    Sample points across a brep's face(s) using a jittered grid in each
    face's UV domain, then jitter into the surrounding tolerance so the
    result reads as scattered rather than gridded. Returns a list of
    (Point3d, face_index) tuples.
    """
    rnd = random.Random(seed)
    points = []
    faces = brep.Faces
    for f in range(faces.Count):
        face = faces[f]
        u_domain = face.Domain(0)
        v_domain = face.Domain(1)
        u_step = u_domain.Length / max(u_count, 1)
        v_step = v_domain.Length / max(v_count, 1)
        for i in range(u_count):
            for j in range(v_count):
                u0 = u_domain.Min + i * u_step
                v0 = v_domain.Min + j * v_step
                # jitter within the cell, biased toward center to avoid
                # spilling into the neighboring cell
                u = u0 + rnd.uniform(0.15, 0.85) * u_step
                v = v0 + rnd.uniform(0.15, 0.85) * v_step
                pt_2d = rg.Point2d(u, v)
                if face.IsPointOnFace(u, v) == rg.PointFaceRelation.Exterior:
                    continue
                pt = face.PointAt(u, v)
                points.append((pt, f))
    return points


def _poisson_filter(points, min_spacing):
    """
    Greedy rejection pass: walk the (already-jittered) point list in random
    order, keep a point only if it's farther than min_spacing from every
    previously-accepted point. This is O(n^2) but n is small (grid cells per
    louvre, not per facade), so it's fine here - not a true Bridson sampler.
    """
    accepted = []
    for pt, face_idx in points:
        ok = True
        for apt, _af in accepted:
            if pt.DistanceTo(apt) < min_spacing:
                ok = False
                break
        if ok:
            accepted.append((pt, face_idx))
    return accepted


def _make_void_spheres(louvre, x_count, y_count, r_min, r_max, min_spacing, seed):
    raw_pts = _jittered_grid_points(louvre, x_count, y_count, seed)
    rnd = random.Random(seed)
    rnd.shuffle(raw_pts)  # randomize acceptance order so the filter isn't grid-biased
    kept_pts = _poisson_filter(raw_pts, min_spacing)

    spheres = []
    for pt, _face_idx in kept_pts:
        radius = rnd.uniform(r_min, r_max)
        sphere = rg.Sphere(pt, radius)
        spheres.append(sphere)
    return spheres


def _boolean_difference_all(louvre, sphere_breps, tolerance):
    """
    Subtract all sphere_breps from a single louvre brep in one call.
    Returns (result_breps, success_bool). Falls back to [louvre] unchanged
    if the boolean produces nothing (rather than dropping geometry silently).
    """
    if not sphere_breps:
        return [louvre], False

    first = [louvre]
    result = rg.Brep.CreateBooleanDifference(first, sphere_breps, tolerance)
    # CreateBooleanDifference returns a plain Brep[] here (no out-params on
    # this overload) - not a tuple, unlike Intersection.BrepBrep or similar
    # RhinoCommon calls elsewhere that DO carry out-params.
    if result is None or len(result) == 0:
        return [louvre], False
    return list(result), True


def _combined_bbox(breps):
    bbox = rg.BoundingBox.Empty
    for b in breps:
        bbox.Union(b.GetBoundingBox(True))
    return bbox


def _build_tile_boxes(bbox, tile_max_x, tile_max_y, tile_max_z):
    """
    Lay a grid of axis-aligned boxes (world-aligned, not brep-aligned - fine
    for a typically-planar facade; if the facade is curved/angled in plan,
    tile against a local plane instead, which this script does not attempt).
    """
    if not bbox.IsValid:
        return []

    dx = max(bbox.Max.X - bbox.Min.X, 1e-9)
    dy = max(bbox.Max.Y - bbox.Min.Y, 1e-9)
    dz = max(bbox.Max.Z - bbox.Min.Z, 1e-9)

    nx = max(1, int(math.ceil(dx / tile_max_x))) if tile_max_x > 0 else 1
    ny = max(1, int(math.ceil(dy / tile_max_y))) if tile_max_y > 0 else 1
    nz = max(1, int(math.ceil(dz / tile_max_z))) if tile_max_z > 0 else 1

    step_x = dx / nx
    step_y = dy / ny
    step_z = dz / nz

    boxes = []
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                x0 = bbox.Min.X + ix * step_x
                y0 = bbox.Min.Y + iy * step_y
                z0 = bbox.Min.Z + iz * step_z
                corner_min = rg.Point3d(x0, y0, z0)
                corner_max = rg.Point3d(x0 + step_x, y0 + step_y, z0 + step_z)
                box_bbox = rg.BoundingBox(corner_min, corner_max)
                boxes.append(rg.Box(box_bbox))
    return boxes


def _trim_to_tiles(breps, tile_boxes, tolerance):
    """
    Intersect each brep against each tile box (as a solid brep cutter) to
    produce per-tile fragments. Uses boolean intersection rather than Trim,
    since Trim needs a cutting surface/plane and a box gives closed solids
    more reliably for this use case.
    """
    tile_breps = []
    tile_index = []
    for t_idx, box in enumerate(tile_boxes):
        box_brep = box.ToBrep()
        for brep in breps:
            pieces = rg.Brep.CreateBooleanIntersection([brep], [box_brep], tolerance)
            if pieces:
                for piece in pieces:
                    tile_breps.append(piece)
                    tile_index.append(t_idx)
    return tile_breps, tile_index


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

tolerance = _get_tolerance()

voided_breps = []
sphere_previews = []

if not louvre_breps:
    print("No input louvres - connect Stage 1 output to 'louvre_breps'.")
else:
    for idx, louvre in enumerate(louvre_breps):
        if louvre is None or not louvre.IsValid:
            print("Skipping invalid brep at index {0}".format(idx))
            continue

        # different seed per louvre so voids aren't identical/repeating,
        # but still reproducible run-to-run
        louvre_seed = (random_seed or 0) + idx * 7919

        spheres = _make_void_spheres(
            louvre, x_count, y_count,
            sphere_radius_min, sphere_radius_max,
            min_spacing, louvre_seed
        )
        sphere_breps = [rg.Brep.CreateFromSphere(s) for s in spheres]
        sphere_previews.extend(sphere_breps)

        if run_boolean:
            result, ok = _boolean_difference_all(louvre, sphere_breps, tolerance)
            if not ok:
                print("Boolean difference failed on louvre {0} - check for "
                      "spheres fully outside the solid or tangent at "
                      "tolerance {1}. Kept original brep.".format(idx, tolerance))
            voided_breps.extend(result)
        else:
            voided_breps.append(louvre)

    if not run_boolean:
        print("run_boolean is False - previewing {0} spheres against "
              "unmodified louvres. Toggle run_boolean ON once placement "
              "looks right (boolean ops are slower).".format(len(sphere_previews)))

# --- Fabrication segmentation ---
tile_boxes = []
tile_breps = []
tile_index = []

if voided_breps:
    facade_bbox = _combined_bbox(voided_breps)
    tile_boxes = _build_tile_boxes(facade_bbox, tile_max_x, tile_max_y, tile_max_z)
    if run_boolean:
        # only trim into tiles once the voided geometry is real solids;
        # trimming the un-boolean'd preview is wasted boolean work
        tile_breps, tile_index = _trim_to_tiles(voided_breps, tile_boxes, tolerance)
        print("Facade bounding box split into {0} tile(s); {1} trimmed "
              "fragment(s) produced.".format(len(tile_boxes), len(tile_breps)))
    else:
        print("{0} tile box(es) computed for preview - turn run_boolean ON "
              "to also get trimmed per-tile breps.".format(len(tile_boxes)))
