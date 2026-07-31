# -*- coding: utf-8 -*-

"""
Rhino Python Script (Rhino 8 & 9)
Colors selected Brep (polysurface) faces blue (RGB: 0, 0, 255).
Supports pre-selection, multi-selection, and automatic Extrusion-to-Brep conversion.

Engine: Python 3 (CPython, via ScriptEditor / F5) or IronPython 2 (RunPythonScript) -
this script uses no syntax specific to either engine and no non-ASCII source bytes,
so it runs unmodified under both.
"""

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System.Drawing

# Target face color: RGB (0, 0, 255) - pure blue.
TARGET_COLOR = System.Drawing.Color.FromArgb(0, 0, 255)


def main():
    """Prompt for Brep/Extrusion face(s) (pre-selection or interactive pick),
    color each selected face TARGET_COLOR, and replace the modified geometry
    in the document as a single undo step."""

    # Create a custom GetObject command to select subobject surfaces/faces
    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt("Select Brep faces to color blue (255)")
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Surface
    go.SubObjectSelect = True
    go.EnablePreSelect(True, True)

    # Get the user selection
    go.GetMultiple(1, 0)

    if go.CommandResult() != Rhino.Commands.Result.Success:
        print("Selection cancelled.")
        return

    obj_refs = go.Objects()
    if not obj_refs:
        print("No faces selected.")
        return

    # Group picked face indices by parent object id, so each object is only
    # duplicated/replaced once even if multiple faces on it were selected.
    grouped_changes = {}

    for ref in obj_refs:
        rh_obj = ref.Object()
        if not rh_obj:
            continue

        comp_index = ref.GeometryComponentIndex
        # Ensure we are dealing with a BrepFace subobject
        if comp_index.ComponentIndexType == Rhino.Geometry.ComponentIndexType.BrepFace:
            face_idx = comp_index.Index
            obj_id = rh_obj.Id

            if obj_id not in grouped_changes:
                grouped_changes[obj_id] = {
                    "rh_obj": rh_obj,
                    "face_indices": []
                }
            grouped_changes[obj_id]["face_indices"].append(face_idx)

    if not grouped_changes:
        print("No valid Brep faces were selected.")
        return

    # Wrap in an Undo record so the operation can be undone in a single step
    undo_record = sc.doc.BeginUndoRecord("Color Selected Faces Blue")
    rs.EnableRedraw(False)

    modified_faces = 0
    modified_objects = 0

    try:
        for obj_id, data in grouped_changes.items():
            rh_obj = data["rh_obj"]
            face_indices = data["face_indices"]
            geom = rh_obj.Geometry

            # Determine geometry type and duplicate to modify
            brep = None
            if isinstance(geom, Rhino.Geometry.Brep):
                brep = geom.Duplicate()
            elif isinstance(geom, Rhino.Geometry.Extrusion):
                # Convert extrusion to Brep to support per-face colors
                brep = geom.ToBrep()

            if not brep:
                continue

            # Assign color to each selected face index
            for idx in face_indices:
                if 0 <= idx < brep.Faces.Count:
                    brep.Faces[idx].PerFaceColor = TARGET_COLOR
                    modified_faces += 1

            # Replace the document geometry with the modified version
            if sc.doc.Objects.Replace(obj_id, brep):
                modified_objects += 1

    except Exception as ex:
        print("An error occurred during execution: {}".format(str(ex)))

    finally:
        # Deselect all elements so the blue color is immediately visible without selection highlights
        sc.doc.Objects.UnselectAll(True)
        sc.doc.EndUndoRecord(undo_record)
        rs.EnableRedraw(True)
        sc.doc.Views.Redraw()

    # Provide clear operational command-line feedback for shop fabrication validation
    feedback_msg = "Successfully colored {} face(s) across {} polysurface(s) blue."
    print(feedback_msg.format(modified_faces, modified_objects))


if __name__ == "__main__":
    main()
