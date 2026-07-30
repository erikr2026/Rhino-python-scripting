# LeaderObjectName.py - Novemeber 2024
# Sample script to create a convex hull using
# If this code works, it was written by Dale Fugier.
# If not, I don't know who wrote it.
# Works with Rhino 8

#! python3
import Rhino
import scriptcontext as sc

#
# GetObject custom geometry filter
#
def __ObjectNameFilter(rhObject, geometry, componentIndex):
    if isinstance(rhObject, Rhino.DocObjects.RhinoObject):
        if rhObject.Attributes.Name:
            return True
    return False

#
# ObjectName text field string formatter
#
def __ObjectNameString(rhObject):
    rc = None
    if isinstance(rhObject, Rhino.DocObjects.RhinoObject):
        if rhObject.Attributes.Name:
            rc = '%<ObjectName(\"{}\")>%'.format(rhObject.Id)
    return rc

#
# Main function
#
def LeaderObjectName():
    # Pick an object that has a attribute name
    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt('Select named object')
    go.SetCustomGeometryFilter(__ObjectNameFilter)
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

    objref.Object().Select(False)

    # Format a text field string
    text = __ObjectNameString(objref.Object())
    if not text:
        return

    detail_sn = objref.SelectionViewDetailSerialNumber()
    if detail_sn > 0:
        detail_obj = sc.doc.Objects.Find(detail_sn)
        if isinstance(detail_obj, Rhino.DocObjects.DetailViewObject):
            w2p = detail_obj.WorldToPageTransform
            point.Transform(w2p)

    cmd = '_-Leader {} _Multipause \"{}\"'.format(point, text)
    Rhino.RhinoApp.RunScript(cmd, True)

    sc.doc.Views.Redraw()

# Check to see if this file is being executed as the "main" python
# script instead of being used as a module by some other python script
# This allows us to use the module which ever way we want.
if __name__ == "__main__":
    LeaderObjectName()
    