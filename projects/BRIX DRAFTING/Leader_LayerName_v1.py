# LeaderLayerName.py - Updated for proper detail view tracking
# Follows the logic of LeaderObjectName to ensure coordinate mapping 
# inside detail views while maintaining proper placement.

#! python3
import Rhino
import scriptcontext as sc

def __LayerNameFilter(rhObj, geo, idx):
    """Filter to ensure we pick valid geometry."""
    if isinstance(rhObj, Rhino.DocObjects.RhinoObject):
        return rhObj.Attributes.LayerIndex >= 0
    return False

def LeaderLayerName():
    # Setup object picker
    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt('Select object to display layer name')
    go.SetCustomGeometryFilter(__LayerNameFilter)
    go.EnablePreSelect(False, True)
    go.OneByOnePostSelect = True
    go.InactiveDetailPickEnabled = True
    go.Get()
    
    if go.CommandResult() != Rhino.Commands.Result.Success:
        return

    objref = go.Object(0)
    point = objref.SelectionPoint()
    if not point.IsValid:
        return

    # Get the layer name
    layer = sc.doc.Layers.FindIndex(objref.Object().Attributes.LayerIndex)
    if not layer:
        return
    layer_name = layer.Name

    # Logic from LeaderObjectName:
    # If selected in a detail, transform the point to page space
    # so the leader remains attached to the layout perspective.
    detail_sn = objref.SelectionViewDetailSerialNumber()
    if detail_sn > 0:
        detail_obj = sc.doc.Objects.Find(detail_sn)
        if isinstance(detail_obj, Rhino.DocObjects.DetailViewObject):
            # Applying WorldToPageTransform ensures the point maps correctly
            # to the paper space coordinate system for that detail.
            w2p = detail_obj.WorldToPageTransform
            point.Transform(w2p)

    # Deselect the object to avoid visual clutter
    objref.Object().Select(False)

    # Execute command
    # Using raw coordinates after transformation ensures placement in page space
    cmd = '_-Leader {},{},{} _Multipause "{}"'.format(point.X, point.Y, point.Z, layer_name)
    Rhino.RhinoApp.RunScript(cmd, True)

    sc.doc.Views.Redraw()

if __name__ == "__main__":
    LeaderLayerName()