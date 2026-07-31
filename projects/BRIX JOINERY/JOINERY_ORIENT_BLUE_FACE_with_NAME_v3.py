# -*- coding: utf-8 -*-

"""
Rhino Python Script (Rhino 8 & 9)

Selects solid Breps, groups them into sets based on their name prefixes
(e.g. 'DIN1-A' -> set 'DIN1'), sorts sets and sequences naturally, aligns
each copy flat with its blue face pointing UP (World Z) at Z=0.47, nests
each set along the X-axis with spacing, offsets each successive set along
the Y-axis, and drops CNC label text (part name + project name) on the
'97 CUTFILE::BRIX TEXT' layer above each nested part's original centroid.

Engine: this folder's sibling scripts (e.g. JOINERYSETBLUEFACEWIP.py) carry
an explicit "Rhino 8 & 9" / RunPythonScript-style header, so this is written
to the same convention. The exact launch command (ScriptEditor vs.
RunPythonScript) was not independently confirmed for this specific file —
if you know it runs elsewhere, no code here depends on the distinction
(no Python-3-only syntax, no non-ASCII literals beyond this header comment).

Streamlined from JOINERY_ORIENT_BLUE_FACE_with_NAME_v2.py: extracted the
repeated "AreaMassProperties centroid, falling back to bounding-box center"
block (previously duplicated verbatim for the original geometry and again
for the pre-transform copy) into get_centroid(), and the repeated
"is this string non-empty after stripping" checks into has_text(). No
control flow, ordering, tolerances, or transform math changed.
"""

import re
import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import Rhino
import scriptcontext as sc
import System


def natural_sort_key(s):
    """
    Returns a list of alphanumeric tokens for natural sorting.
    Ensures that 'DIN2' sorts before 'DIN10', and 'A' sorts before 'B'.
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def has_text(s):
    """True if s is a non-empty string once whitespace is stripped."""
    return bool(s) and s.strip() != ""


def get_centroid(geometry):
    """
    Best-effort centroid for a Brep: AreaMassProperties first (true
    area-weighted centroid), falling back to the bounding-box center if
    mass properties can't be computed, and finally World origin if even
    the bounding box is invalid. Never returns None.
    """
    centroid = None
    try:
        amp = rg.AreaMassProperties.Compute(geometry)
        if amp:
            centroid = amp.Centroid
    except Exception:
        pass

    if not centroid:
        bbox = geometry.GetBoundingBox(True)
        if bbox.IsValid:
            centroid = bbox.Center
        else:
            centroid = rg.Point3d(0.0, 0.0, 0.0)

    return centroid


def orient_layout_and_label():
    """
    Selects solid Breps, groups them into sets based on their name prefixes (e.g., 'DIN1-A' -> set 'DIN1'),
    sorts sets and sequences naturally, aligns each copy flat with its blue face pointing UP (World Z) at Z=0.47,
    nests each set along the X-axis with spacing, and offsets each successive set in the Y-axis.
    """
    obj_ids = rs.GetObjects("Select solid Breps to orient, layout, and label", 8 | 16, True, True, True)
    if not obj_ids:
        print("No objects selected.")
        return

    project_name = rs.StringBox("Enter Project Name for CNC labels:", "PROJECT-A", "Project Name Configuration")
    if project_name is None:
        print("Process cancelled by user.")
        return

    rs.EnableRedraw(False)

    doc = Rhino.RhinoDoc.ActiveDoc
    processed_count = 0
    spacing = 12.0   # Clear edge-to-edge spacing between parts (12 inches)

    target_layer = "97 CUTFILE::BRIX TEXT"
    target_style_name = "CNC PARTS"

    rs.AddLayer(target_layer)
    layer_index = doc.Layers.FindByFullPath(target_layer, -1)
    if layer_index < 0:
        layer = doc.Layers.FindName("BRIX TEXT")
        if layer:
            layer_index = layer.Index
        else:
            layer_index = doc.Layers.CurrentLayerIndex

    dim_style = doc.DimStyles.FindName(target_style_name)
    if dim_style is None:
        idx = doc.DimStyles.Add(target_style_name, False)
        if idx >= 0:
            dim_style = doc.DimStyles[idx]
        else:
            dim_style = doc.DimStyles.Current

    sets_dict = {}

    for obj_id in obj_ids:
        obj_name = rs.ObjectName(obj_id)
        if not obj_name:
            rh_obj = rs.coercerhinoobject(obj_id)
            if rh_obj and rh_obj.Attributes.Name:
                obj_name = rh_obj.Attributes.Name

        # Determine base set name and sequential suffix
        if not has_text(obj_name):
            set_name = "UNNAMED"
            seq_suffix = str(obj_id)
            full_name = ""
        else:
            full_name = obj_name.strip()
            # Split from the right at the last hyphen
            base, sep, suffix = full_name.rpartition("-")
            if not sep:
                set_name = full_name
                seq_suffix = ""
            else:
                set_name = base
                seq_suffix = suffix

        if set_name not in sets_dict:
            sets_dict[set_name] = []
        sets_dict[set_name].append((obj_id, seq_suffix, full_name))

    sorted_set_names = sorted(sets_dict.keys(), key=natural_sort_key)
    current_y = 0.0  # Dynamic layout offset in the World Y direction

    for set_name in sorted_set_names:
        # Sort items within this set sequentially by their parsed suffix
        items_in_set = sorted(sets_dict[set_name], key=lambda x: natural_sort_key(x[1]))

        current_x = 0.0     # Tracks the layout nesting position along the World X-axis
        max_y_in_set = 0.0  # Tracks the maximum height of parts in the current row (Y-axis)
        processed_in_set = 0

        for obj_id, seq_suffix, obj_name in items_in_set:
            rh_obj = rs.coercerhinoobject(obj_id)
            if not rh_obj or not isinstance(rh_obj.Geometry, rg.Brep):
                continue

            geometry = rh_obj.Geometry
            faces = geometry.Faces
            blue_faces = []

            for i in range(faces.Count):
                face = faces[i]
                face_color = face.PerFaceColor

                # Identify face color overrides matching Blue (R=0, G=0, B=255)
                if not face_color.IsEmpty and face_color.R == 0 and face_color.G == 0 and face_color.B == 255:
                    try:
                        amp = rg.AreaMassProperties.Compute(face)
                        area = amp.Area if amp else 0.0
                    except Exception:
                        area = 0.0
                    blue_faces.append((face, area, i))

            if not blue_faces:
                centroid = get_centroid(geometry)

                rs.AddTextDot("!", centroid)
                fallback_name = obj_name if has_text(obj_name) else str(obj_id)
                print("SKIPPED: Object '{}' has no blue (RGB 0,0,255) face. Placed '!' text dot at centroid.".format(fallback_name))
                continue

            # Sort candidate blue faces by surface area descending to find the primary face
            blue_faces.sort(key=lambda x: x[1], reverse=True)
            primary_face, primary_area, face_index = blue_faces[0]

            domain_u = primary_face.Domain(0)
            domain_v = primary_face.Domain(1)

            normal_vec = primary_face.NormalAt(domain_u.Mid, domain_v.Mid)
            center_pt = primary_face.PointAt(domain_u.Mid, domain_v.Mid)
            normal_vec.Unitize()

            world_x = rg.Vector3d.XAxis
            world_y = rg.Vector3d.YAxis
            world_z = rg.Vector3d.ZAxis

            # If the face is horizontal (pointing mostly up or down)
            if abs(normal_vec.Z) > 0.707:
                u = world_x - (normal_vec * (world_x * normal_vec))
                u.Unitize()
                v = rg.Vector3d.CrossProduct(normal_vec, u)
                v.Unitize()
                if (u * world_x + v * world_y) < 0:
                    u, v = -u, -v
            else:
                v = world_z - (normal_vec * (world_z * normal_vec))
                v.Unitize()
                u = rg.Vector3d.CrossProduct(v, normal_vec)
                u.Unitize()
                if (u * world_x + v * world_z) < 0:
                    u, v = -u, -v

            source_plane = rg.Plane(center_pt, u, v)
            plane_to_plane = rg.Transform.PlaneToPlane(source_plane, rg.Plane.WorldXY)

            if not plane_to_plane.IsValid:
                print("Object '{}' skipped: Invalid plane alignment calculated.".format(obj_id))
                continue

            # Calculate bounding box of transformed copy for exact sequential layout
            temp_brep = geometry.Duplicate()
            temp_brep.Transform(plane_to_plane)
            bbox = temp_brep.GetBoundingBox(True)
            temp_brep.Dispose()

            if not bbox.IsValid:
                print("Object '{}' skipped: Could not calculate bounding box.".format(obj_id))
                continue

            # Translate so min bounding box corner is at current_x, current_y, and the blue face is at Z=0.47
            translation = rg.Vector3d(current_x - bbox.Min.X, current_y - bbox.Min.Y, 0.47)
            final_transform = rg.Transform.Translation(translation) * plane_to_plane

            if final_transform.IsValid:
                new_obj_id = doc.Objects.Transform(obj_id, final_transform, False)
                if new_obj_id != System.Guid.Empty:
                    processed_count += 1
                    processed_in_set += 1

                    rs.RemoveObjectFromAllGroups(new_obj_id)

                    print("Copied and nested '{}' at X: {:.3f}, Y: {:.3f}, Z: 0.470 (Set: {})".format(
                        obj_name if has_text(obj_name) else str(obj_id),
                        current_x,
                        current_y,
                        set_name
                    ))

                    orig_centroid = get_centroid(geometry)

                    nested_centroid = rg.Point3d(orig_centroid)
                    nested_centroid.Transform(final_transform)

                    if has_text(obj_name):
                        text_plane = rg.Plane.WorldXY
                        text_plane.Origin = nested_centroid

                        text_entity = rg.TextEntity()
                        text_entity.PlainText = obj_name
                        text_entity.Plane = text_plane
                        text_entity.Justification = rg.TextJustification.MiddleCenter

                        if dim_style:
                            text_entity.DimensionStyleId = dim_style.Id
                            text_entity.ClearPropertyOverrides()

                        attributes = Rhino.DocObjects.ObjectAttributes()
                        attributes.LayerIndex = layer_index

                        doc.Objects.AddText(text_entity, attributes)

                        if has_text(project_name):
                            proj_plane = rg.Plane.WorldXY
                            proj_plane.Origin = nested_centroid + rg.Vector3d(0.0, 1.0, 0.0)

                            proj_text_entity = rg.TextEntity()
                            proj_text_entity.PlainText = project_name
                            proj_text_entity.Plane = proj_plane
                            proj_text_entity.Justification = rg.TextJustification.MiddleCenter

                            if dim_style:
                                proj_text_entity.DimensionStyleId = dim_style.Id
                                proj_text_entity.ClearPropertyOverrides()

                            doc.Objects.AddText(proj_text_entity, attributes)
                    else:
                        dot_id = rs.AddTextDot("!", nested_centroid)
                        if dot_id:
                            rs.ObjectLayer(dot_id, target_layer)

                    # Track height of items in this row to determine the next Y offset
                    part_height_y = bbox.Max.Y - bbox.Min.Y
                    if part_height_y > max_y_in_set:
                        max_y_in_set = part_height_y

                    current_x += (bbox.Max.X - bbox.Min.X) + spacing
                else:
                    print("Object '{}' skipped: Failed to generate copy.".format(obj_id))

        # Advance Y coordinates to start a new row for the next set
        if processed_in_set > 0:
            current_y += max_y_in_set + spacing

    rs.EnableRedraw(True)
    doc.Views.Redraw()

    print("Process complete. Nested {} copy object(s) across sorted rows.".format(processed_count))


if __name__ == "__main__":
    # NOTE (left intentionally unchanged from v2): the original file calls
    # orient_layout_and_label() twice in a row here. That runs the entire
    # selection/prompt/orient/label flow twice per script execution (a second
    # "Select solid Breps" + "Enter Project Name" prompt back-to-back). This
    # looks like an unintentional copy-paste duplication rather than a
    # deliberate double-pass design, but removing it would change observable
    # behavior (one run vs. two), so it's preserved here per the
    # no-behavior-change constraint. Flag this to the owner and confirm
    # before deleting the second call.
    orient_layout_and_label()
    orient_layout_and_label()
