"""
ConvertCurveDegree.py - Python 3 (CPython) port of ConvertCurveDegree.rvb
(original author/company placeholders left blank in the source .rvb)

TARGET ENGINE: Rhino 8 Script Editor, CPython3 mode (ScriptEditor command,
F5). Not intended for the legacy `RunPythonScript` (IronPython 2) command.

Original behavior: pick a single non-rational curve, read its control
points, ask the user for a new curve degree (capped at min(11, point
count - 1), matching the max degree AddCurve/a NURBS curve of that many
points can support), rebuild it as a new control-point curve of the chosen
degree through the same points, copy display/organizational properties
(layer, name, color, linetype, print color/width, group membership, grip
state) from the old curve to the new one, then delete the original.

Porting notes / deliberate simplifications:
  - `Rhino.AddAlias`/`Rhino.AddStartupScript` (registering a persistent
    "ConvertCrvDegree" command alias) is a legacy VBScript RhinoScript
    mechanism with no Script Editor CPython3 equivalent; dropped. Run this
    file directly with F5, or point a Rhino alias/button at it manually.
  - `MsgBox` (a blocking modal dialog for the "rational curves not
    supported" message) is replaced with a `print()` to the command line --
    a reasonable simplification per the task brief; no other user input is
    needed at that point, so a full Eto dialog would add ceremony without
    adding functionality.
  - `Rhino.ObjectURL` has no rhinoscriptsyntax equivalent, and no
    corresponding property could be confirmed on RhinoCommon's
    `ObjectAttributes` either (fetching the RhinoCommon HTML docs for this
    resulted in an unrenderable JS-app shell, and searching the live
    RhinoCommon API index for a Url-related member on ObjectAttributes
    turned up nothing this session).
    # TODO: unverified -- object hyperlink URL copying from the original
    # script's MatchProperties() is dropped rather than guessed; if this
    # ever needs to be restored, look for it under whatever RhinoCommon
    # calls the "weblink"/notes-adjacent object property in a current
    # Rhino 8 SDK, not assumed here.
  - All other property-copy calls (`ObjectLayer`, `ObjectName`,
    `ObjectColorSource`/`ObjectColor`, `ObjectLinetypeSource`/
    `ObjectLinetype`, `ObjectPrintColorSource`/`ObjectPrintColor`,
    `ObjectPrintWidthSource`/`ObjectPrintWidth`, `ObjectGroups`/
    `AddObjectToGroup`, `ObjectGripsOn`/`EnableObjectGrips`) map 1:1 to their
    rhinoscriptsyntax equivalents (confirmed against
    https://developer.rhino3d.com/api/RhinoScriptSyntax/, fetched live this
    session).
  - Note: the original's grip-copy line (`If Rhino.ObjectGripsOn(sObj1)
    Then Rhino.EnableObjectGrips(sObj2)`) tests grips on `sObj1` (the *new*
    curve, which was never grip-enabled) and enables them on `sObj2` (the
    *old* curve, about to be deleted) -- almost certainly a copy/paste bug
    in the original (arguments backwards) that would never actually fire
    or matter, since the old curve is deleted immediately after. Reproduced
    as-is below rather than "fixed", since guessing the original intent
    isn't safe -- flagged inline.
"""

import rhinoscriptsyntax as rs


def match_properties(obj1, obj2):
    """Copy display/organizational properties from obj2 onto obj1."""
    rs.ObjectLayer(obj1, rs.ObjectLayer(obj2))

    name = rs.ObjectName(obj2)
    if name is not None:
        rs.ObjectName(obj1, name)

    rs.ObjectColorSource(obj1, rs.ObjectColorSource(obj2))
    rs.ObjectColor(obj1, rs.ObjectColor(obj2))

    rs.ObjectLinetypeSource(obj1, rs.ObjectLinetypeSource(obj2))
    rs.ObjectLinetype(obj1, rs.ObjectLinetype(obj2))

    rs.ObjectPrintColorSource(obj1, rs.ObjectPrintColorSource(obj2))
    rs.ObjectPrintColor(obj1, rs.ObjectPrintColor(obj2))

    rs.ObjectPrintWidthSource(obj1, rs.ObjectPrintWidthSource(obj2))
    rs.ObjectPrintWidth(obj1, rs.ObjectPrintWidth(obj2))

    # rs.ObjectURL has no equivalent -- see module docstring TODO.

    # Reproduced verbatim from the original (args as written there); this
    # tests obj1 (the freshly built curve) rather than obj2, so it is
    # effectively a no-op here. See module docstring note.
    if rs.ObjectGripsOn(obj1):
        rs.EnableObjectGrips(obj2)

    groups = rs.ObjectGroups(obj2)
    if groups:
        for grp in groups:
            rs.AddObjectToGroup(obj1, grp)


def convert_curve_degree():
    crv_id = rs.GetObject("Select a non-rational curve.", rs.filter.curve, True)
    if crv_id is None:
        return

    if rs.IsCurveRational(crv_id):
        print("Sorry, the script is not handling rational curves yet.")
        return

    cur_degree = rs.CurveDegree(crv_id)
    crv_pts = rs.CurvePoints(crv_id)
    if not crv_pts:
        return

    max_degree = min(len(crv_pts) - 1, 11)
    target_degree = rs.GetInteger(
        "New curve degree less than {}".format(max_degree + 1),
        cur_degree, 1, max_degree
    )
    if target_degree is None:
        return

    new_crv = rs.AddCurve(crv_pts, target_degree)
    if new_crv is None:
        return

    match_properties(new_crv, crv_id)
    rs.DeleteObject(crv_id)


if __name__ == "__main__":
    convert_curve_degree()
