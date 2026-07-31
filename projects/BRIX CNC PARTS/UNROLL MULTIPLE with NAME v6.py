# rdk:command_name: UNROLL_MULTIPLE
# rdk:command_alias: UNROLL_MULTIPLE
# -*- coding: utf-8 -*-
"""
UNROLL MULTIPLE with NAME v6 - streamlined rewrite of v5 (same behavior).

Execution engine: unconfirmed. The "# rdk:" header comments at the top of
this file suggest it is registered as a Rhino command/alias, which is the
same pattern used by both the legacy RunPythonScript command and Rhino 8's
ScriptEditor command registration. Live docs did not resolve which one
applies here (both fetch attempts to developer.rhino3d.com 404'd this
session), so this is NOT verified - confirm with the owner or by checking
how v5 is actually invoked before assuming either engine. The source itself
is written to run under both: plain ASCII, str.format() instead of f-strings,
and an explicit UTF-8 coding declaration.

Unrolls selected surfaces/polysurfaces, positions the unrolled results in a
grid layout, generates centered CNC text labels, and silently creates bend
lines on internal edges on the "97 CUTFILE::MARKINGS" layer.
"""
import rhinoscriptsyntax as rs
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc
import math
import System  # Guid.Empty validation

MARKINGS_LAYER = "97 CUTFILE::MARKINGS"
TEXT_LAYER = "97 CUTFILE::BRIX TEXT"
TEXT_STYLE_NAME = "CNC PARTS"
BEND_LINE_LENGTH = 2.0
BEND_LINE_FULL_THRESHOLD = 4.0
GRID_SPACING = 24.0
PROJECT_LABEL_OFFSET_Y = 1.0


def _bake_id(new_id):
    """Return new_id if the RhinoCommon Add* call produced a real object,
    else None. Centralizes the Guid.Empty/None safety check that v5
    repeated after every sc.doc.Objects.Add* call."""
    if new_id and new_id != System.Guid.Empty:
        return new_id
    return None


def _bbox_average(bb):
    """Average of the 8 bounding-box corner points, as [x, y, z].
    Same math as v5's repeated 'sum(p[i] for p in bb) / 8.0' snippets."""
    return [sum(p[i] for p in bb) / 8.0 for i in range(3)]


def _get_following_geometry(obj_id):
    """Curves/points/dots grouped with obj_id, to unroll alongside it.
    Matches v5: only the object's FIRST group is considered."""
    grps = rs.ObjectGroups(obj_id)
    if not grps:
        return []
    members = rs.ObjectsByGroup(grps[0])
    return [m for m in members if m != obj_id and
            (rs.IsCurve(m) or rs.IsPoint(m) or rs.IsTextDot(m))]


def _bake_unroll_results(unrolled_breps, curves, points, dots):
    """Bake the Unroller.PerformUnroll() output to the document.
    Returns (all_ids, surface_ids) - surface_ids is the subset of all_ids
    that came from unrolled_breps, in order."""
    all_ids = []
    surface_ids = []

    for g in unrolled_breps:
        if not g:
            continue
        new_id = _bake_id(sc.doc.Objects.AddBrep(g))
        if new_id:
            all_ids.append(new_id)
            surface_ids.append(new_id)

    for c in curves:
        if not c:
            continue
        new_id = _bake_id(sc.doc.Objects.AddCurve(c))
        if new_id:
            all_ids.append(new_id)

    for p in points:
        if not p:
            continue
        new_id = _bake_id(sc.doc.Objects.AddPoint(p))
        if new_id:
            all_ids.append(new_id)

    for d in dots:
        if not d:
            continue
        new_id = _bake_id(sc.doc.Objects.AddTextDot(d))
        if new_id:
            all_ids.append(new_id)

    return all_ids, surface_ids


def _generate_bend_lines(unrolled_breps, all_ids):
    """Bake short marker lines on internal (interior-valence) edges of the
    unrolled breps, onto MARKINGS_LAYER. Edges shorter than the full-line
    threshold get one line spanning the whole edge; longer edges get two
    short lines, one at each end. Coordinate-based dedup prevents baking
    the same shared edge twice. Appends new object ids to all_ids in place."""
    if not rs.IsLayer(MARKINGS_LAYER):
        rs.AddLayer(MARKINGS_LAYER)

    seen_edge_coords = set()

    for ug in unrolled_breps:
        if not ug:
            continue
        for edge in ug.Edges:
            if edge.Valence != rg.EdgeAdjacency.Interior:
                continue

            p1 = edge.PointAtStart
            p2 = edge.PointAtEnd
            pts = sorted([(round(p1.X, 3), round(p1.Y, 3), round(p1.Z, 3)),
                          (round(p2.X, 3), round(p2.Y, 3), round(p2.Z, 3))])
            edge_key = tuple(pts)
            if edge_key in seen_edge_coords:
                continue

            crv = edge.EdgeCurve.DuplicateCurve()
            if not crv:
                continue

            total_len = crv.GetLength()
            crv.Domain = rg.Interval(0, total_len)

            if total_len <= BEND_LINE_FULL_THRESHOLD:
                segments = [(crv.PointAt(0.0), crv.PointAt(total_len))]
            else:
                segments = [
                    (crv.PointAt(0.0), crv.PointAt(BEND_LINE_LENGTH)),
                    (crv.PointAt(total_len), crv.PointAt(total_len - BEND_LINE_LENGTH)),
                ]

            for start, end in segments:
                line_id = _bake_id(sc.doc.Objects.AddLine(rg.Line(start, end)))
                if line_id:
                    rs.ObjectLayer(line_id, MARKINGS_LAYER)
                    all_ids.append(line_id)

            seen_edge_coords.add(edge_key)


def _resolve_centroid(main_surface_id):
    """Centroid of the main unrolled surface, falling back to the
    bounding-box average if the area centroid can't be computed."""
    centroid_data = rs.SurfaceAreaCentroid(main_surface_id)
    if centroid_data and len(centroid_data) > 0:
        return centroid_data[0]

    bb = rs.BoundingBox(main_surface_id)
    if bb and len(bb) == 8:
        return _bbox_average(bb)
    return None


def _make_label_factory(all_ids):
    """Returns a create_label(text, position) closure that bakes a single
    centered TextEntity onto TEXT_LAYER, using the "CNC PARTS" dimstyle
    (or the document's current dimstyle if that one isn't found).
    Appends the baked id to all_ids in place."""
    if not rs.IsLayer(TEXT_LAYER):
        rs.AddLayer(TEXT_LAYER)

    dim_style = sc.doc.DimStyles.FindName(TEXT_STYLE_NAME)
    if not dim_style:
        dim_style = sc.doc.DimStyles.Find(TEXT_STYLE_NAME, True)

    def create_label(text_string, position_coords):
        text_entity = rg.TextEntity()
        text_entity.Plane = rg.Plane(
            rg.Point3d(position_coords[0], position_coords[1], position_coords[2]),
            rg.Vector3d.ZAxis
        )
        text_entity.PlainText = text_string
        text_entity.Justification = rg.TextJustification.Center

        style = dim_style or sc.doc.DimStyles.Current
        if style:
            text_entity.DimensionStyleId = style.Id
            text_entity.TextHeight = style.TextHeight if style.TextHeight > 0 else 1.0

        baked_id = _bake_id(sc.doc.Objects.AddText(text_entity))
        if baked_id:
            rs.ObjectLayer(baked_id, TEXT_LAYER)
            all_ids.append(baked_id)

    return create_label


def _label_surfaces(surface_ids, part_name, proj_name, all_ids):
    """Set the part name on all unrolled surfaces for this part, then bake
    the part-name label at the main surface's centroid and (if provided)
    the project-name label offset above it."""
    if not surface_ids:
        return

    main = surface_ids[0]
    if part_name:
        for s in surface_ids:
            if rs.IsObject(s):
                rs.ObjectName(s, part_name)

    cen = _resolve_centroid(main)
    if not cen:
        return

    create_label = _make_label_factory(all_ids)

    create_label(part_name if part_name else "!", cen)

    if proj_name.strip():
        proj_pos = [cen[0], cen[1] + PROJECT_LABEL_OFFSET_Y, cen[2]]
        create_label(proj_name.strip(), proj_pos)


def _original_orientation_angle(obj_id):
    """Angle (degrees, 0-360) of the source object's bounding-box X edge
    relative to world X, used to re-orient the unrolled result to roughly
    match the original part's layout orientation."""
    bb = rs.BoundingBox(obj_id)
    if not (bb and len(bb) == 8):
        return 0.0

    vec_x = rs.VectorSubtract(bb[1], bb[0])
    vec_x = [vec_x[0], vec_x[1], 0]
    unit_x = rs.VectorUnitize(vec_x)
    if not unit_x:
        return 0.0

    angle = rs.VectorAngle([1, 0, 0], unit_x)
    if unit_x[1] < 0:
        angle = 360 - angle
    return angle


def _unroll_one(obj_id):
    """Unroll a single surface/polysurface plus its grouped following
    geometry, bake everything, add bend-line markings and labels.
    Returns (valid_baked_ids, orientation_angle), or None if this object
    couldn't be unrolled/baked."""
    if not rs.IsObject(obj_id):
        return None

    name = rs.ObjectName(obj_id)

    brep = rs.coercebrep(obj_id)
    if not brep:
        return None

    following_ids = _get_following_geometry(obj_id)

    unroller = rg.Unroller(brep)
    unroller.ExplodeOutput = False
    for f_id in following_ids:
        geom = rs.coercegeometry(f_id)
        if geom:
            unroller.AddFollowingGeometry(geom)

    unrolled_geom, curves, points, dots = unroller.PerformUnroll()
    if not unrolled_geom:
        return None

    all_ids, surface_ids = _bake_unroll_results(unrolled_geom, curves, points, dots)
    if not all_ids:
        return None

    _generate_bend_lines(unrolled_geom, all_ids)

    return unrolled_geom, all_ids, surface_ids, name


def arrange_unrolled_surfaces():
    """
    Unrolls selected surfaces, positions them cleanly in a grid layout,
    generates centered CNC text labels, and then automatically and silently
    creates bend lines on internal edges on the "97 CUTFILE::MARKINGS" layer.
    """
    # Prompt for project name using strict positional arguments to match Eto wrapper signatures
    proj_name = rs.StringBox(
        "Enter Project Name for CNC labels:",
        "",
        "Project Name Configuration"
    )
    if proj_name is None:
        return  # user cancelled

    objs = rs.GetObjects("Select surfaces/polysurfaces to unroll",
                         rs.filter.surface | rs.filter.polysurface)
    if not objs:
        return

    undo_record = Rhino.RhinoDoc.ActiveDoc.BeginUndoRecord("Unroll and Generate Bend Lines")

    try:
        results = []  # list of (valid_ids, angle)

        for obj_id in objs:
            unroll_result = _unroll_one(obj_id)
            if unroll_result is None:
                continue
            unrolled_geom, all_ids, surface_ids, name = unroll_result

            _label_surfaces(surface_ids, name, proj_name, all_ids)

            # No grouping applied to preserve individual element state
            valid_ids = [aid for aid in all_ids if rs.IsObject(aid)]
            angle = _original_orientation_angle(obj_id)
            results.append((valid_ids, angle))

        if not results:
            print("Nothing could be unrolled successfully.")
            return

        # ————————————————————————
        # GRID LAYOUT
        # ————————————————————————
        n = len(results)
        cols = int(math.ceil(math.sqrt(n)))

        max_w = max_h = 0.0
        for ids, _ in results:
            active_ids = [x for x in ids if rs.IsObject(x)]
            if not active_ids:
                continue
            bb = rs.BoundingBox(active_ids)
            if bb and len(bb) == 8:
                w = rs.Distance(bb[0], bb[1])
                h = rs.Distance(bb[0], bb[3])
                max_w = max(max_w, w)
                max_h = max(max_h, h)

        cell_w = max_w + GRID_SPACING
        cell_h = max_h + GRID_SPACING

        for i, (ids, angle) in enumerate(results):
            active_ids = [x for x in ids if rs.IsObject(x)]
            if not active_ids:
                continue

            bb = rs.BoundingBox(active_ids)
            if not bb or len(bb) < 8:
                continue

            row, col = i // cols, i % cols
            target_pt = [col * cell_w, -row * cell_h, bb[0][2]]

            move_vec = rs.VectorSubtract(target_pt, bb[0])
            rs.MoveObjects(active_ids, move_vec)

            if abs(angle) > 0.0001:
                cx, cy, _ = _bbox_average(bb)
                center = [cx, cy, bb[0][2]]
                rs.RotateObjects(active_ids, center, -angle, axis=[0, 0, 1])

        sc.doc.Views.Redraw()
        print("Done: {0} parts unrolled, arranged, and processed for bend markings.".format(n))

    except Exception as ex:
        print("An error occurred during execution: {0}".format(ex))

    finally:
        # Guarantee that the undo context finishes cleanly
        if undo_record:
            Rhino.RhinoDoc.ActiveDoc.EndUndoRecord(undo_record)


if __name__ == "__main__":
    arrange_unrolled_surfaces()
