"""SelParallelToAxis.py

Python 3 (CPython, PythonNet) port of SelParallelToAxis.rvb, for Rhino 8's
Script Editor (ScriptEditor command, F5). Not written for legacy
IronPython/RunPythonScript.

Original: Pascal Golay, SelParallelToAxis.rvb (2008).
Ported 2026-07-31.

What it does: selects every line-curve in the document whose start/end
points are constant in exactly the two construction-plane axes other
than the one the user picks (X, Y, or Z) -- i.e. lines parallel to that
construction-plane axis. Works entirely on the active view's CPlane, not
world axes, matching the original.

Function names/signatures (ObjectsByType, GetString, IsObjectSelectable,
IsLine, CurveStartPoint, CurveEndPoint, XformWorldToCPlane, ViewCPlane,
SelectObject, EnableRedraw) verified 2026-07-31 against the
rhinoscriptsyntax source on GitHub
(https://github.com/mcneel/rhinoscriptsyntax, rhino-8.x branch,
Scripts/rhinoscript/{selection,userinterface,curve,transformation,view,object}.py).

Bug noted (not carried over): the original's CheckValidArray() had a
missing space, `strToCheck = ""Then` -- a VBScript typo that happens to
still parse (Then is misread as a separate token) but which, if fixed
literally, changes nothing about behavior here since GetString with a
restricted choice list already prevents free-text entry. Not applicable
in Python; rs.GetString(..., strings=[...]) enforces the same choice
restriction, so no equivalent check is needed here.
"""

import rhinoscriptsyntax as rs

_AXES = ["X", "Y", "Z"]


def sel_parallel_to_axis():
    curve_ids = rs.ObjectsByType(4)  # 4 = curve, matches original filter code
    if not curve_ids:
        print("No lines found.")
        return

    axis = rs.GetString("Find lines parallel to Cplane axis.", None, _AXES)
    if axis is None:
        return

    axis = axis.upper()
    if axis not in _AXES:
        print("Invalid axis choice.")
        return

    # expected pattern: True only in the position matching the chosen axis
    expected = [axis == a for a in _AXES]

    cplane = rs.ViewCPlane()

    rs.EnableRedraw(False)
    try:
        for curve_id in curve_ids:
            if not rs.IsObjectSelectable(curve_id):
                continue
            if not rs.IsLine(curve_id):
                continue

            p1 = rs.XformWorldToCPlane(rs.CurveStartPoint(curve_id), cplane)
            p2 = rs.XformWorldToCPlane(rs.CurveEndPoint(curve_id), cplane)
            p1 = [round(p1[i], 8) for i in range(3)]
            p2 = [round(p2[i], 8) for i in range(3)]

            actual = [p1[i] != p2[i] for i in range(3)]

            if actual == expected:
                rs.SelectObject(curve_id)
    finally:
        rs.EnableRedraw(True)


if __name__ == "__main__":
    sel_parallel_to_axis()
