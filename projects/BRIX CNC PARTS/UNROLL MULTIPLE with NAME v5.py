# rdk:command_name: UNROLL_MULTIPLE
# rdk:command_alias: UNROLL_MULTIPLE
# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc
import math
import System  # Handle Guid.Empty validation safely

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
    
    # Abort execution safely if user cancels the dialog box
    if proj_name is None:
        return

    # Select objects
    objs = rs.GetObjects("Select surfaces/polysurfaces to unroll",
                         rs.filter.surface | rs.filter.polysurface)
    if not objs:
        return

    # Initialize RhinoCommon Undo Record to safely group all operations
    undo_record = Rhino.RhinoDoc.ActiveDoc.BeginUndoRecord("Unroll and Generate Bend Lines")
    
    try:
        results = []        # To store (ids, angle)

        for obj_id in objs:
            if not rs.IsObject(obj_id):
                continue
                
            name = rs.ObjectName(obj_id)
            
            # Get the geometry
            brep = rs.coercebrep(obj_id)
            if not brep: 
                continue

            # 1. Find grouped curves/points/dots
            following_ids = []
            grps = rs.ObjectGroups(obj_id)
            if grps:
                members = rs.ObjectsByGroup(grps[0])
                following_ids = [m for m in members if m != obj_id and
                                (rs.IsCurve(m) or rs.IsPoint(m) or rs.IsTextDot(m))]

            # 2. Setup RhinoCommon Unroller (Silent)
            unroller = Rhino.Geometry.Unroller(brep)
            unroller.ExplodeOutput = False 
            
            for f_id in following_ids:
                geom = rs.coercegeometry(f_id)
                if geom: 
                    unroller.AddFollowingGeometry(geom)

            unrolled_geom, curves, points, dots = unroller.PerformUnroll()
            
            if not unrolled_geom:
                continue

            # 3. Bake geometry to the document with strict Null/Empty GUID safety filters
            all_ids = []
            surfs = []
            
            for g in unrolled_geom:
                if g:
                    new_id = sc.doc.Objects.AddBrep(g)
                    if new_id and new_id != System.Guid.Empty:
                        all_ids.append(new_id)
                        surfs.append(new_id)
            
            for c in curves: 
                if c:
                    new_id = sc.doc.Objects.AddCurve(c)
                    if new_id and new_id != System.Guid.Empty:
                        all_ids.append(new_id)

            for p in points: 
                if p:
                    new_id = sc.doc.Objects.AddPoint(p)
                    if new_id and new_id != System.Guid.Empty:
                        all_ids.append(new_id)
                        
            for d in dots: 
                if d:
                    new_id = sc.doc.Objects.AddTextDot(d)
                    if new_id and new_id != System.Guid.Empty:
                        all_ids.append(new_id)

            # If no geometry was successfully baked, skip processing this object
            if not all_ids:
                continue

            # 4. SILENT BEND LINE GENERATION ON "97 CUTFILE::MARKINGS"
            markings_layer = "97 CUTFILE::MARKINGS"
            if not rs.IsLayer(markings_layer):
                rs.AddLayer(markings_layer)

            seen_edge_coords = set()
            line_length = 2.0

            for ug in unrolled_geom:
                if not ug:
                    continue
                for edge in ug.Edges:
                    # Filter for internal edges only
                    if edge.Valence != rg.EdgeAdjacency.Interior:
                        continue
                        
                    # Coordinate-based duplicate check to prevent double baking
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
                    
                    # Apply length rule (Full line if <= 4 inches, otherwise two 2-inch segments at ends)
                    if total_len <= 4.0:
                        line_geom = rg.Line(crv.PointAt(0.0), crv.PointAt(total_len))
                        line_id = sc.doc.Objects.AddLine(line_geom)
                        if line_id and line_id != System.Guid.Empty:
                            rs.ObjectLayer(line_id, markings_layer)
                            all_ids.append(line_id)
                    else:
                        line_geom1 = rg.Line(crv.PointAt(0.0), crv.PointAt(line_length))
                        line_geom2 = rg.Line(crv.PointAt(total_len), crv.PointAt(total_len - line_length))
                        line_id1 = sc.doc.Objects.AddLine(line_geom1)
                        line_id2 = sc.doc.Objects.AddLine(line_geom2)
                        if line_id1 and line_id1 != System.Guid.Empty:
                            rs.ObjectLayer(line_id1, markings_layer)
                            all_ids.append(line_id1)
                        if line_id2 and line_id2 != System.Guid.Empty:
                            rs.ObjectLayer(line_id2, markings_layer)
                            all_ids.append(line_id2)
                    
                    seen_edge_coords.add(edge_key)

            # 5. Set object name on the unrolled surfaces and generate Centroid Text
            if surfs:
                main = surfs[0]
                if name:
                    for s in surfs: 
                        if rs.IsObject(s):
                            rs.ObjectName(s, name)
                
                # Resolve centroid for the label positioning
                cen = None
                centroid_data = rs.SurfaceAreaCentroid(main)
                
                if centroid_data and len(centroid_data) > 0:
                    cen = centroid_data[0]
                else:
                    # Fallback: Calculate Center point from Bounding Box
                    bb = rs.BoundingBox(main)
                    if bb and len(bb) == 8:
                        cen = [
                            sum(p[0] for p in bb) / 8.0,
                            sum(p[1] for p in bb) / 8.0,
                            sum(p[2] for p in bb) / 8.0
                        ]
                
                # Generate physical Text objects at the centroid
                if cen:
                    # Ensure layer "97 CUTFILE::BRIX TEXT" exists
                    target_layer = "97 CUTFILE::BRIX TEXT"
                    if not rs.IsLayer(target_layer):
                        rs.AddLayer(target_layer)
                    
                    # Set up style overrides matching "CNC PARTS" style
                    style_name = "CNC PARTS"
                    dim_style = sc.doc.DimStyles.FindName(style_name)
                    if not dim_style:
                        dim_style = sc.doc.DimStyles.Find(style_name, True)
                    
                    # Helper to cleanly bake individual text entities
                    def create_label(text_string, position_coords):
                        text_entity = Rhino.Geometry.TextEntity()
                        text_plane = Rhino.Geometry.Plane(
                            Rhino.Geometry.Point3d(position_coords[0], position_coords[1], position_coords[2]), 
                            Rhino.Geometry.Vector3d.ZAxis
                        )
                        text_entity.Plane = text_plane
                        text_entity.PlainText = text_string
                        text_entity.Justification = Rhino.Geometry.TextJustification.Center
                        
                        if dim_style:
                            text_entity.DimensionStyleId = dim_style.Id
                            text_entity.TextHeight = dim_style.TextHeight if dim_style.TextHeight > 0 else 1.0
                        else:
                            current_style = sc.doc.DimStyles.Current
                            if current_style:
                                text_entity.DimensionStyleId = current_style.Id
                                text_entity.TextHeight = current_style.TextHeight if current_style.TextHeight > 0 else 1.0
                        
                        baked_id = sc.doc.Objects.AddText(text_entity)
                        if baked_id and baked_id != System.Guid.Empty:
                            rs.ObjectLayer(baked_id, target_layer)
                            all_ids.append(baked_id)

                    # Label 1: Base Part Name at centroid
                    base_part_name = name if name else "!"
                    create_label(base_part_name, cen)

                    # Label 2: Project Name (if provided) placed 1" in +Y direction
                    if proj_name.strip():
                        proj_pos = [cen[0], cen[1] + 1.0, cen[2]]
                        create_label(proj_name.strip(), proj_pos)

            # Identify valid unrolled parts (no grouping applied to preserve individual element state)
            valid_ids = [aid for aid in all_ids if rs.IsObject(aid)]

            # 6. Calculate original orientation
            bb = rs.BoundingBox(obj_id)
            if bb and len(bb) == 8:
                vec_x = rs.VectorSubtract(bb[1], bb[0])
                vec_x = [vec_x[0], vec_x[1], 0]
                unit_x = rs.VectorUnitize(vec_x)
                if unit_x:
                    angle = rs.VectorAngle([1, 0, 0], unit_x)
                    if unit_x[1] < 0: 
                        angle = 360 - angle
                else:
                    angle = 0.0
            else:
                angle = 0.0

            results.append((valid_ids, angle))

        if not results:
            print("Nothing could be unrolled successfully.")
            return

        # ————————————————————————
        # GRID LAYOUT
        # ————————————————————————
        n = len(results)
        cols = int(math.ceil(math.sqrt(n)))
        spacing = 24.0

        max_w = max_h = 0.0
        for ids, _ in results:
            # Only check bounding boxes for currently existing objects
            active_ids = [x for x in ids if rs.IsObject(x)]
            if not active_ids:
                continue
            bb = rs.BoundingBox(active_ids)
            if bb and len(bb) == 8:
                w = rs.Distance(bb[0], bb[1])
                h = rs.Distance(bb[0], bb[3])
                max_w = max(max_w, w)
                max_h = max(max_h, h)

        cell_w = max_w + spacing
        cell_h = max_h + spacing

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
                cx = sum(p[0] for p in bb) / 8.0
                cy = sum(p[1] for p in bb) / 8.0
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