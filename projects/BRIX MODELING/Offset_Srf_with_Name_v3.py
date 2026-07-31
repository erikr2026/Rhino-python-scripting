# -*- coding: utf-8 -*-
"""
REVERSED OFFSET TOOL (ROUND CORNERS & MERGED FACES) - v3, streamlined
Inverts offset direction: Positive = Inward, Negative = Outward.
Rounds offset gaps (extend=False) and merges coplanar faces on the result.

Target: Rhino 8/9, Python 3 script engine (run via ScriptEditor / F5).
Same behavior as v2; refactored into helper functions, added docstrings,
and closed a couple of latent null/leak bugs (see CHANGELOG notes).
"""
import rhinoscriptsyntax as rs
import Rhino
import scriptcontext as sc
import System


def get_valid_selection():
    """Return object ids for the current/picked surfaces & polysurfaces, or None."""
    ids = rs.SelectedObjects()
    if not ids:
        ids = rs.GetObjects("Select surfaces/polysurfaces to offset",
                            rs.filter.surface | rs.filter.polysurface)
    if not ids:
        print("No valid geometry selected.")
        return None

    valid_ids = [oid for oid in ids if rs.IsSurface(oid) or rs.IsPolysurface(oid)]
    if not valid_ids:
        print("Selection does not contain valid surfaces or polysurfaces.")
        return None
    return valid_ids


def get_offset_distance():
    """Prompt for offset distance; return the inverted (API-ready) value, or None if cancelled."""
    distance = rs.GetReal("Enter offset distance (Positive = Inward, Negative = Outward)", 1.0)
    if distance is None:
        return None
    # Invert for internal API requirements (positive user input = inward offset)
    return -distance


def offset_and_add(obj_id, offset_dist, solid, extend, tolerance, angle_tolerance, layer):
    """
    Offset one surface/polysurface, merge coplanar faces on each result piece,
    and add it to the document on the given layer with the source object's name
    (falling back to "Offset_Obj").

    Returns the number of new objects created for this source object.
    """
    brep = rs.coercebrep(obj_id)
    if not brep:
        return 0

    created = 0
    try:
        # PythonNet maps 'out' parameters to a tuple: (Brep[], outBlends, outWalls)
        offset_result = Rhino.Geometry.Brep.CreateOffsetBrep(
            brep, offset_dist, solid, extend, tolerance
        )

        if offset_result and offset_result[0]:
            original_name = rs.ObjectName(obj_id)
            for b in offset_result[0]:
                if not b:
                    continue
                # Required modification: merge all coplanar faces
                b.MergeCoplanarFaces(tolerance, angle_tolerance)

                new_id = sc.doc.Objects.AddBrep(b)
                if new_id != System.Guid.Empty:
                    rs.ObjectLayer(new_id, layer)
                    rs.ObjectName(new_id, original_name if original_name else "Offset_Obj")
                    created += 1
                b.Dispose()
    finally:
        brep.Dispose()

    return created


def run_reversed_offset():
    """Entry point: offset selected surfaces/polysurfaces using the reversed sign convention."""
    valid_ids = get_valid_selection()
    if not valid_ids:
        return

    offset_dist = get_offset_distance()
    if offset_dist is None:
        return

    solid = True
    # Setting extend=False forces the engine to blend (round) offset gaps
    # instead of extending surfaces to sharp intersections.
    extend = False

    tolerance = sc.doc.ModelAbsoluteTolerance
    angle_tolerance = sc.doc.ModelAngleToleranceRadians
    current_layer = rs.CurrentLayer()

    rs.EnableRedraw(False)
    created_count = 0

    # Use native RhinoCommon undo block (avoids issues with rs wrapper in CPython)
    undo_record = sc.doc.BeginUndoRecord("Reversed Offset Round")

    try:
        for obj_id in valid_ids:
            created_count += offset_and_add(
                obj_id, offset_dist, solid, extend, tolerance, angle_tolerance, current_layer
            )
    except Exception as e:
        print("Error during processing: {0}".format(str(e)))
    finally:
        sc.doc.EndUndoRecord(undo_record)
        rs.EnableRedraw(True)
        sc.doc.Views.Redraw()

    if created_count > 0:
        # Passing properly formatted lists to prevent Python 3 iteration TypeErrors
        hide_orig = rs.GetBoolean("Hide original objects?",
                                  [("Hide", "No", "Yes")], [True])
        if hide_orig and hide_orig[0]:
            rs.HideObjects(valid_ids)

        print("Offset complete. {0} objects created.".format(created_count))


if __name__ == "__main__":
    run_reversed_offset()
