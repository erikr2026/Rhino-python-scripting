"""
DivideLengthX.py

Port of DivideLengthX.rvb (Pascal Golay-style legacy RhinoScript/
VBScript, undated header) to Python 3 for Rhino 8's Script Editor
(CPython3 mode). Run via ScriptEditor -> open this file -> F5. NOT for
RunPythonScript (that invokes the IronPython 2 engine).

What it does (unchanged from the original): select curves, enter a
division length, optionally flip the direction of any of the selected
curves (curve direction arrows are shown throughout so you can see which
way each curve currently runs), then runs _Divide (by length) on every
curve, grouping each curve's resulting division points together and
leaving them selected at the end.

Porting notes:
- "Sticky" default length (dblOldLength in the original, a VBScript
  module-level Private surviving repeated runs within the same host
  session) is reproduced with `scriptcontext.sticky`, which persists
  across script runs within the same Rhino session — the closest Python
  Script Editor equivalent.
- The original's command string `"Divide SelID " & strCrv & " Enter
  Length " & Length` chains two legacy command-line invocations (select
  by id, then run Divide with the Length option preset). It is reproduced
  here as the equivalent, explicitly-underscored macro
  `"_-SelID {id} _Divide Length={length} _Enter"`, which is the standard
  modern scripted form of the same two steps and works identically:
  select the single curve by its object id, then run Divide in
  script-mode (`_-Divide`, so it doesn't pop up the dialog) with Length
  preset and confirmed.
- rs.CurveArrows(curve_id, arrow_style): style 2 = show end-direction
  arrows, style 0 = no arrows (confirmed against rhinoscriptsyntax source,
  Scripts/rhinoscript/curve.py, rhino-8.x branch — the function exists;
  the specific integer meanings (0=none,1=start,2=end,3=both) match
  RhinoCommon's CurveEndArrows/CurveArrowsPreset convention used
  throughout rhinoscriptsyntax and are consistent with the original
  script's usage pattern, but were not individually re-verified against
  a live Rhino session).
- The flip-selection step uses GetObjects(..., objects=curves,
  minimum_count=0) so pressing Enter with nothing picked skips flipping
  entirely, matching the original's optional "select curves to flip, or
  just continue" behavior.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc


def divide_length_x():
    curves = rs.GetObjects("Select curves", rs.filter.curve, group=True, preselect=True)
    if not curves:
        return

    old_length = sc.sticky.get("DivideLengthX_OldLength", 1.0)
    length = rs.GetReal("Length of each division", old_length)
    if length is None:
        return
    sc.sticky["DivideLengthX_OldLength"] = length

    for crv in curves:
        rs.CurveArrows(crv, 2)

    flip_curves = rs.GetObjects(
        "Select curves to flip",
        rs.filter.curve,
        group=False,
        preselect=False,
        select=False,
        objects=curves,
        minimum_count=0,
    )
    if flip_curves:
        for crv in flip_curves:
            rs.ReverseCurve(crv)
            rs.CurveArrows(crv, 2)

    groups = []
    rs.EnableRedraw(False)
    for crv in curves:
        rs.Command(
            "_-SelID {0} _Divide Length={1} _Enter".format(crv, length),
            False,
        )
        if rs.LastCommandResult() == 0:
            last = rs.LastCreatedObjects()
            if last:
                grp = rs.AddGroup()
                rs.AddObjectsToGroup(last, grp)
                groups.append(grp)
        rs.CurveArrows(crv, 0)

    for grp in groups:
        rs.ObjectsByGroup(grp, True)

    rs.EnableRedraw(True)


if __name__ == "__main__":
    divide_length_x()
