# rdk:command_name: EXPORT_DXF_v1
# rdk:command_alias: EXPORT_DXF_v1
# -*- coding: utf-8 -*-
"""
Rhino 8/9 Python Script
Description: Exports selected geometry as a .DXF file using the 'CAM Imperial' export scheme.
Author: Rhino Python Scripter
"""

import os
import rhinoscriptsyntax as rs


def export_selected_dxf():
    """Exports selected objects to DXF using the 'CAM Imperial' scheme."""
    # Check for active viewport selection
    selected = rs.SelectedObjects()
    
    if not selected:
        # Prompt user to select objects if selection is empty
        selected = rs.GetObjects(
            "Select geometry to export to DXF (CAM Imperial)", 
            0,     # Filter: All objects
            True,  # Group select
            True,  # Preselect
            True   # Select
        )
        if not selected:
            print("Export canceled: No geometry was selected.")
            return

    # Ask the user for the output file path using save file dialog
    filepath = rs.SaveFileName(
        "Export Selected DXF (CAM Imperial)", 
        "DXF Files (*.dxf)|*.dxf||", 
        None, 
        None, 
        "dxf"
    )
    
    if not filepath:
        print("Export canceled: No destination file selected.")
        return

    # Enforce correct file extension
    if not filepath.lower().endswith(".dxf"):
        filepath = "{}.dxf".format(filepath)

    # Clean existing file if present to bypass command-line dialog hangs
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError as err:
            print("Error: The destination file exists but could not be overwritten. Details: {}".format(err))
            return

    # Convert path backslashes to forward slashes to ensure reliable macro parsing
    safe_path = filepath.replace("\\", "/")
    
    # Construct scriptable command string
    # We use 'CAM Imperial' as the requested scheme and double-quotes to encapsulate the path safely
    cmd_str = '_-Export "{}" _Scheme "CAM Imperial" _Enter'.format(safe_path)

    # Temporarily disable viewport redraw to optimize execution performance
    rs.EnableRedraw(False)
    try:
        # Run silent command (echo=False) to prevent spamming the command line
        success = rs.Command(cmd_str, False)
        if success:
            print("Successfully exported {} object(s) to {}".format(len(selected), filepath))
        else:
            print("Export failed: Please verify that the 'CAM Imperial' export scheme exists in your Rhino configuration.")
    except Exception as ex:
        print("An error occurred during the DXF export execution: {}".format(ex))
    finally:
        # Re-enable viewport redrawing
        rs.EnableRedraw(True)


if __name__ == "__main__":
    export_selected_dxf()#! python 3
