"""Select_AnnontationStyle_All_Layouts_v2.py

Selects every layout-space annotation (dimension, text, leader, etc.) across
ALL page layouts / detail views that uses a Dimension Style the user picks
from a list box. Activates the first layout containing a match.

Engine: written in a Python-2/3-compatible subset (no f-strings, no type
hints, no walrus operator), so it runs unchanged whether launched via the
Rhino 8 `ScriptEditor` command (Python 3 / F5) or the legacy `RunPythonScript`
command (IronPython 2). Default recommended entry point is `ScriptEditor`.

Behavior is intentionally identical to v1 (Select_AnnontationStyle_All_Layouts_v1.py).
This version only refactors for readability and adds a top-level error guard;
no RhinoCommon call signatures were changed. See the owner's copy of v1 for
the original, and the chat/changelog note delivered alongside this file for
the list of what changed and why.
"""

import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs


def _get_style_names():
    """Returns names of all non-deleted Dimension Styles in the active doc."""
    return [s.Name for s in sc.doc.DimStyles if not s.IsDeleted]


def _build_viewport_to_layout_map():
    """Maps every layout MainViewport.Id and every DetailView Viewport.Id
    to its owning RhinoPageView, so an annotation's ViewportId can be
    resolved back to a layout in a single dict lookup."""
    viewport_to_layout = {}
    for pview in sc.doc.Views.GetPageViews():
        viewport_to_layout[pview.MainViewport.Id] = pview
        details = pview.GetDetailViews()
        if details:
            for det in details:
                viewport_to_layout[det.Viewport.Id] = pview
    return viewport_to_layout


def _dimstyle_id_of(obj):
    """Returns the DimensionStyleId for an annotation object, preferring the
    geometry-level style (per-object override) and falling back to the
    attribute-level style. Returns None if neither is present."""
    style_id = getattr(obj.Geometry, "DimensionStyleId", None)
    if style_id is None:
        style_id = getattr(obj.Attributes, "DimensionStyleId", None)
    return style_id


def select_annotations_by_viewport_optimized():
    """Selects layout-assigned annotations matching a chosen Dimension Style."""
    style_names = _get_style_names()
    if not style_names:
        print("No styles found in document.")
        return

    selected_name = rs.ListBox(style_names, "Select Style to highlight in Layouts:", "Style Selector")
    if not selected_name:
        return

    target_style = sc.doc.DimStyles.FindName(selected_name)
    if not target_style:
        return
    target_id = target_style.Id

    viewport_to_layout = _build_viewport_to_layout_map()

    # Fast query directly for Annotation Objects to bypass traversing all geometry
    annotations = sc.doc.Objects.FindByObjectType(Rhino.DocObjects.ObjectType.Annotation)
    if not annotations:
        print("No annotations found in document.")
        return

    rs.EnableRedraw(False)
    sc.doc.Objects.UnselectAll()

    count = 0
    first_layout_with_match = None

    try:
        for obj in annotations:
            if obj.IsDeleted:
                continue

            viewport_id = obj.Attributes.ViewportId
            if viewport_id not in viewport_to_layout:
                continue

            if _dimstyle_id_of(obj) == target_id:
                # Force selection even across inactive layouts
                obj.Select(True, True)
                if first_layout_with_match is None:
                    first_layout_with_match = viewport_to_layout[viewport_id]
                count += 1
    finally:
        # Always restore redraw, even if the loop above raised.
        rs.EnableRedraw(True)

    if count > 0:
        if first_layout_with_match:
            sc.doc.Views.ActiveView = first_layout_with_match
        sc.doc.Views.Redraw()
        print("Success: Selected {} annotations in Layouts/Details.".format(count))
    else:
        print("No matching annotations found in Layout space.")


if __name__ == "__main__":
    try:
        select_annotations_by_viewport_optimized()
    except Exception as ex:
        # Surface a clean one-line message on the command line instead of a
        # raw Python traceback, per shop-floor usability expectations.
        print("Select_AnnontationStyle_All_Layouts failed: {}".format(ex))
