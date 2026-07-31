# -*- coding: utf-8 -*-

"""
Rhino Python Script (Rhino 8 & 9) - run via ScriptEditor (Python 3) or
RunPythonScript (IronPython 2); no engine-specific syntax is used here.

Inverts visibility of objects based on subobject face colors.
Any Brep with at least one blue (RGB 0,0,255) face is shown (isolated).
All other objects that do not contain a blue face are hidden.

Streamlined from "JOINERY ISOLATE BLUE WIP.py": same behavior, one pass
over the document instead of three (classify+collect, then two more loops
to show/hide), and the target color is a single named constant instead of
three loose R/G/B locals. No functional change.
"""

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System.Drawing

TARGET_COLOR = System.Drawing.Color.FromArgb(0, 0, 255)  # blue face marker


def has_blue_face(geom):
    """Return True if geom is a Brep with at least one face colored TARGET_COLOR."""
    if not isinstance(geom, Rhino.Geometry.Brep):
        return False
    for face in geom.Faces:
        color = face.PerFaceColor
        # Unset face colors return Color.Empty, which has IsEmpty set to True.
        if color.IsEmpty:
            continue
        # Compare raw RGB values to avoid alpha channel mismatch issues.
        if color.R == TARGET_COLOR.R and color.G == TARGET_COLOR.G and color.B == TARGET_COLOR.B:
            return True
    return False


def main():
    undo_record = sc.doc.BeginUndoRecord("Invert Hide Non-Blue Face Objects")
    rs.EnableRedraw(False)

    # Retrieve all physical objects in the active model database, including
    # hidden/locked ones, so previously-hidden blue objects can be revealed
    # and previously-shown non-blue objects can be hidden.
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.ActiveObjects = True
    settings.HiddenObjects = True
    settings.LockedObjects = True

    shown_count = 0
    hidden_count = 0

    for obj in sc.doc.Objects.GetObjectList(settings):
        # Skip system, helper, or grip objects.
        if not obj or obj.IsDeleted:
            continue

        if has_blue_face(obj.Geometry):
            # Ensure target objects are visible (even if locked).
            if not obj.Visible:
                sc.doc.Objects.Show(obj.Id, True)
                shown_count += 1
        else:
            # Hide non-target objects that are currently visible.
            if obj.Visible:
                sc.doc.Objects.Hide(obj.Id, True)
                hidden_count += 1

    sc.doc.EndUndoRecord(undo_record)
    rs.EnableRedraw(True)
    sc.doc.Views.Redraw()

    # Provide shop-floor operational command-line feedback.
    print("Isolate Complete: Revealed {} blue-faced object(s); hid {} other object(s).".format(
        shown_count, hidden_count))


if __name__ == "__main__":
    main()
