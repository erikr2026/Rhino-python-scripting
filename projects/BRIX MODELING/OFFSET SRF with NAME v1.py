# -*- coding: utf-8 -*-
"""
REVERSED OFFSET TOOL
Inverts offset direction: Positive = Inward, Negative = Outward.
Optimized for Rhino 8/9 Python 3.
"""
import rhinoscriptsyntax as rs
import Rhino
import scriptcontext as sc
import System

def run_reversed_offset():
    # 1. Validation and Selection
    ids = rs.SelectedObjects()
    if not ids:
        ids = rs.GetObjects("Select surfaces/polysurfaces to offset",
                            rs.filter.surface | rs.filter.polysurface)
    
    if not ids:
        print("No valid geometry selected.")
        return

    # Filter to ensure valid input types
    valid_ids = [oid for oid in ids if rs.IsSurface(oid) or rs.IsPolysurface(oid)]
    if not valid_ids:
        print("Selection does not contain valid surfaces or polysurfaces.")
        return

    # 2. Parameters
    distance = rs.GetReal("Enter offset distance (Positive = Inward, Negative = Outward)", 1.0)
    if distance is None:
        return

    # Invert for internal API requirements
    offset_dist = -distance
    solid = True
    loose = False
    tolerance = sc.doc.ModelAbsoluteTolerance

    # 3. Execution
    rs.EnableRedraw(False)
    created_count = 0
    current_layer = rs.CurrentLayer()

    try:
        for obj_id in valid_ids:
            brep = rs.coercebrep(obj_id)
            if not brep:
                continue
            
            # Perform offset operation
            # Result returns (Brep[], double)
            offset_result = Rhino.Geometry.Brep.CreateOffsetBrep(
                brep, offset_dist, solid, not loose, tolerance
            )

            if offset_result and offset_result[0]:
                for b in offset_result[0]:
                    if b:
                        new_id = sc.doc.Objects.AddBrep(b)
                        if new_id:
                            rs.ObjectLayer(new_id, current_layer)
                            rs.ObjectName(new_id, rs.ObjectName(obj_id) or "Offset_Obj")
                            created_count += 1
                    b.Dispose()
            
            brep.Dispose()
            
    except Exception as e:
        print("Error during processing: {0}".format(str(e)))
    finally:
        rs.EnableRedraw(True)
        sc.doc.Views.Redraw()

    # 4. Cleanup
    if created_count > 0:
        hide_orig = rs.GetBoolean("Hide original objects?",
                                  ("Hide", "No", "Yes"), (True))
        if hide_orig and hide_orig[0]:
            rs.HideObjects(valid_ids)
        
        print("Offset complete. {0} objects created.".format(created_count))

if __name__ == "__main__":
    run_reversed_offset()