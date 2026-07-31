"""
WorldCPlaneToView.py

Ported from WorldCPlaneToView.rvb (legacy VBScript RhinoScript, Pascal
Golay / McNeel). Target engine: Rhino 8 Script Editor, CPython 3 mode (open
the .py file in ScriptEditor and press F5). Not for the legacy
`RunPythonScript` (IronPython 2) command.

Two tools:

  world_cplane_to_view() -- looks at the current view's camera direction,
      figures out which of the 6 standard world-axis-aligned views it's
      closest to (Top/Bottom/Front/Back/Left/Right), and sets that view's
      construction plane to the corresponding world-aligned plane (origin
      at the world origin).

  orient_view_cplane_to_world() -- same as above, but preserves the
      construction plane's current ORIGIN (only its orientation/axes are
      reset to the matched world-aligned plane).

Not ported: `Rhino.AddStartupScript` / two `Rhino.AddAlias` calls, which
registered permanent Rhino aliases ("WorldCplaneToView",
"OrientViewCplaneToWorld") that re-ran this script file, dispatching to one
Sub or the other based on the alias's argument. No equivalent mechanism
exists for a Script Editor .py file; this file instead prompts on the
command line for which of the two tools to run when executed directly (see
the bottom of the file). Create Rhino aliases by hand (Options > Aliases)
if you want one-word shortcuts.

Not a bug, just a naming note: `most_parallel()` below picks the CANDIDATE
AXIS with the LARGEST angle to the camera's frame Z-axis, not the smallest.
This is correct, not backwards: `rs.ViewCameraPlane()`'s Z-axis points from
the view target OUT toward the camera (the "eye" direction), which is the
opposite sense from each candidate's "into the screen" viewing direction
used to build the aStr/aPlanes labels below -- so the best-matching
candidate is the one nearest 180 degrees (most ANTI-parallel to the camera
frame's Z-axis), which is exactly what picking the largest angle finds.
Verified by tracing the index correspondence between aVec, aPlanes and
aStr for all 6 entries; not verified against a live Rhino session, so
confirm the resulting CPlane orientation makes sense the first time you
run this on each of the 6 standard views.

Verification note: rs.ViewCPlane, rs.ViewCameraPlane, rs.CurrentView,
rs.EnableRedraw, and rs.coerceplane's accepted list-of-3-points format
(`[origin, x_axis_point, y_axis_point]`, an optional unused 4th list
element) were confirmed this session against the mcneel/rhinoscriptsyntax
GitHub source (view.py, utility.py). `Rhino.VectorUnitize` /
`Rhino.VectorDotProduct` / `Rhino.aCos` / `Rhino.ToDegrees` are legacy
RhinoScript (VBScript COM) methods with no rhinoscriptsyntax equivalents;
this port uses `Rhino.Geometry.Vector3d.Unitize()` /
`Rhino.Geometry.Vector3d.Multiply(v1, v2)` (the dot product, confirmed via
McNeel Discourse as the RhinoCommon dot-product method) / Python's
`math.acos` / `math.degrees` instead. There is no live Rhino available in
this environment to actually execute this script.
"""

import math

import rhinoscriptsyntax as rs
from Rhino.Geometry import Vector3d

# Candidate "into the screen" viewing directions for the 6 standard views,
# and the corresponding world-aligned CPlane (as [origin, x_axis_point,
# y_axis_point, normal_point] lists -- rs.coerceplane only reads the first
# three of these to build the plane) and display name. Index-for-index
# correspondence across all three lists is required (see docstring).
_A_VEC = [
    Vector3d(1, 0, 0),
    Vector3d(0, 1, 0),
    Vector3d(0, 0, 1),
    Vector3d(-1, 0, 0),
    Vector3d(0, -1, 0),
    Vector3d(0, 0, -1),
]

_A_PLANES = [
    [(0, 0, 0), (0, -1, 0), (0, 0, 1), (-1, 0, 0)],
    [(0, 0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)],
    [(0, 0, 0), (1, 0, 0), (0, -1, 0), (0, -1, 0)],
    [(0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)],
    [(0, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 1, 0)],
    [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0)],
]

_A_STR = ["Left.", "Front.", "Bottom.", "Right.", "Back.", "Top."]


def _vector_angle(vec1, vec2):
    """Angle in degrees between two vectors (0 if they're effectively
    parallel, to avoid an acos domain error from floating-point drift)."""
    test1 = Vector3d(vec1)
    test2 = Vector3d(vec2)
    test1.Unitize()
    test2.Unitize()

    dbl_dot = Vector3d.Multiply(test1, test2)

    if round(dbl_dot, 5) == 1.0:
        return 0.0

    dbl_dot = max(-1.0, min(1.0, dbl_dot))  # guard acos domain
    dbl_angle = math.acos(dbl_dot)

    if dbl_angle == 0:
        return 0.0
    return math.degrees(dbl_angle)


def _most_parallel(vec, a_vec):
    idx = 0
    ang = _vector_angle(vec, a_vec[0])
    for i in range(1, len(a_vec)):
        temp_ang = _vector_angle(vec, a_vec[i])
        if temp_ang > ang:
            ang = temp_ang
            idx = i
    return idx


def world_cplane_to_view():
    vec_dir = rs.ViewCameraPlane().ZAxis
    n = _most_parallel(vec_dir, _A_VEC)

    rs.ViewCPlane(rs.CurrentView(), _A_PLANES[n])
    print("Cplane set to " + _A_STR[n])


def orient_view_cplane_to_world():
    a_pt = rs.ViewCPlane().Origin

    rs.EnableRedraw(False)
    try:
        world_cplane_to_view()

        plane = rs.ViewCPlane()
        plane.Origin = a_pt
        rs.ViewCPlane(None, plane)
    finally:
        rs.EnableRedraw(True)


if __name__ == "__main__":
    choice = rs.GetString(
        "Which tool?", "WorldCplaneToView",
        ["WorldCplaneToView", "OrientViewCplaneToWorld"],
    )
    if choice:
        choice_lower = choice.lower()
        if choice_lower == "worldcplanetoview":
            world_cplane_to_view()
        elif choice_lower == "orientviewcplanetoworld":
            orient_view_cplane_to_world()
