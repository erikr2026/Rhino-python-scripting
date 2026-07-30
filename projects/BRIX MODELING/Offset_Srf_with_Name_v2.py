# -*- coding: utf-8 -*-
"""
REVERSED OFFSET TOOL (ROUND CORNERS & MERGED FACES)
Inverts offset direction: Positive = Inward, Negative = Outward.
Optimized for Rhino 8/9 Python 3.
"""
import rhinoscriptsyntax as rs
import Rhino
import scriptcontext as sc
import System

def run_reversed_offset():
    ids = rs.SelectedObjects()
    if not ids:
        ids = rs.GetObjects("Select surfaces/polysurfaces to offset",
                            rs.filter.surface | rs.filter.polysurface)
    
    if not ids:
        print("No valid geometry selected.")
        return

    valid_ids = [oid for oid in ids if rs.IsSurface(oid) or rs.IsPolysurface(oid)]
    if not valid_ids:
        print("Selection does not contain valid surfaces or polysurfaces.")
        return

    distance = rs.GetReal("Enter offset distance (Positive = Inward, Negative = Outward)", 1.0)
    if distance is None:
        return

    # Invert for internal API requirements
    offset_dist = -distance
    solid = True
    
    # Setting extend=False forces the engine to blend (round) offset gaps 
    # instead of extending surfaces to sharp intersections.
    extend = False 
    
    tolerance = sc.doc.ModelAbsoluteTolerance
    angle_tolerance = sc.doc.ModelAngleToleranceRadians

    rs.EnableRedraw(False)
    created_count = 0
    current_layer = rs.CurrentLayer()
    
    # Use native RhinoCommon undo block (avoids issues with rs wrapper in CPython)
    undo_record = sc.doc.BeginUndoRecord("Reversed Offset Round")

    try:
        for obj_id in valid_ids:
            brep = rs.coercebrep(obj_id)
            if not brep:
                continue
            
            # Perform offset operation
            # PythonNet maps 'out' parameters to a tuple: (Brep[], outBlends, outWalls)
            offset_result = Rhino.Geometry.Brep.CreateOffsetBrep(
                brep, offset_dist, solid, extend, tolerance
            )

            if offset_result and offset_result[0]:
                for b in offset_result[0]:
                    if b:
                        # Required modification: merge all coplanar faces
                        b.MergeCoplanarFaces(tolerance, angle_tolerance)
                        
                        new_id = sc.doc.Objects.AddBrep(b)
                        if new_id != System.Guid.Empty:
                            rs.ObjectLayer(new_id, current_layer)
                            
                            original_name = rs.ObjectName(obj_id)
                            rs.ObjectName(new_id, original_name if original_name else "Offset_Obj")
                            created_count += 1
                            
                    b.Dispose()
            
            brep.Dispose()
            
    except Exception as e:
        print("Error during processing: {0}".format(str(e)))
    finally:
        sc.doc.EndUndoRecord(undo_record)
        rs.EnableRedraw(True)
        sc.doc.Views.Redraw()

    if created_count > 0:
        # Passing properly formatted lists to prevent Python 3 iteration TypeErrors
        hide_orig = rs.GetBoolean("Hide original objects?",
                                  [("Hide", "No", "Yes")], [True])
        if hide_orig and hide_orig[0]:
            rs.HideObjects(valid_ids)
        
        print("Offset complete. {0} objects created.".format(created_count))

if __name__ == "__main__":
    run_reversed_offset()