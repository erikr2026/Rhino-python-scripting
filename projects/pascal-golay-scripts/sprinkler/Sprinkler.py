"""
Sprinkler.py

Ported from Sprinkler.rvb (legacy VBScript RhinoScript, Pascal Golay / McNeel).
Target engine: Rhino 8 Script Editor, CPython 3 mode (open the .py file in
ScriptEditor and press F5). Not for the legacy `RunPythonScript` (IronPython 2)
command.

What it does: picks a source object and a base point on it, picks a target
surface/mesh, then scatters random copies of the source object across the
target by projecting random points (from a temporary planar "seed" surface
built over the target's bounding box) straight down onto the target.
Optionally randomizes rotation about world Z and/or uniform scale per copy.

Not ported: the original's `Rhino.AddStartUpScript` / `Rhino.AddAlias` calls.
Those registered a permanent Rhino alias ("Sprinkler") that reloaded and ran
this script from disk on every Rhino startup -- a legacy-RhinoScript-specific
mechanism with no direct equivalent for a Script Editor .py file. If you want
a one-word alias, create it by hand in Rhino's Options > Aliases, pointing at
`_-RunPythonScript "<path to this file>"` (or the ScriptEditor equivalent).

Persistence of the "last used" option values (how many copies, rotation
range, scale range, which randomize toggles were on) is done via
scriptcontext.sticky, the standard rhinoscriptsyntax mechanism for values
that should survive from one run of a script to the next within the same
Rhino session. In the original VBScript these were module-scope `Private`
variables that persisted only because the script file stayed loaded as a
running alias -- sticky is the closest equivalent for a script that's
re-run from scratch each time.

Bugs found in the original and NOT reproduced here (fixed instead):
  - Rotation range prompts (lines ~75-79): the second GetReal call's result
    is checked with `If isNull(a1)` instead of `If isNull(a2)` -- a copy-paste
    typo that means canceling the second prompt doesn't actually abort.
  - Scale range prompts (lines ~88-92): the FIRST GetReal call's result is
    checked with `If isNull(f2)` before f2 has even been assigned yet (an
    IsEmpty-style VBScript quirk masks the bug at runtime, but it's still
    checking the wrong variable) -- should check `f1`.
Both are corrected below: each prompt's own return value is what's checked
for cancellation.

Verification note: rs.GetObject / rs.GetBoolean / rs.GetReal / rs.GetInteger /
rs.SurfaceDomain / rs.EvaluateSurface / rs.PlaneFromPoints / rs.BoundingBox /
rs.coercebrep / rs.coercemesh signatures were confirmed this session against
the mcneel/rhinoscriptsyntax GitHub source (selection.py, userinterface.py,
surface.py, geometry.py, plane.py, utility.py).

IMPORTANT: the original VBScript calls `Rhino.ProjectPointToSurface` and
`Rhino.ProjectPointToMesh`. Those were legacy RhinoScript (VBScript COM)
methods -- they do NOT exist in rhinoscriptsyntax (confirmed this session by
listing every `def` in rhinoscriptsyntax's surface.py, geometry.py, and
mesh.py: neither name appears anywhere in the module). The nearest modern
equivalent is the RhinoCommon method
`Rhino.Geometry.Intersect.Intersection.ProjectPointsToBreps(breps, points,
direction, tolerance)` (and the mesh counterpart `...ProjectPointsToMeshes`,
same argument order), confirmed via a live McNeel Discourse thread this
session (an OP asking specifically about this signature, answered by McNeel
staff). Rhino's Script Editor auto-converts a plain Python list into the
.NET `IEnumerable<T>` these expect, so no manual `System.Collections.Generic`
wrapping is needed here (also confirmed in that thread). This script uses
that RhinoCommon call directly rather than a nonexistent rs.* wrapper.

Everything else (CopyObject, RotateObject, ScaleObject, BoundingBox,
PlaneFromPoints, AddPlaneSurface) matches the well-established
rhinoscriptsyntax API and mirrors the original VBScript's call pattern
one-for-one. There is no live Rhino available in this environment to
actually execute the script -- run it in Rhino and confirm before relying
on it, especially the projection call above.
"""

import random

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
from Rhino.Geometry import Vector3d
from Rhino.Geometry.Intersect import Intersection

_STICKY_PREFIX = "Sprinkler_"


def _sticky_get(key, default):
    return sc.sticky.get(_STICKY_PREFIX + key, default)


def _sticky_set(key, value):
    sc.sticky[_STICKY_PREFIX + key] = value


def sprinkler():
    old_int = _sticky_get("oldInt", 10)
    old_a_state = _sticky_get("oldAState", [False, False])
    old_small = _sticky_get("oldSmall", 0.9)
    old_large = _sticky_get("oldLarge", 1.1)
    old_min = _sticky_get("oldMin", -20.0)
    old_max = _sticky_get("oldMax", 20.0)

    s_obj = rs.GetObject("Select the object to sprinkle.", preselect=True)
    if s_obj is None:
        return

    a_base = rs.GetPoint("Base point on object.")
    if a_base is None:
        return

    target_filter = rs.filter.surface | rs.filter.polysurface | rs.filter.mesh
    s_targ = rs.GetObject("Select target object.", target_filter, preselect=False)
    if s_targ is None:
        return

    int_copy = rs.GetInteger("How many?", old_int, 1)
    if int_copy is None:
        return
    _sticky_set("oldInt", int_copy)

    a_rand = rs.GetBoolean(
        "Randomize?",
        (("Rotation", "No", "Yes"), ("Scale", "No", "Yes")),
        old_a_state,
    )
    if a_rand is None:
        return
    _sticky_set("oldAState", list(a_rand))

    a_bb = rs.BoundingBox(s_targ)
    if not a_bb:
        print("Could not compute a bounding box for the target object.")
        return

    plane = rs.PlaneFromPoints(a_bb[4], a_bb[5], a_bb[7])

    rs.EnableRedraw(False)
    try:
        width = rs.Distance(a_bb[0], a_bb[1])
        length = rs.Distance(a_bb[0], a_bb[3])
        s_srf = rs.AddPlaneSurface(plane, width, length)

        a_dom_u = rs.SurfaceDomain(s_srf, 0)
        a_dom_v = rs.SurfaceDomain(s_srf, 1)

        a1 = a2 = None
        if a_rand[0]:
            a1 = rs.GetReal(
                "Set one end of the rotation range in degrees. "
                "Choose a number between -180 and 180.",
                old_min, -180, 180,
            )
            if a1 is None:
                return
            a2 = rs.GetReal(
                "Set the other end of the rotation range in degrees. "
                "Choose a number between -180 and 180.",
                old_max, -180, 180,
            )
            if a2 is None:
                return
            _sticky_set("oldMin", a1)
            _sticky_set("oldMax", a2)

        f1 = f2 = None
        if a_rand[1]:
            f1 = rs.GetReal("Smallest scale factor.", old_small, 0.001)
            if f1 is None:
                return
            f2 = rs.GetReal("Largest scale factor.", old_large, f1 + 0.001)
            if f2 is None:
                return
            _sticky_set("oldSmall", f1)
            _sticky_set("oldLarge", f2)

        is_mesh_target = rs.IsMesh(s_targ)
        target_brep = None if is_mesh_target else rs.coercebrep(s_targ)
        target_mesh = rs.coercemesh(s_targ) if is_mesh_target else None
        down = Vector3d(0, 0, -1)
        tolerance = sc.doc.ModelAbsoluteTolerance

        i = 0
        max_attempts = int_copy * 200  # safety valve: original loops forever
        # if the target can never be hit (e.g. a degenerate/rotated target).
        attempts = 0
        while i < int_copy:
            attempts += 1
            if attempts > max_attempts:
                print(
                    "Sprinkler: stopped after {0} attempts, only placed {1} "
                    "of {2} copies (target may not be reachable from the "
                    "seed plane).".format(attempts, i, int_copy)
                )
                break

            par = (random.random() * a_dom_u[1], random.random() * a_dom_v[1])
            seed_pt = rs.EvaluateSurface(s_srf, par[0], par[1])

            if is_mesh_target:
                hits = Intersection.ProjectPointsToMeshes(
                    [target_mesh], [seed_pt], down, tolerance
                )
            else:
                hits = Intersection.ProjectPointsToBreps(
                    [target_brep], [seed_pt], down, tolerance
                )

            if hits:
                a_pt = hits[0]
                x = rs.CopyObject(s_obj, a_base, a_pt)
                if x is None:
                    continue

                if a_rand[0]:
                    dbl_ang = a1 + random.random() * (a2 - a1)
                    rs.RotateObject(x, a_pt, dbl_ang, (0, 0, 1), False)

                if a_rand[1]:
                    factor = f1 + random.random() * (f2 - f1)
                    rs.ScaleObject(x, a_pt, (factor, factor, factor), False)

                i += 1

        rs.DeleteObject(s_srf)
    finally:
        rs.EnableRedraw(True)


if __name__ == "__main__":
    sprinkler()
