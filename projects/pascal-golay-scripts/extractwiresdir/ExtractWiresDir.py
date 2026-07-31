"""
ExtractWiresDir.py

Python 3 (CPython) port of ExtractWiresDir.rvb, for Rhino 8's Script
Editor (ScriptEditor command, run with F5). Not for the legacy
RunPythonScript/IronPython 2 engine.

Original by Pascal Golay (McNeel), 2009-03-17.
Original ToDo carried over unresolved: "make it work with singularities."

Extracts a surface's isocurves (wireframe), then keeps only the
isocurves running in the same direction as one the user picks, deleting
the crossing-direction ones. The kept curves are grouped and selected.

Function/API mappings verified 2026 against mcneel/rhinoscriptsyntax
GitHub source (rhino-8.x branch) via WebFetch this session:
  - rs.GetObjectEx(message, filter, preselect, select, objects) is the
    modern equivalent of legacy RhinoScript's GetObject(...,objects)
    5th-argument form that restricted picking to a specific candidate
    list (here, only the isocurves just created by ExtractWireFrame).
    It returns a (id, preselected, selmethod, point, viewname) tuple -
    note this is a 5-tuple (no curve-parameter element), unlike
    GetCurveObject's 6-tuple.
  - rs.CurveCurveIntersection(curveA, curveB) returns a list of
    intersection-event tuples or None if there's no intersection -
    truthiness works directly as a "do they cross" test, matching the
    original's isArray() check.

Deviation from the original: the VBScript passed the full original
isocurve id list (aLast) straight to AddObjectsToGroup/SelectObjects
even though some of those ids had just been deleted in the loop above.
This port filters to rs.IsObject(c) survivors first, since passing a
deleted id to those calls is undefined behavior in the modern API.
"""

import rhinoscriptsyntax as rs


def extract_wires_dir():
    srf_id = rs.GetObject("Select a surface.", rs.filter.surface, True, True)
    if srf_id is None:
        return

    layer = rs.ObjectLayer(srf_id)

    rs.Command("_ExtractWireFrame", False)
    if rs.LastCommandResult() != 0:
        rs.Print("ExtractWireFrame did not succeed.")
        return

    last_ids = rs.LastCreatedObjects()
    if not last_ids:
        rs.Print("No isocurves were extracted.")
        return
    rs.ObjectLayer(last_ids, layer)

    pick = rs.GetObjectEx(
        "Select an isocurve in the direction to keep",
        rs.filter.curve,
        False,
        False,
        last_ids,
    )
    if pick is None:
        return
    keep_curve_id = pick[0]

    rs.EnableRedraw(False)

    for crv_id in list(last_ids):
        if crv_id != keep_curve_id:
            if rs.CurveCurveIntersection(crv_id, keep_curve_id):
                rs.DeleteObject(crv_id)

    remaining_ids = [c for c in last_ids if rs.IsObject(c)]
    group_name = rs.AddGroup()
    rs.AddObjectsToGroup(remaining_ids, group_name)
    rs.SelectObjects(remaining_ids)

    rs.EnableRedraw(True)


if __name__ == "__main__":
    extract_wires_dir()
