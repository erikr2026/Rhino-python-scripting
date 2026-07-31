"""Duplicate and join the edge curves of a closed polysurface.

Engine: Python 3 via Rhino's ScriptEditor command (F5). Also runs unchanged
under legacy IronPython 2 (RunPythonScript) - no Python-3-only syntax is used.

Behavior is unchanged from POLYSURFACE DUPE EDGE V1.py; this pass only adds
a docstring, a null-check on the join result (rs.JoinCurves can return None,
which would otherwise raise a TypeError on len()/SelectObjects), and pulls
the filter bitmask into named rs.filter constants for readability.
"""

import rhinoscriptsyntax as rs


def duplicate_polysurface_edges():
    # 1. Ask user to select a surface or polysurface.
    obj_id = rs.GetObject(
        "Select a closed polysurface",
        filter=rs.filter.surface | rs.filter.polysurface,
    )
    if not obj_id:
        return

    # 2. Duplicate all edge curves of the brep.
    #    Returns None (not an empty list) if it can't produce any edges.
    edges = rs.DuplicateEdgeCurves(obj_id)
    if not edges:
        print("No edges found or operation failed.")
        return

    # 3. Join them into as few curve objects as possible.
    #    JoinCurves can also return None on failure - guard before using
    #    len()/SelectObjects, which would otherwise raise a TypeError.
    joined_curves = rs.JoinCurves(edges, delete_input=True)
    if not joined_curves:
        print("Edges duplicated but join failed.")
        return

    # 4. Select the resulting curves.
    rs.SelectObjects(joined_curves)
    print("Successfully extracted {} curves.".format(len(joined_curves)))


if __name__ == "__main__":
    duplicate_polysurface_edges()
