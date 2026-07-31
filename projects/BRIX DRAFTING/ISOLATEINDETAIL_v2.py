"""ISOLATEINDETAIL v2 - streamlined version of ISOLATEINDETAIL_v1.py.

Isolates the selected objects inside the active Detail view by hiding
everything else via the native -_HideInDetail command.

Engine: written for Python 3 via Rhino 8's ScriptEditor (F5 to run).
Uses only print()/rhinoscriptsyntax calls that behave the same under
IronPython 2, so it should also run fine via RunPythonScript if needed -
but ScriptEditor/Python 3 is the intended target.

Same behavior as v1; changes are structural/clarity only (see repo
CHANGELOG note from the streamlining pass). No rs.* call signatures or
argument values were altered.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc


def _is_inside_detail():
    """Return True if the active view is a Detail viewport (not the main view)."""
    view = sc.doc.Views.ActiveView
    viewport = view.ActiveViewport
    return view.MainViewport.Id != viewport.Id


def IsolateInDetail():
    """Hide every object except the current selection, scoped to the active Detail.

    Workflow:
      1. Require the active view to be a Detail (double-clicked into it).
      2. Prompt the user to pick the objects to keep visible.
      3. Compute everything else in the document as the "hide" set.
      4. Select the "hide" set and run -_HideInDetail to hide them only
         within this Detail (leaves other Details/model space untouched).
      5. Restore selection to the originally-picked "keep" objects.
    """
    if not _is_inside_detail():
        print("Error: You MUST be double-clicked inside a Detail window.")
        return

    keep_ids = rs.GetObjects("Select objects to ISOLATE in this detail", preselect=True)
    if not keep_ids:
        return

    # Everything visible in the document, minus what we're keeping, gets hidden.
    keep_set = set(keep_ids)
    hide_ids = [obj_id for obj_id in rs.AllObjects() if obj_id not in keep_set]

    if not hide_ids:
        print("Everything is already isolated.")
        return

    rs.EnableRedraw(False)
    try:
        rs.UnselectAllObjects()
        rs.SelectObjects(hide_ids)

        # "-" prefix runs the scripted (dialog-free) version of the command.
        rs.Command("-_HideInDetail _Enter", echo=False)

        # Leave the isolated objects selected, not the ones we just hid.
        rs.UnselectAllObjects()
        rs.SelectObjects(keep_ids)
    except Exception as ex:
        # Surface a plain message instead of a raw traceback on the command line.
        print("Error: IsolateInDetail failed - {0}".format(ex))
        return
    finally:
        rs.EnableRedraw(True)
        rs.Redraw()

    print("Isolate complete using HideInDetail.")


if __name__ == "__main__":
    IsolateInDetail()
