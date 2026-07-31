"""
UpdateSelectedBlocks.py

Ported from UpdateSelectedBlocks.rvb (legacy VBScript RhinoScript, Pascal
Golay / McNeel). Target engine: Rhino 8 Script Editor, CPython 3 mode (open
the .py file in ScriptEditor and press F5). Not for the legacy
`RunPythonScript` (IronPython 2) command.

What it does: prompts you to select one or more block instances, collects
the distinct block-definition names among them, then runs Rhino's
`BlockManager` command's `_Update` option once per distinct name (useful for
refreshing linked/embedded block definitions from their source file without
opening the BlockManager dialog UI).

Not ported: `Rhino.AddStartUpScript` / `Rhino.AddAlias`, which registered a
permanent Rhino alias ("UpdateSelectedBlocks") that re-ran this script from
disk on every Rhino startup. No equivalent mechanism exists for a Script
Editor .py file; create an alias by hand pointing at this file if you want
one (Options > Aliases).

Verification note: rs.GetObjects, rs.filter.instance, and
rs.BlockInstanceName signatures/values were confirmed this session against
the mcneel/rhinoscriptsyntax GitHub source (selection.py, block.py).
`Rhino.CullDuplicateStrings` (used in the original to dedupe the block-name
list) is a legacy RhinoScript (VBScript COM) method with NO equivalent in
rhinoscriptsyntax -- confirmed by listing every `def` in
rhinoscriptsyntax's utility.py, which only has CullDuplicateNumbers and
CullDuplicatePoints, no string version. Deduplication is done here with
plain Python instead (`dict.fromkeys`, which also preserves first-seen
order, matching the likely intent of the original).

There is no live Rhino available in this environment to actually execute
this script; the `_-BlockManager ... _Update "name" ... _Enter _Enter`
command-line macro is carried over unchanged from the original and should
be tested in Rhino before relying on it.
"""

import rhinoscriptsyntax as rs


def update_selected_blocks():
    a_obj = rs.GetObjects(
        "Select blocks to update.",
        rs.filter.instance,
        preselect=True,
    )
    if not a_obj:
        return

    a_update = [rs.BlockInstanceName(s_block) for s_block in a_obj]
    a_final = list(dict.fromkeys(a_update))  # dedupe, preserve first-seen order

    parts = []
    for name in a_final:
        parts.append(' _Update "{0}"'.format(name))

    cmd = "_-BlockManager" + "".join(parts) + " _Enter _Enter"
    rs.Command(cmd, False)


if __name__ == "__main__":
    update_selected_blocks()
