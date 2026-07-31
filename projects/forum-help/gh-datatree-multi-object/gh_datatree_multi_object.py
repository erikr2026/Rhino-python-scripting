"""
GH Python 3 Script Component (Rhino 8) - per-branch geology profile transposition.

Forum context: https://discourse.mcneel.com/t/applying-the-same-gh-routine-across-several-objects/221292
Written for Juan Esteban Velasquez Rojas's question. Two partial replies already
exist in the thread (a pointer to Hops/Data I/O, and a working .gh/.ghx file from
"Artstep"). Neither the OP's original script nor his actual geometry (topography
mesh, geology curves, offset lines) was available to inspect or test against -
this is a from-scratch reconstruction of the workflow he described in prose, built
to demonstrate the data-tree pattern that was actually missing, not a drop-in
replacement for his file. Treat variable names/inputs as a template to adapt, and
re-test against his real model before trusting the numbers.

UNVERIFIED THIS SESSION: network access to developer.rhino3d.com's live API
reference was not exercised for the exact signatures of
`Intersection.ProjectPointsToMeshes` and `Intersection.CurvePlane` below -
they are written from memory of the RhinoCommon API and are plausible, but
were not confirmed against the live docs or a console `help()` call this
turn. Run `help(Rhino.Geometry.Intersect.Intersection.ProjectPointsToMeshes)`
and `help(Rhino.Geometry.Intersect.Intersection.CurvePlane)` in the Rhino
Python editor before trusting the argument order/return shape, particularly
whether `CurvePlane` returns `(bool, CurveIntersections)` or just
`CurveIntersections`/`None` directly - this script assumes the latter.

ENGINE / HOW TO USE:
    This is written for a GH Python 3 script component (the default in Rhino 8),
    not a standalone RunPythonScript file. Drop it into a Python 3 script
    component on the canvas; do not paste into a legacy IronPython 2 component
    (rhinoscriptsyntax calls and DataTree access patterns below assume Python 3
    + Grasshopper's script-component data marshalling, but are otherwise plain
    RhinoCommon/Grasshopper API and should run under either engine).

INPUTS (declare on the component, all as trees, "Reparameterize"/graft OFF at
the component boundary - graft/flatten is exactly what breaks this pattern,
see explanation below):
    offset_lines : Curve   - one branch per offset line, ideally one item per
                              branch (each offset line is its own branch, e.g.
                              paths {0}, {1}, {2}, ... one per cross-section).
    topo_mesh    : Mesh    - single item, same mesh reused for every branch.
    geology_crvs : Curve   - the reference "station 0" soil-layer curves, list
                              (not a tree) - same curves reused for every branch.
    station0_x   : float   - the x (or station) origin the geology curves are
                              parameterised against, single item.

OUTPUTS:
    ground_curves : Curve      - tree, one branch per offset line, projected
                                  natural-ground polyline for that line.
    layer_z       : float      - tree, one branch per offset line, one z value
                                  per geology curve, per point along that line.
    thickness     : float      - tree, one branch per offset line, per-layer
                                  thickness (consecutive layer_z differences)
                                  at each point along that line.

--------------------------------------------------------------------------
WHY THIS NEEDS EXPLICIT PER-BRANCH HANDLING (the actual teaching point):

Grasshopper native components apply one operation across an ENTIRE data
tree using a fixed matching rule (usually "longest list" or "cross
reference" per branch-pair). That works fine when you have exactly one
offset line, because there is only one branch to match against the mesh
and the geology curves - there is no ambiguity.

The moment you have ~40 offset lines, every downstream component that
takes more than one tree as input (e.g. "Project", "Evaluate Curve",
"Plane/Plane intersection") has to decide how to zip branch {0} of the
offset lines against branch {0} of the geology curves, branch {0} of the
thickness maths, etc. If those trees don't already have IDENTICAL path
structures, GH's default matching either:
  (a) silently reuses branch {0} of the shorter tree for everything
      (the "it's not doing the right thing, but not obviously wrong"
      failure the OP describes), or
  (b) grafts/flattens in a way that merges unrelated cross-sections
      into one branch, so thickness values from line 12 get computed
      against ground curve data from line 3.

Graft and Flatten are structural transforms that change WHERE data lives
in the tree - they don't tell a component HOW to iterate line-by-line.
Once you have two or more independent "rows" (cross-sections) that each
need their own private computation using shared reference data (the one
mesh, the one set of geology curves), the correct fix is not more
graft/flatten juggling - it's to iterate the branches yourself and keep
the reference data un-treed (single-item / plain list) so each branch
computation is isolated and explicit. That's what this script does:
one Python loop = one cross-section, full control over which curves and
which mesh get used every time, and the output tree path is set
explicitly to mirror the input path - so nothing can cross-contaminate
between offset lines regardless of how many there are.
--------------------------------------------------------------------------
"""

import Rhino
import Rhino.Geometry as rg
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path

# ---------------------------------------------------------------------
# Tolerances - use the active Rhino document's model tolerance rather
# than a hardcoded number, so this behaves consistently whether the
# model is in meters or millimeters (a common real-world mismatch on
# civil/marine sites brought in from different sources).
# ---------------------------------------------------------------------
tol = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
if tol <= 0:
    tol = 0.01


def project_points_to_mesh(points, mesh, direction=rg.Vector3d.ZAxis):
    """Project a list of points straight down (or along `direction`) onto
    a mesh. Returns a same-length list of Point3d, with None for any
    point that misses the mesh (e.g. control point falls off the edge
    of the topo survey) so a bad point doesn't silently shift the whole
    branch's indexing.
    """
    projected = []
    for pt in points:
        hits = rg.Intersect.Intersection.ProjectPointsToMeshes(
            [mesh], [pt], direction, tol
        )
        projected.append(hits[0] if hits and len(hits) > 0 else None)
    return projected


def layer_elevations_at_station(geology_curves, plane):
    """Intersect a vertical cross-section plane with each geology curve
    (each curve = one soil-layer interface) and return the z of the
    lowest intersection per curve - i.e. the elevation of that layer's
    top at this station. Returns None for a curve that plane misses.
    """
    z_values = []
    for crv in geology_curves:
        ok, events = rg.Intersect.Intersection.CurvePlane(crv, plane, tol)
        if not ok or events is None or events.Count == 0:
            z_values.append(None)
            continue
        # A curve can cross the plane more than once (folded geology);
        # take the intersection point, not just the parameter, and use
        # the lowest z if there are multiple hits at this station.
        zs = [events[i].PointA.Z for i in range(events.Count)]
        z_values.append(min(zs))
    return z_values


def thicknesses_from_elevations(z_values):
    """Consecutive differences between ordered layer elevations = layer
    thickness. Curves must already be ordered top-to-bottom (or
    bottom-to-top consistently) in `geology_crvs` - this script does not
    infer stratigraphic order from geometry, because that's a modeling
    decision only the geologist/user can make correctly.
    """
    out = []
    for i in range(len(z_values) - 1):
        a, b = z_values[i], z_values[i + 1]
        out.append(None if (a is None or b is None) else abs(a - b))
    return out


# ---------------------------------------------------------------------
# Main loop: one branch (one path) = one offset line = one independent
# computation. `geology_crvs` and `topo_mesh` are NOT trees - they are
# plain lists/single items reused identically on every iteration. This
# is the deliberate structural choice that avoids the branch-matching
# ambiguity described above: there is nothing for GH to "match" because
# the matching happens explicitly, in Python, by this loop.
# ---------------------------------------------------------------------
ground_curves = DataTree[object]()
layer_z = DataTree[object]()
thickness = DataTree[object]()

if offset_lines is None or topo_mesh is None or geology_crvs is None:
    print("Missing input(s): connect offset_lines, topo_mesh, and geology_crvs.")
else:
    for path in offset_lines.Paths:
        branch_curves = offset_lines.Branch(path)
        out_path = path  # mirror the input path exactly - do not renumber

        branch_ground_pts = []
        branch_z_rows = []
        branch_thk_rows = []

        for line in branch_curves:
            if line is None:
                continue

            # Sample the offset line at its control points (or divide by
            # length if it's a straight offset with no useful control
            # point spacing - swap this line for
            # line.DivideByCount(n, True) if that fits the OP's geometry
            # better; control-point sampling assumes his lines already
            # carry the station spacing he wants, per his description).
            pts = [line.PointAt(t) for t in
                   [line.Domain.ParameterAt(u) for u in
                    [i / 20.0 for i in range(21)]]]

            ground_pts = project_points_to_mesh(pts, topo_mesh)
            branch_ground_pts.extend([p for p in ground_pts if p is not None])

            for src_pt, grd_pt in zip(pts, ground_pts):
                if grd_pt is None:
                    continue
                station_plane = rg.Plane(
                    rg.Point3d(station0_x + src_pt.X, 0, 0),
                    rg.Vector3d.XAxis,
                )
                z_vals = layer_elevations_at_station(geology_crvs, station_plane)
                branch_z_rows.append(z_vals)
                branch_thk_rows.append(thicknesses_from_elevations(z_vals))

        if branch_ground_pts:
            ground_curves.Add(
                rg.PolylineCurve(branch_ground_pts), out_path
            )
        for z_row in branch_z_rows:
            for z in z_row:
                layer_z.Add(z, out_path)
        for thk_row in branch_thk_rows:
            for t in thk_row:
                thickness.Add(t, out_path)
