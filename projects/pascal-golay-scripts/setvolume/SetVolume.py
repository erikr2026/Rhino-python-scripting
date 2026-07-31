"""SetVolume.py

Python 3 (CPython, PythonNet) port of SetVolume.rvb, for Rhino 8's
Script Editor (ScriptEditor command, F5). Not written for legacy
IronPython/RunPythonScript.

Original: Pascal Golay, SetVolume.rvb (2009).
Ported 2026-07-31.

What it does: scales a selected closed solid (brep/polysurface or closed
mesh) about its own volume centroid so it reaches a user-specified
target volume, then optionally scales a set of other objects by the
same factor about the same center. `Dimensions to scale` (1/2/3) picks
whether the scale is applied along one picked direction, in a plane, or
uniformly in 3D -- since scaling n dimensions by f multiplies volume by
f^n, the actual per-axis factor used is f = (target/current)^(1/n).

Function names/signatures (GetObject, GetObjects, GetInteger, GetReal,
MessageBox, IsBrep, IsObjectSolid, IsMesh, SurfaceVolume, SurfaceVolume-
Centroid, MeshVolume, MeshVolumeCentroid, ScaleObject, GetPoints,
VectorCreate, VectorRotate, PlaneFromFrame, ViewCPlane, EnableRedraw)
verified 2026-07-31 against the rhinoscriptsyntax source on GitHub
(https://github.com/mcneel/rhinoscriptsyntax, rhino-8.x branch,
Scripts/rhinoscript/{selection,userinterface,surface,mesh,object,
pointvector,plane,view,document}.py).

Persisted "last used" defaults (target volume, dimensions-to-scale) use
`scriptcontext.sticky`, mirroring the original's module-level `Private`
variables. Same caveat as in SetbackFillet.py: I could not re-confirm
`scriptcontext.sticky` itself against a live guide page this session
(guide URLs 404'd); its presence is inferred from rhinoscriptsyntax's
own confirmed use of the sibling `scriptcontext.doc`, plus long-standing
convention -- flagging rather than asserting verification that didn't
happen. If unavailable, defaults simply won't persist across runs.

Real API difference found (not a bug, just a modern-API adaptation):
the original indexes `Rhino.MeshVolume(sObj)(0)` for the volume value.
Modern `rs.MeshVolume()` returns a 3-tuple `(meshes_used, total_volume,
error_estimate)` -- volume is index [1], not [0] (verified from the
function's own docstring/source). `rs.SurfaceVolume()` still returns
`(volume, error)` so its `[0]` indexing carries over unchanged, and
`rs.MeshVolumeCentroid()` returns the centroid point directly (not
wrapped in a tuple), unlike the old `(0)`-indexed COM call.

Minor numeric note: the original's volume-factor exponents use
`.333333334` for the 3D case (nine-digit approximation of 1/3, off by
about 1e-9 from the true value). Replaced with exact `1.0/3.0` here --
this changes the result by a negligible, well below any real-world
fabrication tolerance, amount, so it is not treated as a behavioral
change worth preserving verbatim.

`vecDir`/`BP` (the picked 1D-scale direction and base point) are only
Python function-local state here, not sticky -- in the original they
were module-level `Private` vars too, but since `n` is always reset to
0 for the primary object at the start of every run, they never actually
carried a meaningful value across separate script executions; they only
needed to survive across the inner loop within a single run (primary
object, then each "other" object scaled by the same direction), which
plain local variables do just as well.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc

_STICKY_VOL = "SetVolume_oldvol"
_STICKY_DIM = "SetVolume_olddim"


class _Scale1DState:
    def __init__(self):
        self.vec_dir = None
        self.base_point = None


def volume_factor(int_dim):
    if int_dim == 3:
        return 1.0 / 3.0
    if int_dim == 2:
        return 0.5
    return 1.0  # int_dim == 1


def object_volume(obj_id):
    """Returns (volume, centroid) or None if the object isn't closed."""
    if rs.IsBrep(obj_id):
        if not rs.IsObjectSolid(obj_id):
            return None
        vol_data = rs.SurfaceVolume(obj_id)
        cen_data = rs.SurfaceVolumeCentroid(obj_id)
        if vol_data is None or cen_data is None:
            return None
        return vol_data[0], cen_data[0]

    if rs.IsMesh(obj_id):
        vol_data = rs.MeshVolume(obj_id)
        if vol_data is None:
            return None
        cen = rs.MeshVolumeCentroid(obj_id)
        if cen is None:
            return None
        return vol_data[1], cen

    return None


def scale1d(obj_id, cen, f, n, state):
    crnt_plane = rs.ViewCPlane()

    if n == 0:
        pts = rs.GetPoints(True, False, "Base point", "Direction point", 2)
        if not pts or len(pts) != 2:
            return False
        vec_x = rs.VectorCreate(pts[1], pts[0])
        state.vec_dir = vec_x
        state.base_point = pts[0]
    else:
        vec_x = state.vec_dir

    vec_y = rs.VectorRotate(vec_x, 90, crnt_plane.ZAxis)
    rs.ViewCPlane(None, rs.PlaneFromFrame(state.base_point, vec_x, vec_y))
    rs.ScaleObject(obj_id, cen, (f, 1, 1))
    rs.ViewCPlane(None, crnt_plane)
    rs.EnableRedraw(True)
    return True


def scale_by_factor(obj_id, int_dim, cen, f, n, state):
    if int_dim == 3:
        rs.ScaleObject(obj_id, cen, (f, f, f))
    elif int_dim == 2:
        rs.ScaleObject(obj_id, cen, (f, f, 1))
    else:
        if n == 0:
            rs.EnableRedraw(True)
        scale1d(obj_id, cen, f, n, state)


def set_object_volume(obj_id, int_dim, cen, vol, targ, n, state):
    f = (targ / vol) ** volume_factor(int_dim)
    rs.EnableRedraw(False)

    scale_by_factor(obj_id, int_dim, cen, f, n, state)

    result = object_volume(obj_id)
    new_vol = result[0] if result else None
    if new_vol is not None:
        print("Objects scaled by {}. The new volume is {}.".format(f, round(new_vol, 5)))

    return f


def set_volume():
    obj_id = rs.GetObject("Select a closed volume to set.", 8 + 16 + 32, True)
    if obj_id is None:
        return

    other_ids = rs.GetObjects("Select other objects to scale. Press Enter for none.", preselect=False)

    old_dim = sc.sticky.get(_STICKY_DIM, 3)
    int_dim = rs.GetInteger("Dimensions to scale", old_dim, 1, 3)
    if int_dim is None:
        return
    sc.sticky[_STICKY_DIM] = int_dim

    rs.EnableRedraw(False)

    result = object_volume(obj_id)
    if result is None:
        rs.MessageBox("The object is Not closed.")
        rs.EnableRedraw(True)
        return
    vol, cen = result

    old_vol = sc.sticky.get(_STICKY_VOL, 1.0)
    prompt = "Set desired object volume. Current volume is {}".format(round(vol, 5))
    targ = rs.GetReal(prompt, old_vol)
    if targ is None:
        rs.EnableRedraw(True)
        return
    sc.sticky[_STICKY_VOL] = targ

    state = _Scale1DState()
    f = set_object_volume(obj_id, int_dim, cen, vol, targ, 0, state)

    if other_ids:
        for n, other_id in enumerate(other_ids, start=1):
            scale_by_factor(other_id, int_dim, cen, f, n, state)

    rs.EnableRedraw(True)


if __name__ == "__main__":
    set_volume()
