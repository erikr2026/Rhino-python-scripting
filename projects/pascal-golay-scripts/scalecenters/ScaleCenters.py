"""ScaleCenters.py

Python 3 (CPython, PythonNet) port of ScaleCenters.rvb, for Rhino 8's
Script Editor (ScriptEditor command, F5). Not written for legacy
IronPython/RunPythonScript.

Original: Pascal Golay, ScaleCenters.rvb (2009).
Ported 2026-07-31.

What it does: scales a set of objects "in place" by moving only the
centers of their bounding boxes by a scale factor, without scaling the
objects themselves. It does this by placing a temporary point at each
object's bounding-box center, running Rhino's interactive _Scale1D /
_Scale2D / _Scale command on those points (so the user gets Rhino's
normal dynamic scale preview/base-point/reference-point prompting),
then moving each original object from its old center to the scaled
point location.

Function names/signatures (BoundingBox, GetString, GetObjects, AddPoint,
SelectObjects, Command, LastCommandResult, PointCoordinates, MoveObject,
DeleteObjects, EnableRedraw) verified 2026-07-31 against the
rhinoscriptsyntax source on GitHub
(https://github.com/mcneel/rhinoscriptsyntax, rhino-8.x branch,
Scripts/rhinoscript/{geometry,selection,userinterface,application,object}.py).

Known quirk carried over from the original (not a bug I introduced):
the scale-type prompt list is the literal strings "OneD", "Two2D", "3D"
(not "1D"/"2D"/"3D") -- that's what the original GetString choice list
used, so it's kept verbatim for behavioral parity. Type one of those
three (or just hit Enter for the default) at the command-line prompt.
"""

import rhinoscriptsyntax as rs

_SCALE_CHOICES = ["OneD", "Two2D", "3D"]


def scale_from_centers(scale_index):
    """scale_index: 0 = Scale1D, 1 = Scale2D, 2 (or anything else) = Scale (3D)."""

    obj_ids = rs.GetObjects("Select objects", preselect=True)
    if not obj_ids:
        return

    centers = []
    center_pt_ids = []

    for obj_id in obj_ids:
        bbox = rs.BoundingBox(obj_id, rs.CurrentView())
        if not bbox:
            print("Could not compute a bounding box for one of the selected objects. Skipping it.")
            centers.append(None)
            center_pt_ids.append(None)
            continue
        # bbox is 8 corner points, counter-clockwise starting at the bottom
        # rectangle; corner 6 is diagonally opposite corner 0, so their
        # average is the box center -- same indexing the original .rvb used.
        cx = (bbox[0].X + bbox[6].X) / 2.0
        cy = (bbox[0].Y + bbox[6].Y) / 2.0
        cz = (bbox[0].Z + bbox[6].Z) / 2.0
        center = (cx, cy, cz)
        centers.append(center)
        center_pt_ids.append(rs.AddPoint(center))

    if not any(center_pt_ids):
        print("No valid objects to scale.")
        return

    rs.UnselectAllObjects()
    valid_pt_ids = [pid for pid in center_pt_ids if pid is not None]
    rs.SelectObjects(valid_pt_ids)

    if scale_index == 0:
        rs.Command("_Scale1D", echo=True)
    elif scale_index == 1:
        rs.Command("_Scale2D", echo=True)
    else:
        rs.Command("_Scale", echo=True)

    if rs.LastCommandResult() != 0:
        rs.DeleteObjects(valid_pt_ids)
        return

    rs.EnableRedraw(False)
    try:
        for i, obj_id in enumerate(obj_ids):
            if centers[i] is None or center_pt_ids[i] is None:
                continue
            new_pt = rs.PointCoordinates(center_pt_ids[i])
            rs.MoveObject(obj_id, rs.PointSubtract(new_pt, centers[i]))
        rs.DeleteObjects(valid_pt_ids)
    finally:
        rs.EnableRedraw(True)


def scale_centers():
    scale_type = rs.GetString("Scale type", "3D", _SCALE_CHOICES)
    if scale_type is None:
        return

    try:
        scale_index = _SCALE_CHOICES.index(scale_type)
    except ValueError:
        # case-insensitive fallback, matching original StringInArray(...,0)
        lowered = [s.lower() for s in _SCALE_CHOICES]
        try:
            scale_index = lowered.index(scale_type.lower())
        except ValueError:
            return

    scale_from_centers(scale_index)


if __name__ == "__main__":
    scale_centers()
