"""
FileInfo.py

Python 3 (CPython) port of FileInfo.rvb, for Rhino 8's Script Editor
(ScriptEditor command, run with F5). Not for the legacy
RunPythonScript/IronPython 2 engine.

Original author: Pascal Golay (McNeel). No date given in the source.

Reports: the current file's saved size and last-saved time, a total
object count, and a breakdown of object counts by geometry type.

Function/API mappings verified 2026 against mcneel/rhinoscriptsyntax
GitHub source (rhino-8.x branch) via WebFetch this session:
  - rs.Print does NOT exist in rhinoscriptsyntax (confirmed absent from
    every module in the source tree) - the original's `Rhino.Print` is
    ported to a plain Python `print(...)`, which Rhino 8's Script Editor
    routes to its Output panel.
  - rs.TextOut(message, title=None) does exist (wraps
    Rhino.UI.Dialogs.ShowTextDialog) and is used here for the pop-up
    text-window behavior the original had, matching its non-commented
    Rhino.TextOut call.
  - rs.ObjectsByType(geometry_type, select=False, state=0) bit flags are
    unchanged from legacy RhinoScript (1=point, 2=point cloud, 4=curve,
    8=surface, 16=polysurface, 32=mesh, 256=light, 512=annotation,
    4096=instance, 8192=text dot, 65536=hatch, 131072=morph control,
    134217728=cage, 536870912=clipping plane) - same values also used
    verbatim in the original .rvb, and available identically via the
    rs.filter class constants.

Deviations from the original, both necessary rather than stylistic:
  1. File size/last-modified-time were read via VBScript's
     "Scripting.FileSystemObject" COM object, which is Windows-only and
     has no CPython3 equivalent (COM automation isn't available under
     the CPython3 bridge). This port uses Python's stdlib `os.path`
     instead, which also works on Mac Rhino.
  2. The original registered command aliases via `Rhino.AddAlias` /
     `Rhino.AddStartUpScript`. Neither exists in rhinoscriptsyntax -
     that legacy alias/startup-script mechanism is specific to the old
     RhinoScript engine. A Script Editor .py file is run directly
     (F5, or from a saved toolbar/alias pointing at the file), so no
     porting is needed here; this file just exposes file_info(),
     how_many(), and how_many_scene() as callable functions.
"""

import os
import datetime
import rhinoscriptsyntax as rs


def current_file_size():
    """Returns a human-readable summary of the saved file's size and
    last-saved time, or an explanatory message if the file has never
    been saved."""
    doc_path = rs.DocumentPath()
    doc_name = rs.DocumentName()

    if not doc_path or not doc_name:
        return "This file has not been saved. No file size is available."

    full_path = os.path.join(doc_path, doc_name)

    if not os.path.isfile(full_path):
        return "This file has not been saved. No file size is available."

    size_bytes = os.path.getsize(full_path)
    mtime = os.path.getmtime(full_path)
    saved_str = datetime.datetime.fromtimestamp(mtime).strftime("%A, %B %d, %Y %I:%M:%S %p")

    return (
        "{} was last saved {}\n"
        "As last saved it uses {:.2f} MB\n"
        "of disk space.".format(doc_name, saved_str, size_bytes / 1048576.0)
    )


def how_many_in_scene():
    """Returns a one-line summary of the total object count in the file."""
    all_ids = rs.AllObjects()
    if not all_ids:
        return "No objects found in the file."
    count = len(all_ids)
    if count == 1:
        return "1 object found in the file."
    return "{} objects found in the file.".format(count)


def how_many():
    """Reports how many objects are currently selected."""
    selected_ids = rs.SelectedObjects()
    if not selected_ids:
        result = "No objects are selected."
    elif len(selected_ids) == 1:
        result = "1 object is selected."
    else:
        result = "{} objects are selected.".format(len(selected_ids))
    print(result)
    rs.MessageBox(result, 64)


def how_many_scene():
    """Reports the total object count via print and a text dialog."""
    result = how_many_in_scene()
    print(result)
    rs.TextOut(result)


# geometry-type bit flag -> descriptive label, in the same order as the original
_TYPE_LABELS = (
    (rs.filter.point, "points"),
    (rs.filter.pointcloud, "point clouds"),
    (rs.filter.curve, "curves"),
    (rs.filter.surface, "surfaces"),
    (rs.filter.polysurface, "polysurfaces"),
    (rs.filter.mesh, "meshes"),
    (rs.filter.light, "lights"),
    (rs.filter.annotation, "annotations"),
    (rs.filter.instance, "block instances"),
    (rs.filter.textdot, "dots"),
    (rs.filter.hatch, "hatches"),
    (rs.filter.morph, "controls"),
    (rs.filter.cage, "cages"),
    (rs.filter.clippingplane, "clipping planes"),
)


def object_breakdown():
    """Returns a multi-line breakdown of object counts by geometry type,
    one line per type that has at least one object present."""
    lines = []
    for type_flag, label in _TYPE_LABELS:
        ids = rs.ObjectsByType(type_flag)
        if ids:
            lines.append("{} {}".format(len(ids), label))
    return "\n".join(lines)


def file_info():
    file_size_str = current_file_size()
    total_str = how_many_in_scene()
    breakdown_str = object_breakdown()

    full_report = "{}\n{}\n{}".format(file_size_str, total_str, breakdown_str)

    rs.TextOut(full_report)
    print(full_report)


if __name__ == "__main__":
    file_info()
