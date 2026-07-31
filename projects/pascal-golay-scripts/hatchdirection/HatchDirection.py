"""
HatchDirection.py

Python 3 (CPython, PythonNet bridge) port of HatchDirection.rvb, for
Rhino 8's Script Editor (run via the ScriptEditor command, F5). Do NOT run
this through the legacy RunPythonScript command -- that invokes the
IronPython 2 engine.

Original behavior (Pascal Golay, legacy RhinoScript/VBScript):
  - Two entry points existed as command aliases: HatchDirection (sets hatch
    pattern rotation only) and HatchOrient (also sets the hatch's base
    point via the _HatchBase command), both implemented by a shared
    SetHatch(blnBase) routine.
  - Prompts to select hatches, then prompts for two points defining a
    direction line (in the current construction plane if it differs from
    world XY).
  - Computes the angle of that line and applies it as the pattern rotation
    to every selected hatch whose pattern isn't "Solid" (solid fills have no
    meaningful rotation). If HatchOrient was called, also moves each hatch's
    pattern base point to the first picked point via the _HatchBase command
    before setting rotation.
  - Reports how many hatches were changed.

Porting notes:
  - Rhino.AddStartUpScript / Rhino.AddAlias have no equivalent for a
    CPython3 Script Editor file; this port defines set_hatch() and calls it
    at the bottom. Pass `base=True` for the old HatchOrient behavior, or
    `base=False` (default) for the old HatchDirection behavior -- edit the
    `if __name__ == "__main__":` block or call set_hatch(True) directly from
    Script Editor's console to choose.
  - Function-name mappings verified against the mcneel/rhinoscriptsyntax
    GitHub source (rhino-8.x branch): GetObjects, GetPoints, ViewCPlane,
    WorldXYPlane, Angle, EnableRedraw, HatchPattern, HatchRotation,
    SelectObjects, UnselectAllObjects, SelectObject, Command, Print all
    exist with the signatures used below. Filter value 65536 = rs.filter.hatch
    (unchanged from the original -- rhinoscriptsyntax object-type filter
    bit flags are the same values as the old RhinoScript ones).
  - Rhino.XformWorldToCPlane has no rhinoscriptsyntax wrapper. Ported using
    RhinoCommon's Plane.RemapToPlaneSpace(point) directly (confirmed
    2026 via developer.rhino3d.com/api/rhinocommon's live API data:
    `bool RemapToPlaneSpace(Point3d ptSample, out Point3d ptPlane)`).
    Per the standing out-parameter rule, PythonNet returns this as a tuple
    `(success, remapped_point)`, not just the point.
  - Rhino.Pt2Str has no rhinoscriptsyntax equivalent either; replaced with a
    small local pt2str() helper that formats "x,y,z" using repr-safe
    float formatting, for building the `_HatchBase` command-line string.
    This is a simplification of the original's locale/units-aware
    formatting (which also supported "smart" trimming of trailing zeros);
    plain repr should parse fine as command-line input in Rhino 8 but if a
    hatch base point ends up slightly off from what's expected, check this
    formatting first.
  - The original's PlaneCompare (component-by-component point comparison of
    two planes' origin/x-axis/y-axis) is replaced with rs.PointCompare on
    the same three components -- same logic, using an existing
    rhinoscriptsyntax function instead of a hand-rolled one.
  - The "HatchOrient" _HatchBase-then-rotate order is preserved from the
    original (base point set first via SetHatchBase, non-solid rotation
    applied after, in the same per-hatch loop iteration) even though the
    original's `n` counter only counts pattern-rotation changes, not base
    point changes -- if base=True and every hatch happens to be "Solid"
    pattern, the base point IS still moved, but the report will say
    "No hatches were changed," which is misleading but matches the
    original's counting behavior exactly. Flagged here, not fixed.

Limitation: no live Rhino available in this environment to actually run the
script -- validated only with `python3 -m py_compile` (syntax parses) and a
manual read-through against the rhinoscriptsyntax source. Test in Script
Editor before relying on it.
"""

import rhinoscriptsyntax as rs

HATCH_FILTER = 65536  # rs.filter.hatch


def pt2str(pt):
    """Format a 3D point as "x,y,z" for use in a Rhino command-line string.
    Simplified replacement for Rhino.Pt2Str -- see module docstring."""
    return "{0},{1},{2}".format(pt[0], pt[1], pt[2])


def plane_compare(plane1, plane2):
    """True if two planes have the same origin, x-axis, and y-axis
    (within rs.PointCompare's default tolerance)."""
    return (
        rs.PointCompare(plane1[0], plane2[0])
        and rs.PointCompare(plane1[1], plane2[1])
        and rs.PointCompare(plane1[2], plane2[2])
    )


def world_to_cplane(point, plane):
    """Remap a world-space point into the given plane's local (s, t, d)
    coordinates. Equivalent to the old Rhino.XformWorldToCPlane, which has
    no rhinoscriptsyntax wrapper -- implemented via RhinoCommon's
    Plane.RemapToPlaneSpace, whose C# signature has an `out` parameter and
    so returns a (success, point) tuple under PythonNet."""
    success, remapped = plane.RemapToPlaneSpace(point)
    if not success:
        return None
    return remapped


def set_hatch_base(hatch_id, pt):
    rs.UnselectAllObjects()
    rs.SelectObject(hatch_id)
    rs.Command("_HatchBase " + pt2str(pt), False)


def set_hatch(bln_base):
    hatches = rs.GetObjects("Select hatches to modify.", HATCH_FILTER, preselect=True, select=True)
    if not hatches:
        return

    prompt1 = "Set base point for selected hatches." if bln_base else "First direction point."
    base_pts = rs.GetPoints(True, True, prompt1, "Set hatch direction", 2)
    if not base_pts or len(base_pts) != 2:
        return

    cplane = rs.ViewCPlane()
    if not plane_compare(cplane, rs.WorldXYPlane()):
        p1 = world_to_cplane(base_pts[0], cplane)
        p2 = world_to_cplane(base_pts[1], cplane)
        if p1 is None or p2 is None:
            rs.Print("Could not remap points to the current construction plane.")
            return
    else:
        p1 = base_pts[0]
        p2 = base_pts[1]

    angle = rs.Angle(p1, p2)[0]

    rs.EnableRedraw(False)

    n = 0
    for hatch_id in hatches:
        if bln_base:
            set_hatch_base(hatch_id, p1)
        if rs.HatchPattern(hatch_id) != "Solid":
            rs.HatchRotation(hatch_id, angle)
            n += 1

    rs.SelectObjects(hatches)
    rs.EnableRedraw(True)

    if n == 0:
        msg = "No hatches were changed."
    elif n == 1:
        msg = "1 Hatch set to {0} degrees.".format(round(angle, 3))
    else:
        msg = "{0} Hatches set to {1} degrees.".format(n, round(angle, 3))

    rs.Print(msg)


def hatch_direction():
    set_hatch(False)


def hatch_orient():
    set_hatch(True)


if __name__ == "__main__":
    # Original had two aliases (HatchDirection / HatchOrient) sharing this
    # logic. Default to the plain rotation-only behavior; call
    # hatch_orient() instead (or edit this line) for the base-point variant.
    hatch_direction()
