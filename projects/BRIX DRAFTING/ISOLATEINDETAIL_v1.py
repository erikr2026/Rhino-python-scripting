import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs

def IsolateInDetail():
    # 1. Check if we are in a Detail
    view = sc.doc.Views.ActiveView
    viewport = view.ActiveViewport
    
    if view.MainViewport.Id == viewport.Id:
        print("Error: You MUST be double-clicked inside a Detail window.")
        return

    # 2. Get the objects you want to KEEP (Isolate)
    keep_ids = rs.GetObjects("Select objects to ISOLATE in this detail", preselect=True)
    if not keep_ids:
        return

    # 3. Find every other object that should be HIDDEN
    # rs.AllObjects() gets everything visible in the document
    all_ids = rs.AllObjects()
    keep_set = set(keep_ids)
    
    # Filter list: any ID not in our 'keep' list
    hide_ids = [obj_id for obj_id in all_ids if obj_id not in keep_set]

    if not hide_ids:
        print("Everything is already isolated.")
        return

    # 4. THE SMASH: Use the native Rhino Command engine
    rs.EnableRedraw(False)
    try:
        # Clear current selection
        rs.UnselectAllObjects()
        
        # Select the objects we want to hide
        rs.SelectObjects(hide_ids)
        
        # Run the actual Rhino command - this is bulletproof
        # The "-" prefix runs the scripted version (no dialogs)
        rs.Command("-_HideInDetail _Enter", echo=False)
        
        # Cleanup: Unselect the hidden objects and re-select the isolated ones
        rs.UnselectAllObjects()
        rs.SelectObjects(keep_ids)
        
    finally:
        rs.EnableRedraw(True)
        rs.Redraw()

    print("Isolate complete using HideInDetail.")

if __name__ == "__main__":
    IsolateInDetail()