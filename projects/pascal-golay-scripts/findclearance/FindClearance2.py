"""
FindClearance2.py

Python 3 (CPython, PythonNet bridge) port of FindClearance2.rvb, for Rhino 8's
Script Editor (run via the ScriptEditor command, F5). Do NOT run this through
the legacy RunPythonScript command -- that invokes the IronPython 2 engine.

Original behavior (Pascal Golay, legacy RhinoScript/VBScript):
  - Prompts for two objects (surfaces/polysurfaces): the object to test, and
    the object to test clearance against.
  - Asks for a point on the second object near where clearance should be
    measured.
  - If the two breps actually intersect, highlights the intersection curves
    and reports "Objects intersect."
  - Otherwise "ping-pongs" a point back and forth between the closest points
    on each brep for a fixed 512 iterations, converging on (an estimate of)
    the minimum distance between the two breps near the picked location, then
    reports the estimated clearance in the model's display units and draws a
    line + two points marking the two closest points found.

Porting notes:
  - Rhino.AddStartupScript / Rhino.AddAlias (VBScript session-persistence
    hooks) have no direct rhinoscriptsyntax equivalent for a CPython3 Script
    Editor file, and Script Editor scripts aren't installed as command
    aliases the way old .rvb files were. This port simply defines
    find_clearance() and calls it at the bottom of the file when run
    directly. If you want a reusable Rhino command out of this, wire it up
    via Script Editor's own "Debug"/"Create Command" workflow -- that's a
    separate step outside what this file can set up for itself.
  - Function-name mappings verified 2026 against the mcneel/rhinoscriptsyntax
    GitHub source (rhino-8.x branch): GetObject, GetPointOnSurface,
    IntersectBreps, BrepClosestPoint, SelectObject/SelectObjects, AddLine,
    AddPoint, AddGroup, AddObjectsToGroup, AddObjectToGroup, ObjectsByGroup,
    CurveStartPoint, CurveEndPoint, CurveLength, UnitSystemName,
    UnitDistanceDisplayPrecision, EnableRedraw, Print all exist there with
    the signatures used below.
  - rs.BrepClosestPoint(object_id, point) returns a tuple
    (point, (u, v), (type, index), normal) -- NOT just a point -- so the
    closest point itself is result[0]. This mirrors the VBScript
    `Temp = Rhino.BrepClosestPoint(...): aTemp2 = Temp(0)` pattern exactly.
  - Original bug preserved, not fixed: the ping-pong loop always runs
    exactly 512 iterations before doing anything with the result (the
    VBScript only checks `If i = max` once, right at the last pass), so the
    line/points/print only ever appear after the full 512 passes -- there is
    no early-exit once the two closest points stop moving. Left as-is to
    match original behavior; iteration count and lack of a convergence
    tolerance are exactly as they were in the .rvb.
  - MsgBox calls ported to rs.MessageBox (simple OK dialog) since they were
    pure notifications, not input; this preserves the original modal-popup
    behavior rather than downgrading to a command-line-only message.

Limitation: no live Rhino available in this environment to actually run the
script -- validated only with `python3 -m py_compile` (syntax parses) and a
manual read-through against the rhinoscriptsyntax source. Test in Script
Editor before relying on it.
"""

import rhinoscriptsyntax as rs


def ping_pong(pt, brep1, brep2):
    """Bounce a point back and forth between the closest points on two
    breps for a fixed 512 iterations. Returns the length of the line
    connecting the final two closest points (the estimated clearance), or
    None if something went wrong.

    Mirrors the original PingPong VBScript function, including its fixed
    iteration count and its "only build the line on the very last pass"
    behavior.
    """
    max_iterations = 512
    line_id = None
    last_pt2 = None

    rs.EnableRedraw(False)

    i = 0
    while True:
        temp = rs.BrepClosestPoint(brep1, pt)
        if not temp:
            return None
        pt2 = temp[0]

        temp2 = rs.BrepClosestPoint(brep2, pt2)
        if not temp2:
            return None
        pt = temp2[0]

        i += 1

        if i == max_iterations:
            line_id = rs.AddLine(pt, pt2)
            last_pt2 = pt2
            pt_ids = [
                rs.AddPoint(rs.CurveStartPoint(line_id)),
                rs.AddPoint(rs.CurveEndPoint(line_id)),
            ]
            grp = rs.AddGroup()
            rs.AddObjectsToGroup(pt_ids, grp)
            rs.AddObjectToGroup(line_id, grp)
            rs.ObjectsByGroup(grp, True)

        if i == max_iterations:
            break

    if line_id is not None:
        rs.SelectObject(line_id)
        return rs.CurveLength(line_id)
    return None


def find_clearance():
    units_name = rs.UnitSystemName(capitalize=False, singular=False, abbreviate=True)
    precision = rs.UnitDistanceDisplayPrecision()

    obj_ref = rs.GetObject("Select object to test", 8 + 16, True)
    if obj_ref is None:
        return

    obj_test = rs.GetObject("Select object to test for clearance", 8 + 16)
    if obj_test is None:
        return

    pt = rs.GetPointOnSurface(obj_test, "Click near the closest point")
    if pt is None:
        return

    rs.EnableRedraw(False)

    intersect_result = rs.IntersectBreps(obj_test, obj_ref)
    if intersect_result:
        rs.EnableRedraw(True)
        rs.SelectObjects(intersect_result)
        rs.MessageBox(
            "Objects intersect.\nHighlighting curves of intersection.",
            0,
            "FindClearance2",
        )
        return

    clearance = ping_pong(pt, obj_test, obj_ref)

    rs.EnableRedraw(True)

    if clearance is None:
        rs.Print("Could not determine clearance -- ping-pong calculation failed.")
        return

    msg = "Estimated clearance at this location is {} {}".format(
        round(clearance, precision), units_name
    )
    rs.MessageBox(msg, 0, "FindClearance2")
    rs.Print(msg)


if __name__ == "__main__":
    find_clearance()
