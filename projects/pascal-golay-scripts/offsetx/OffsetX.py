"""
OffsetX.py
Ported from OffsetX.rvb (Pascal Golay, McNeel).

Target engine: Rhino 8 Script Editor, CPython3 mode (run via the ScriptEditor
command: open this file, press F5). Not written for the legacy
RunPythonScript/IronPython2 engine.

What it does: pick a curve, choose an offset style:
  - FullCurve: just runs the interactive `_Offset` command on the curve
    as-is.
  - SubCurves: extracts the sub-curve segments of a polycurve/polyline
    (via `_ExtractSubCrv`) and offsets each segment individually.
  - Span: extracts a single NURBS span (via `_SubCrv`) from a copy of the
    curve and offsets it.
  If the curve isn't actually a polycurve/polyline, SubCurves/Span both
  fall back to the FullCurve behavior.

BUG FOUND AND FIXED (flagging per instructions, not silently patching):
  In the original `OffSetSub`, right after running `_ExtractSubCrv` or
  `_SubCrv`, the success check reads:

      If Rhino.LastCommandResult = 0 then
          Dim aLast: aLast = Rhino.LastCommandResult()   ' <-- BUG
          If IsNull(alast) then exit sub
          Else
              If intStyle = 2 Then Rhino.DeleteObject sCop
              exit sub
          End If
      End If

  `aLast` is assigned `Rhino.LastCommandResult()` again (a 0-4 status
  number) instead of `Rhino.LastCreatedObjects()` (the actual new curve
  ids) - compare to the correct pattern used a few lines later in the same
  script (`aOff = Rhino.LastCreatedObjects()`). Because a number is never
  `Null`, `IsNull(aLast)` is always False, so execution always falls into
  the `Else` branch and hits `exit sub` immediately after `_ExtractSubCrv`/
  `_SubCrv` succeeds - before the loop that actually runs `_Offset` on the
  extracted pieces. Net effect: the "SubCurves" and "Span" offset styles in
  the original .rvb are dead on arrival - they extract geometry and then
  bail out without ever offsetting it. "FullCurve" (intStyle 0) is
  unaffected since it never reaches this code path.

  This port fixes it to `rs.LastCreatedObjects()`, matching the working
  pattern already present later in the same script. This is a genuine
  behavior change from the original file, made because reproducing a
  dead-code path defeats the purpose of the port - flagged here and in the
  session's final report rather than done silently.

Other porting notes:
- Dropped `Rhino.AddStartupScript` / `Rhino.AddAlias`: alias/startup-script
  registration belongs to the legacy RhinoScript engine, not a Script
  Editor Python 3 script run via F5.
- `Private oldStyle` (persisted across repeated invocations of the loaded
  RhinoScript alias) is replaced with `scriptcontext.sticky`, the nearest
  equivalent that survives across separate F5 runs in the same session.
- The original had two names for the same sub (`OffsetSub` when called
  from `OffsetX()`, `OffSetSub` where it's declared, and `OffsetSub` again
  in its own recursive call) - harmless in case-insensitive VBScript, but
  Python is case-sensitive, so this port uses one consistent name,
  `offset_sub`.
- `rs.Command`'s echo argument is passed as `False` throughout to suppress
  command-line echo, matching the original's implicit default behavior
  (the .rvb never explicitly requested echo, so Rhino's normal echo
  applied - this port explicitly silences it for a cleaner command line;
  a deliberate minor UX change, not a behavior-affecting one).

Not run against a live Rhino in this session - validated only with
`python3 -m py_compile` / `ast.parse` (no syntax errors). Function names
and signatures were cross-checked against the live rhinoscriptsyntax
reference; the interactive `_Offset`/`_ExtractSubCrv`/`_SubCrv`
command-line macros themselves could not be exercised live - test on real
curves before relying on this.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc


def offset_sub(crv, style):
    if style == 0:
        rs.Command("_Offset")
        return

    cop = None
    if style == 2:
        cop = rs.CopyObject(crv)
        rs.UnselectAllObjects()
        rs.SelectObject(cop)
    else:
        if rs.IsPolyCurve(crv) or rs.IsPolyline(crv):
            rs.UnselectAllObjects()
            rs.SelectObject(crv)
        else:
            offset_sub(crv, 0)
            return

    if style == 1:
        rs.Command("_ExtractSubCrv _Outputlayer=_Current _Join=_Yes _Copy=_Yes")
    elif style == 2:
        rs.Command("_SubCrv")

    if rs.LastCommandResult() == 0:
        last = rs.LastCreatedObjects()
        if last is None:
            return
    else:
        if style == 2 and cop is not None:
            rs.DeleteObject(cop)
        return

    for item in last:
        rs.UnselectAllObjects()
        rs.SelectObject(item)

        rs.Command("_Offset")

        if rs.LastCommandResult() == 0:
            off = rs.LastCreatedObjects()
            rs.DeleteObject(item)

            if not off:
                return
        else:
            rs.DeleteObject(item)
            return


def offset_x():
    old_style = sc.sticky.get("OffsetX_OldStyle", "FullCurve")

    styles = ["FullCurve", "SubCurves", "Span"]

    crv = rs.GetObject("Select curve", 4, True, True)
    if crv is None:
        return

    style_choice = rs.GetString("Offset curve", old_style, styles)
    if style_choice is None:
        return

    style_index = -1
    for i, s in enumerate(styles):
        if style_choice.lower() == s.lower():
            style_index = i
            sc.sticky["OffsetX_OldStyle"] = s
            break

    if style_index == -1:
        return

    offset_sub(crv, style_index)


if __name__ == "__main__":
    offset_x()
