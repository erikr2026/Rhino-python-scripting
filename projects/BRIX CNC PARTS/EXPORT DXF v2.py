# rdk:command_name: EXPORT_DXF_v2
# rdk:command_alias: EXPORT_DXF_v2
# -*- coding: utf-8 -*-
"""
Rhino 8/9 Python Script
Engine: Python 3 (CPython, via ScriptEditor / PythonNet bridge). Uses only
rhinoscriptsyntax + os, so it would also run under IronPython 2 via
RunPythonScript, but ScriptEditor + F5 is the intended launch path.

Description: Exports selected geometry as a .DXF file using the
'CAM Imperial' export scheme.

Streamlined from EXPORT DXF v1.py: same behavior/output, reorganized into
smaller helper functions, magic strings pulled into constants, and clearer
inline docs. No functional changes were made (see companion chat report for
the one spot left alone as behavior-uncertain).
"""

import os
import rhinoscriptsyntax as rs

EXPORT_SCHEME = "CAM Imperial"
DXF_EXTENSION = ".dxf"
DXF_FILE_FILTER = "DXF Files (*.dxf)|*.dxf||"
SELECT_PROMPT = "Select geometry to export to DXF ({})".format(EXPORT_SCHEME)
SAVE_DIALOG_TITLE = "Export Selected DXF ({})".format(EXPORT_SCHEME)


def get_export_selection():
    """Return the objects to export: current selection, or prompt if empty.

    Mirrors v1 exactly: rs.GetObjects args are (message, filter=0 (All
    objects), group=True, preselect=True, select=True).
    """
    selected = rs.SelectedObjects()
    if selected:
        return selected

    selected = rs.GetObjects(SELECT_PROMPT, 0, True, True, True)
    return selected  # None or empty list if the user cancels/picks nothing


def prepare_output_path(filepath):
    """Normalize the chosen save path for the DXF export command.

    - Ensures a '.dxf' extension.
    - Removes any pre-existing file at that path (Rhino's export command
      would otherwise pop a blocking overwrite-confirm dialog that hangs a
      scripted/silent run).
    - Converts backslashes to forward slashes so the path is safe to embed
      in the Rhino scriptable command string.

    Returns the safe path string, or None if an existing file could not be
    removed (error already printed to the command line).
    """
    if not filepath.lower().endswith(DXF_EXTENSION):
        filepath = "{}{}".format(filepath, DXF_EXTENSION)

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError as err:
            print("Error: The destination file exists but could not be overwritten. Details: {}".format(err))
            return None

    return filepath.replace("\\", "/")


def run_dxf_export(safe_path, object_count):
    """Run the silent scriptable _-Export command and report the result.

    Wraps the command in EnableRedraw(False)/(True) to avoid viewport
    flicker during export; the try/finally guarantees redraw is restored
    even if rs.Command raises.
    """
    cmd_str = '_-Export "{}" _Scheme "{}" _Enter'.format(safe_path, EXPORT_SCHEME)

    rs.EnableRedraw(False)
    try:
        success = rs.Command(cmd_str, False)  # echo=False: no command-line spam
        if success:
            print("Successfully exported {} object(s) to {}".format(object_count, safe_path))
        else:
            print("Export failed: Please verify that the '{}' export scheme exists in your Rhino configuration.".format(EXPORT_SCHEME))
    except Exception as ex:
        print("An error occurred during the DXF export execution: {}".format(ex))
    finally:
        rs.EnableRedraw(True)


def export_selected_dxf():
    """Exports selected objects to DXF using the 'CAM Imperial' scheme."""
    selected = get_export_selection()
    if not selected:
        print("Export canceled: No geometry was selected.")
        return

    filepath = rs.SaveFileName(SAVE_DIALOG_TITLE, DXF_FILE_FILTER, None, None, "dxf")
    if not filepath:
        print("Export canceled: No destination file selected.")
        return

    safe_path = prepare_output_path(filepath)
    if not safe_path:
        return

    run_dxf_export(safe_path, len(selected))


if __name__ == "__main__":
    export_selected_dxf()
#! python 3
