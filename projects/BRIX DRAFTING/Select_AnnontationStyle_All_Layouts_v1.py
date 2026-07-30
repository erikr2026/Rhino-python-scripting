import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs

def select_annotations_by_viewport_optimized():
    """Selects layout-assigned annotations matching a chosen Dimension Style."""
    styles = sc.doc.DimStyles
    style_names = [s.Name for s in styles if not s.IsDeleted]
    if not style_names: 
        print("No styles found in document.")
        return

    # User chooses the style
    selected_name = rs.ListBox(style_names, "Select Style to highlight in Layouts:", "Style Selector")
    if not selected_name: 
        return

    target_style = styles.FindName(selected_name)
    if not target_style: 
        return
    target_id = target_style.Id

    # Map layout and detail viewport IDs directly to their parent page view
    page_views = sc.doc.Views.GetPageViews()
    viewport_to_layout = {}
    
    for pview in page_views:
        viewport_to_layout[pview.MainViewport.Id] = pview
        details = pview.GetDetailViews()
        if details:
            for det in details:
                viewport_to_layout[det.Viewport.Id] = pview

    # Fast query directly for Annotation Objects to bypass traversing all geometry
    annotations = sc.doc.Objects.FindByObjectType(Rhino.DocObjects.ObjectType.Annotation)
    if not annotations:
        print("No annotations found in document.")
        return

    # Disable redraw to accelerate selection processing
    rs.EnableRedraw(False)
    sc.doc.Objects.UnselectAll()
    
    count = 0
    first_layout_with_match = None

    for obj in annotations:
        if obj.IsDeleted:
            continue
            
        v_id = obj.Attributes.ViewportId
        if v_id in viewport_to_layout:
            # Query style ID securely with immediate geometry-level preference
            obj_style_id = getattr(obj.Geometry, "DimensionStyleId", None)
            if obj_style_id is None:
                obj_style_id = getattr(obj.Attributes, "DimensionStyleId", None)

            if obj_style_id == target_id:
                # Force selection even across inactive layouts
                obj.Select(True, True)
                
                if first_layout_with_match is None:
                    first_layout_with_match = viewport_to_layout[v_id]
                count += 1

    # Re-enable redraw before running the view switch
    rs.EnableRedraw(True)

    if count > 0:
        if first_layout_with_match:
            sc.doc.Views.ActiveView = first_layout_with_match
        sc.doc.Views.Redraw()
        print("Success: Selected {} annotations in Layouts/Details.".format(count))
    else:
        print("No matching annotations found in Layout space.")

if __name__ == "__main__":
    select_annotations_by_viewport_optimized()