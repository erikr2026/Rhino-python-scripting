"""
CreateOutline.py

Port of CreateOutline.rvb (Pascal Golay, McNeel — legacy RhinoScript/VBScript,
version Friday, December 7, 2007) to Python 3 for Rhino 8's Script Editor
(CPython3 mode). Run via ScriptEditor -> open this file -> F5. NOT for
RunPythonScript (that invokes the IronPython 2 engine).

What it does (unchanged from the original): select curves, run
_CurveBoolean on them with a delete-input mode the user picks (All/Used/
None), and auto-click a "no fill" pick point just outside the curves'
bounding box (offset -10,-10 in the current construction-plane's local X/Y)
so CurveBoolean doesn't need an interactive click.

Porting notes / deliberate simplifications:
- The original used a private module-level "sticky" variable (OldDelete)
  that persists between runs within the same VBScript host session, via
  a `Private` declared at file scope. Python has no direct equivalent for
  a Script Editor run (each F5 press is a fresh module execution), so this
  uses `scriptcontext.sticky` (a dict that persists across script runs in
  the same Rhino session) to reproduce the same "remember my last choice"
  behavior.
- rs.XformCPlaneToWorld(point, plane) / rs.XformWorldToCPlane(point, plane)
  both exist in rhinoscriptsyntax (confirmed 2026-07-31 against the
  rhinoscriptsyntax source, rhino-8.x branch,
  Scripts/rhinoscript/transformation.py) and map 1:1 to the original
  VBScript calls of the same name — used directly below rather than
  reimplementing the conversion by hand.
- rs.BoundingBox(objects, view_or_plane, in_world_coords=False) returns the
  8 corner points in construction-plane-local coordinates when
  in_world_coords is False (confirmed against rhinoscriptsyntax source,
  Scripts/rhinoscript/geometry.py) — matching the original VBScript's use
  of the same flag.
- The original's AddAlias/AddStartupScript calls wire the script up as a
  persistent Rhino command alias ("CreateOutline") that reloads itself at
  Rhino startup. That mechanism is VBScript/RunPythonScript-specific
  (Rhino.AddStartupScript re-registers a .rvb file to auto-load). There is
  no equivalent for a Script Editor Python 3 file — Script Editor scripts
  aren't invoked via command alias in the same way. Omitted; run this file
  directly from Script Editor instead. If you want a persistent alias to
  a Python 3 script, that's set up via Rhino's Options > Aliases UI
  pointing at a `-RunPythonScript "full/path/to/CreateOutline.py"` macro,
  not from inside the script itself.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc


def create_outline():
    curves = rs.GetObjects("Select curves", rs.filter.curve, group=True, preselect=True)
    if not curves:
        return

    old_delete = sc.sticky.get("CreateOutline_OldDelete", "No")
    delete_options = ("All", "Used", "None")
    delete_mode = rs.GetString("Delete input?", old_delete, delete_options)
    if delete_mode is None:
        return
    if delete_mode not in delete_options:
        # GetString with a strings list normally restricts input to that
        # list already; this guard mirrors the original's defensive Filter()
        # check in case of an unexpected value.
        return
    sc.sticky["CreateOutline_OldDelete"] = delete_mode

    view = rs.CurrentView()
    plane = rs.ViewCPlane(view)

    # Bounding box in construction-plane-local coordinates (in_world_coords=False)
    bbox = rs.BoundingBox(curves, view, False)
    if not bbox:
        print("Could not compute a bounding box for the selected curves.")
        return

    bottom_corner = bbox[0]
    offset_pt_cplane = (bottom_corner[0] - 10, bottom_corner[1] - 10, bottom_corner[2])

    # Convert the construction-plane-local point back to world coordinates.
    world_pt = rs.XformCPlaneToWorld(offset_pt_cplane, plane)

    rs.EnableRedraw(False)
    rs.SelectObjects(curves)
    pt_str = "{0},{1},{2}".format(world_pt.X, world_pt.Y, world_pt.Z)
    rs.Command(
        "_CurveBoolean _DeleteInput=_{0} {1} _Enter".format(delete_mode, pt_str),
        False,
    )
    rs.EnableRedraw(True)


if __name__ == "__main__":
    create_outline()
