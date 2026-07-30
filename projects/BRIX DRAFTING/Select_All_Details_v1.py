import Rhino
import scriptcontext as sc

def select_all_details():
    # Clear current selection
    sc.doc.Objects.UnselectAll()
    
    # Get all page layouts in the document
    layouts = sc.doc.Views.GetPageViews()
    
    count = 0
    for layout in layouts:
        # Get all detail objects on the specific layout page
        details = layout.GetDetailViews()
        for detail in details:
            # Select the detail object
            detail.Select(True)
            count += 1
            
    sc.doc.Views.Redraw()
    print("Selected {0} details across all layouts.".format(count))

if __name__ == "__main__":
    select_all_details()