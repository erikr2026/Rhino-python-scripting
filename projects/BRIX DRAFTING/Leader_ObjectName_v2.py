"""Leader_ObjectName_v2.py - streamlined from v1 (November 2024)

Prompts the user to pick an object that has an attribute Name, then drops
a Leader annotation at the pick point whose text is a live ObjectName text
field for that object (i.e. it tracks the object's name if renamed later).

Engine: Python 3 (CPython via PythonNet), run through Rhino's ScriptEditor
command (F5). Not written for RunPythonScript/IronPython 2.

Original attribution (per v1 header): Dale Fugier. The v1 header comment
mentioned "convex hull," which does not describe this script's behavior
(it's leftover boilerplate from a different sample) - corrected here as a
comment-only fix, no behavior change.

Requires Rhino 8.
"""

#! python3
import Rhino
import scriptcontext as sc


def _has_object_name(rhino_object):
    """True if rhino_object is a RhinoObject with a non-empty attribute Name."""
    return (
        isinstance(rhino_object, Rhino.DocObjects.RhinoObject)
        and bool(rhino_object.Attributes.Name)
    )


def _object_name_filter(rhObject, geometry, componentIndex):
    """GetObject custom geometry filter: only allow objects with a Name."""
    return _has_object_name(rhObject)


def _object_name_field(rhino_object):
    """Build the '%<ObjectName(...)>%' text field string for rhino_object.

    Returns None if rhino_object has no attribute Name.
    """
    if not _has_object_name(rhino_object):
        return None
    return '%<ObjectName(\"{}\")>%'.format(rhino_object.Id)


def leader_object_name():
    """Pick a named object and place a Leader annotation showing its name."""
    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt('Select named object')
    go.SetCustomGeometryFilter(_object_name_filter)
    go.EnablePreSelect(False, True)
    go.OneByOnePostSelect = True
    go.InactiveDetailPickEnabled = True
    go.Get()
    if go.CommandResult() != Rhino.Commands.Result.Success:
        return

    objref = go.Object(0)
    rhino_object = objref.Object()
    if rhino_object is None:
        return

    point = objref.SelectionPoint()
    if not point.IsValid:
        return

    rhino_object.Select(False)

    text = _object_name_field(rhino_object)
    if not text:
        return

    # If the pick landed inside a detail view, convert the point from world
    # space to page space so the leader lands in the right spot on the layout.
    detail_sn = objref.SelectionViewDetailSerialNumber()
    if detail_sn > 0:
        detail_obj = sc.doc.Objects.Find(detail_sn)
        if isinstance(detail_obj, Rhino.DocObjects.DetailViewObject):
            w2p = detail_obj.WorldToPageTransform
            point.Transform(w2p)

    cmd = '_-Leader {} _Multipause \"{}\"'.format(point, text)
    Rhino.RhinoApp.RunScript(cmd, True)

    sc.doc.Views.Redraw()


if __name__ == "__main__":
    leader_object_name()
