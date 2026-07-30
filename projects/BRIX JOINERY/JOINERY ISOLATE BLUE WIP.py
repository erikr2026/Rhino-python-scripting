# -*- coding: utf-8 -*-

"""
Rhino Python Script (Rhino 8 & 9)
Inverts visibility of objects based on subobject face colors.
Any Brep with at least one blue (RGB 0,0,255) face is shown (isolated).
All other objects that do not contain a blue face are hidden.
"""

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System.Drawing

def main():
    undo_record = sc.doc.BeginUndoRecord("Invert Hide Non-Blue Face Objects")
    rs.EnableRedraw(False)

    target_r = 0
    target_g = 0
    target_b = 255

    to_show = []
    to_hide = []

    # Retrieve all physical objects in the active model database
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.ActiveObjects = True
    settings.HiddenObjects = True
    settings.LockedObjects = True
    
    doc_objects = sc.doc.Objects.GetObjectList(settings)

    for obj in doc_objects:
        # Skip system, helper, or grip objects
        if not obj or obj.IsDeleted:
            continue
            
        geom = obj.Geometry
        is_target = False
        
        # Check if the object is a Brep
        if isinstance(geom, Rhino.Geometry.Brep):
            for face in geom.Faces:
                color = face.PerFaceColor
                # Unset face colors return Color.Empty, which has IsEmpty set to True
                if not color.IsEmpty:
                    # Compare raw RGB values to avoid alpha channel mismatch issues
                    if color.R == target_r and color.G == target_g and color.B == target_b:
                        is_target = True
                        break
                        
        if is_target:
            # Collect target objects to ensure they are visible
            to_show.append(obj)
        else:
            # Non-target objects will be hidden if they are currently visible
            if obj.Visible:
                to_hide.append(obj)

    shown_count = 0
    hidden_count = 0

    # Ensure all target objects are shown (even if locked, we make them visible)
    for obj in to_show:
        if not obj.Visible:
            sc.doc.Objects.Show(obj.Id, True)
            shown_count += 1

    # Hide all non-target objects
    for obj in to_hide:
        sc.doc.Objects.Hide(obj.Id, True)
        hidden_count += 1

    sc.doc.EndUndoRecord(undo_record)
    rs.EnableRedraw(True)
    sc.doc.Views.Redraw()

    # Provide shop-floor operational command-line feedback
    feedback_msg = "Isolate Complete: Revealed {} blue-faced object(s); hid {} other object(s)."
    print(feedback_msg.format(shown_count, hidden_count))

if __name__ == "__main__":
    main()