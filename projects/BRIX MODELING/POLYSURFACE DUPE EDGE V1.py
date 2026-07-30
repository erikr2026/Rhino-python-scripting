import rhinoscriptsyntax as rs

def duplicate_polysurface_edges():
    # 1. Ask user to select a polysurface
    obj_id = rs.GetObject("Select a closed polysurface", filter=8+16)
    if not obj_id:
        return

    # 2. Get all edges of the brep
    edges = rs.DuplicateEdgeCurves(obj_id)
    
    if edges:
        # 3. Optional: Join them into a single curve object if possible
        joined_curves = rs.JoinCurves(edges, delete_input=True)
        
        # 4. Select the resulting curves
        rs.SelectObjects(joined_curves)
        print("Successfully extracted {} curves.".format(len(joined_curves)))
    else:
        print("No edges found or operation failed.")

if __name__ == "__main__":
    duplicate_polysurface_edges()