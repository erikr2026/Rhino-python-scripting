"""Silhouette_VP.py

Python 3 (CPython, PythonNet) port of Silhouette_VP.rvb, for Rhino 8's
Script Editor (ScriptEditor command, F5). Not written for legacy
IronPython/RunPythonScript.

Original: Silhouette_VP.rvb (author field left as the literal template
placeholder "<insert name>" in the source -- not filled in by whoever
saved this copy; the internal Sub is named `SilhouetteEyePt`, and that
is also the alias the .rvb registers, even though the file itself is
named Silhouette_VP.rvb. Preserved the `SilhouetteEyePt` name for the
Python function below for continuity with the original alias.)
Ported 2026-07-31.

What it does: lets the user pick an eye point and a second point that
sets the view direction, temporarily points the active view's camera at
that eye point looking in that direction in parallel projection, runs
Rhino's `_Silhouette` command on the selected objects from that vantage,
then restores the view to whatever it was before.

Function names/signatures (GetObjects, GetPoint, AddPoint, CurrentView,
ViewCameraLens, ViewProjection, AddNamedView, ViewCameraTarget,
SelectObjects, Command, RestoreNamedView, DeleteObject, EnableRedraw,
PointAdd, VectorUnitize, VectorCreate) verified 2026-07-31 against the
rhinoscriptsyntax source on GitHub
(https://github.com/mcneel/rhinoscriptsyntax, rhino-8.x branch,
Scripts/rhinoscript/{selection,userinterface,geometry,view,object,
pointvector}.py).

Bug/quirk noted, preserved rather than silently fixed: the original
computes `lens` and `proj` (the view's current camera lens length and
projection mode) but never uses them for anything -- the commented-out
line `'if proj = 2 then Rhino.ViewCameraLens ...` that would have used
them is dead, commented-out code in the source. Kept as inert local
variables here for parity/traceability, not wired up to anything, same
as the original.

Also note: `Rhino.AddNamedView("crntView", ...)` uses a fixed literal
name every run. Rhino's named-view list allows duplicate names, and
`RestoreNamedView` finds by name, so repeated runs work correctly but
will accumulate multiple identically-named "crntView" entries in the
document's Named Views panel over time. The original does not clean
this up, and this port doesn't either, to avoid changing behavior --
worth knowing if the Named Views list gets cluttered after many runs.
"""

import rhinoscriptsyntax as rs


def silhouette_eye_pt():
    obj_ids = rs.GetObjects("Select objects for Silhouette", 4 + 8 + 16, preselect=True)
    if not obj_ids:
        return

    eye_pt = rs.GetPoint("Set eye point")
    if eye_pt is None:
        return

    temp_pt_id = rs.AddPoint(eye_pt)

    crnt_view = rs.CurrentView()
    lens = rs.ViewCameraLens(crnt_view)  # noqa: F841 -- unused, kept for parity (dead in original too)
    proj = rs.ViewProjection(crnt_view)  # noqa: F841 -- unused, kept for parity (dead in original too)

    dir_pt = rs.GetPoint("Set view direction.", eye_pt)
    if dir_pt is None:
        rs.DeleteObject(temp_pt_id)
        return

    saved_view_name = rs.AddNamedView("crntView", rs.CurrentView())

    rs.EnableRedraw(False)
    try:
        rs.ViewProjection(None, 1)  # 1 = parallel projection
        target_pt = rs.PointAdd(eye_pt, rs.VectorUnitize(rs.VectorCreate(dir_pt, eye_pt)))
        rs.ViewCameraTarget(None, eye_pt, target_pt)

        rs.SelectObjects(obj_ids)
        rs.Command("_Silhouette")

        rs.RestoreNamedView(saved_view_name, crnt_view, True)
        rs.DeleteObject(temp_pt_id)
    finally:
        rs.EnableRedraw(True)


if __name__ == "__main__":
    silhouette_eye_pt()
