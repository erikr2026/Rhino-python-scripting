"""Select all Detail views across all Layout (page) views in the active document.

Engine: Python 3 (CPython, via ScriptEditor / RunPythonScript F5). No behavior
change from v1 - streamlined for clarity and defensive null-checks only.
Not re-verified against live Rhino docs this pass; RhinoCommon API surface
(RhinoDoc.Views.GetPageViews, PageView.GetDetailViews, DetailViewObject.Select)
is unchanged from v1 and was not re-fetched.
"""
import scriptcontext as sc


def select_all_details():
    """Unselect everything, then select every Detail view on every layout.

    Returns the count of details selected (also printed to the console).
    """
    sc.doc.Objects.UnselectAll()

    layouts = sc.doc.Views.GetPageViews() or []

    count = 0
    for layout in layouts:
        details = layout.GetDetailViews() or []
        for detail in details:
            detail.Select(True)
            count += 1

    sc.doc.Views.Redraw()
    print("Selected {0} details across all layouts.".format(count))
    return count


if __name__ == "__main__":
    select_all_details()
