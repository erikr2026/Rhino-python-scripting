"""Project_Direction.py
Ported from Project_Direction.rvb (Pascal Golay, no header date in
original file).

Target engine: Rhino 8 Script Editor, CPython3 mode (run via F5, NOT the
legacy `RunPythonScript` command).

Original behavior: Rhino's `_Project` command always projects along the
active viewport's CPlane normal. This script works around that by
temporarily re-pointing the active view's CPlane at a user-chosen
direction, running `_Project`, and then restoring the view's original
CPlane -- giving three effective commands (all defined as one-arg-only
`Project(pdir)` internally in the original, but exposed as three separate
command aliases):
  - ProjectDir():    project selected curves/points onto chosen target
                      surfaces/polysurfaces/meshes along a direction
                      defined by two user-picked points.
  - ProjectView():    same, but the projection direction is the CURRENT
                      camera's view direction (`ViewCameraPlane`) instead
                      of two picked points.
  - TrimFromView():   temporarily aims the view's CPlane at the camera
                      plane and forces the view to parallel/orthographic
                      projection (so `_Trim` behaves like a view-based
                      trim), runs `_Trim`, then restores both the
                      original CPlane and the original projection mode.

Both Project() variants build the actual `_Project` command string by
appending `_SelID <guid>` for every target object (rather than passing
target GUIDs as points/objrefs), then a couple of `_Enter`s to accept the
command's prompts -- reproduced identically here since it is a valid,
working way to drive `_Project` from script.

The `Rhino.AddStartupScript` / `Rhino.AddAlias` lines at the top of the
.rvb are legacy alias-registration mechanics with no equivalent need in a
Script Editor Python file, so they are omitted here (see ENTRY POINT NOTE
below for how the three commands are exposed instead).

ENTRY POINT NOTE (a deliberate simplification, not a GUI choice): the
original registers 3 separate command aliases so each could be typed
independently at Rhino's command line. A single Script Editor .py file
has one natural F5 entry point; this port keeps all three as top-level
functions and prompts on the command line for which one to run when the
file is executed directly (a plain `rs.GetString` menu, not a dialog --
this is a one-off dispatch choice, not something worth a whole Eto.Forms
window for). Comment out the dispatcher and call one function directly if
you always want the same one.

BUG FIXED, not silently carried forward -- flagged explicitly:
  In the original `Project` sub's `pdir = 0` branch, `arrPts(0)` and
  `arrPts(1)` are read to set `Pt1`/`Pt2` BEFORE the
  `If Not IsArray(arrPts) Then Exit Sub` cancel check that follows them.
  If the user cancels the two-point pick, `Rhino.GetPoints` returns Null,
  and indexing `arrPts(0)` on a Null value would raise a VBScript runtime
  type-mismatch error rather than a clean exit. This port moves the
  "did the user cancel" check before using the result, which is the
  evident intent (the check exists, it's just misplaced) and avoids the
  Python equivalent (`TypeError`/`IndexError` on `None`) entirely rather
  than reproducing a crash.

API notes verified live against the mcneel/rhinoscriptsyntax GitHub source
(raw.githubusercontent.com/mcneel/rhinoscriptsyntax/master/Scripts/
rhinoscript/*.py) on this date:
  - rs.ViewProjection(view=None, mode=None): mode 1 = parallel,
    2 = perspective, 3 = two-point perspective -- matches the original's
    hard-coded `1` for "force parallel projection."
  - rs.LastCommandResult() returns 0 for success (matches the original's
    `= 0` check) and rs.LastCreatedObjects() returns the ids created by
    the last command -- both confirmed to exist, argument-free.
  - rs.ViewCameraPlane(view=None) and rs.CurrentView(view=None,
    return_name=True) exist with this exact argument shape.
"""

import rhinoscriptsyntax as rs


def _do_project(use_view_direction):
    a_projection_filter = 1 + 4    # point + curve
    a_target_filter = 8 + 16 + 32  # surface + polysurface + mesh

    crnt_plane = rs.ViewCPlane()
    view = rs.CurrentView()

    to_project = rs.GetObjects(
        "Select curves and points to project", a_projection_filter,
        preselect=True, select=True)
    if not to_project:
        return

    targets = rs.GetObjects(
        "Select surfaces, polysurfaces or meshes to project onto",
        a_target_filter, preselect=True, select=True, group=True)
    if not targets:
        return

    rs.EnableRedraw(False)
    try:
        if use_view_direction:
            plane = rs.ViewCameraPlane(view)
        else:
            pts = rs.GetPoints(
                draw_lines=True, message1="First direction point",
                message2="Second direction point", max_points=2)
            # Cancel check moved before use -- see BUG FIXED note above.
            if not pts or len(pts) < 2:
                return
            vec = rs.VectorCreate(pts[1], pts[0])
            plane = rs.PlaneFromNormal(pts[0], vec)

        if plane is None:
            print("Project_Direction: could not determine a projection plane -- aborted.")
            return

        rs.ViewCPlane(view, plane)

        rs.UnselectAllObjects()
        rs.SelectObjects(to_project)
        rs.CurrentView(view)

        rs.SelectObjects(targets)
        cmd = "_Project "
        for target_id in targets:
            cmd += "_SelID {0} ".format(target_id)
        cmd += "_Enter _Enter"

        rs.Command(cmd, False)

        if rs.LastCommandResult() == 0:
            new_ids = rs.LastCreatedObjects()
            rs.UnselectAllObjects()
            if new_ids:
                rs.SelectObjects(new_ids)
            rs.ViewCPlane(view, crnt_plane)
    finally:
        rs.EnableRedraw(True)


def project_dir():
    """Project selected curves/points onto target objects along a
    direction defined by two user-picked points."""
    _do_project(use_view_direction=False)


def project_view():
    """Project selected curves/points onto target objects along the
    current view's camera direction."""
    _do_project(use_view_direction=True)


def trim_from_view():
    """Temporarily aim the view's CPlane at the camera plane and force
    parallel projection so `_Trim` behaves like a view-based trim, then
    restore the original CPlane and projection mode."""
    crnt_plane = rs.ViewCPlane()
    view = rs.CurrentView()

    plane = rs.ViewCameraPlane(view)
    if plane is None:
        print("Project_Direction: could not determine the view's camera plane -- aborted.")
        return

    rs.ViewCPlane(view, plane)
    idx = rs.ViewProjection(view)
    if idx != 1:
        rs.ViewProjection(view, 1)

    rs.Command("_Trim", True)

    rs.ViewCPlane(view, crnt_plane)
    rs.ViewProjection(view, idx)


if __name__ == "__main__":
    choice = rs.GetString(
        "Which command", "ProjectDir",
        ["ProjectDir", "ProjectView", "TrimFromView"])
    if choice == "ProjectDir":
        project_dir()
    elif choice == "ProjectView":
        project_view()
    elif choice == "TrimFromView":
        trim_from_view()
