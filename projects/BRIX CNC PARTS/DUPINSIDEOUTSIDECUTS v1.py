# rdk:command_name: DUP_INSIDE_OUTSIDE
# rdk:command_alias: DUP_INSIDE_OUTSIDE
"""
Duplicate Border and Auto-Sort to Fabrication Layers
Target Engine: Python 3 (Rhino 8 & 9 CPython)
Author: SCRIPTER

Description:
Duplicates outer boundaries and inner cutout loops of selected surfaces,
polysurfaces, or extrusions, sorting them onto dedicated CNC cut layers.
"""

import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs

def get_or_create_layer(layer_path, color_rgb):
    """Retrieves a layer or creates it with the given RGB color."""
    if not rs.IsLayer(layer_path):
        color = Rhino.Drawing.Color.FromArgb(*color_rgb)
        rs.AddLayer(layer_path, color)
    return layer_path

def main():
    # Configuration for CNC fabrication layers
    layers = {
        "outside": {"path": "97 CUTFILE::OUTSIDE CUTS", "color": (255, 0, 0), "outer": True, "inner": False, "count": 0},
        "inside": {"path": "97 CUTFILE::INSIDE CUTS", "color": (0, 120, 255), "outer": False, "inner": True, "count": 0}
    }
    
    # Prompt user for surfaces, polysurfaces, or extrusions
    object_ids = rs.GetObjects("Select surfaces or polysurfaces to duplicate borders", filter=8+16+1073741824, preselect=True)
    if not object_ids:
        print("No valid objects selected.")
        return

    rs.EnableRedraw(False)
    
    # Initialize layers
    for key, cfg in layers.items():
        cfg["layer_id"] = get_or_create_layer(cfg["path"], cfg["color"])
    
    skipped_count = 0

    for obj_id in object_ids:
        # coercebrep cleanly handles Surfaces, Polysurfaces, and Extrusions
        brep = rs.coercebrep(obj_id)
        if not brep:
            skipped_count += 1
            continue
            
        # Extract and sort curves
        for key, cfg in layers.items():
            curves = brep.DuplicateNakedEdgeCurves(cfg["outer"], cfg["inner"])
            if not curves:
                continue
                
            for curve in curves:
                if curve and curve.IsValid:
                    new_id = sc.doc.Objects.AddCurve(curve)
                    if new_id:
                        rs.ObjectLayer(new_id, cfg["layer_id"])
                        cfg["count"] += 1

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