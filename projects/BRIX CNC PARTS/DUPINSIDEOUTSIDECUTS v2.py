# rdk:command_name: DUP_INSIDE_OUTSIDE
# rdk:command_alias: DUP_INSIDE_OUTSIDE
"""
Duplicate Border and Auto-Sort to Fabrication Layers (v2 - streamlined)

Target Engine: Python 3 (Rhino 8 & 9 CPython, run via ScriptEditor / F5)
Author: SCRIPTER

Description:
Duplicates outer boundaries and inner cutout loops of selected surfaces,
polysurfaces, or extrusions, sorting them onto dedicated CNC cut layers.

v2 changes (streamline/cleanup only - no behavior change):
- Object filter mask now built from named rs.filter constants instead of a
  bare "8+16+1073741824" literal (surface=8, polysurface=16, extrusion=
  1073741824 - confirmed against the rhinoscriptsyntax "filter" class source,
  https://raw.githubusercontent.com/mcneel/rhinoscriptsyntax/master/Scripts/
  rhinoscript/selection.py, fetched this session). Same bitmask, easier to
  read/maintain.
- Per-brep curve extraction/layering pulled into a small helper
  (duplicate_and_sort_edges) to remove the nested nesting in main() and make
  the per-object logic independently readable/testable.
- Added docstrings to main() and the new helper.
- No control-flow, ordering, or output-text changes: same prompts, same
  layer paths/colors, same summary message format.
"""

import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs

# Surfaces, polysurfaces, or extrusions - rs.coercebrep() handles all three.
OBJECT_FILTER = rs.filter.surface | rs.filter.polysurface | rs.filter.extrusion


def get_or_create_layer(layer_path, color_rgb):
    """Retrieves a layer or creates it with the given RGB color.

    Returns the layer_path unchanged (rhinoscriptsyntax layer functions
    address layers by path/name, not a separate id).
    """
    if not rs.IsLayer(layer_path):
        color = Rhino.Drawing.Color.FromArgb(*color_rgb)
        rs.AddLayer(layer_path, color)
    return layer_path


def duplicate_and_sort_edges(brep, layers):
    """Duplicates naked edges (outer/inner per layers config) from one brep
    and adds valid resulting curves to the document on the configured layer.

    `layers` is the module-level layer config dict; each cfg's "count" is
    incremented in place for the final summary.
    """
    for cfg in layers.values():
        curves = brep.DuplicateNakedEdgeCurves(cfg["outer"], cfg["inner"])
        if not curves:
            continue

        for curve in curves:
            if curve and curve.IsValid:
                new_id = sc.doc.Objects.AddCurve(curve)
                if new_id:
                    rs.ObjectLayer(new_id, cfg["layer_id"])
                    cfg["count"] += 1


def main():
    """Prompts for surfaces/polysurfaces/extrusions, duplicates their outer
    boundary and inner cutout edges, and sorts the results onto dedicated
    CNC "outside cuts" / "inside cuts" layers."""

    # Configuration for CNC fabrication layers
    layers = {
        "outside": {"path": "97 CUTFILE::OUTSIDE CUTS", "color": (255, 0, 0), "outer": True, "inner": False, "count": 0},
        "inside": {"path": "97 CUTFILE::INSIDE CUTS", "color": (0, 120, 255), "outer": False, "inner": True, "count": 0}
    }

    # Prompt user for surfaces, polysurfaces, or extrusions
    object_ids = rs.GetObjects("Select surfaces or polysurfaces to duplicate borders", filter=OBJECT_FILTER, preselect=True)
    if not object_ids:
        print("No valid objects selected.")
        return

    rs.EnableRedraw(False)

    # Initialize layers
    for cfg in layers.values():
        cfg["layer_id"] = get_or_create_layer(cfg["path"], cfg["color"])

    skipped_count = 0

    for obj_id in object_ids:
        # coercebrep cleanly handles Surfaces, Polysurfaces, and Extrusions
        brep = rs.coercebrep(obj_id)
        if not brep:
            skipped_count += 1
            continue

        duplicate_and_sort_edges(brep, layers)

    rs.EnableRedraw(True)
    sc.doc.Views.Redraw()

    # User feedback
    summary = "Completed! Duplicated {} outside cuts (Red) and {} inside cuts (Blue).".format(
        layers["outside"]["count"], layers["inside"]["count"]
    )
    if skipped_count > 0:
        summary += " Skipped {} incompatible objects.".format(skipped_count)
    print(summary)


if __name__ == "__main__":
    main()
