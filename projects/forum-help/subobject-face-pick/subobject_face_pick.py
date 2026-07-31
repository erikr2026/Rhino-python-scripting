"""
Workaround for: "SubObjectSelectionEnabled works for polylines, not solid faces"
McNeel forum thread (posted 2026-07-14, unanswered as of 2026-07-31):
https://discourse.mcneel.com/t/subobjectselectionenabled-works-for-polylines-not-solid-faces/220842

REPORTED BUG (per the thread)
------------------------------
The original poster (Stefano Menci) drives ObjectTable.PickObjects with a
PickContext and SubObjectSelectionEnabled = True, inside an automated
integration-testing framework that simulates picks at known TextDot
locations (no real mouse involved). For a polyline this correctly reports
the picked sub-object, e.g. "PolycurveSegment, 2". For a solid (an
Extrusion in the test file) it always reports "Extrusion, InvalidType, -1"
-- component type and index never get filled in, whether the flag is on
or off. Rhino version wasn't stated in the thread.

WORKAROUND STRATEGY
--------------------
Don't fight the picker for the missing component info. The thread's own
setup already gives you the one piece of ground truth the picker is
failing to derive: the 3D point where the "pick" happened (the TextDot
position, or the PickContext's pick point/ray). So:

  1. Let PickObjects / GetObject resolve the *whole object* as it already
     does correctly.
  2. Independently determine which face that whole object's geometry
     the known 3D point sits on, by testing the point against every
     face of the object's Brep form (Extrusion.ToBrep() for extrusions,
     or the Brep itself for polysurfaces) and taking the closest match
     within tolerance.
  3. Report that face index directly. For an automated test comparator
     this is equivalent information to "PolycurveSegment, 2" -- it does
     not require a correctly-populated ComponentIndex/ObjRef from the
     picker at all, which is exactly the part that's demonstrably broken
     for Extrusion objects in this bug report.

This sidesteps the bug rather than fixing Rhino's picker internals --
there is no public API to do that from a script, and the bug looks like
it lives in Rhino's C++ pick machinery for Extrusion sub-object reporting,
not in anything under script control.

ENGINE / HOW TO RUN
--------------------
Targets Rhino 8's Python 3 (CPython via PythonNet), run through the
ScriptEditor command (ScriptEditor -> open this file -> F5), not
RunPythonScript (that launches IronPython 2 regardless of this file's
content).

WHAT IS AND ISN'T VERIFIED THIS SESSION
-----------------------------------------
Verified live this session (WebFetch against the actual thread):
  - The bug description, the API calls named in the OP (ObjectTable.PickObjects,
    PickContext, SubObjectSelectionEnabled), and the exact observed strings
    ("PolycurveSegment, 2" vs "Extrusion, InvalidType, -1").

NOT verified live this session -- developer.rhino3d.com's RhinoCommon API
pages are a JS-rendered SPA that returned only page chrome ("RhinoCommon
API" with no body) to every fetch attempt this session, and the
mcneel/rhinocommon GitHub source paths tried also 404'd. The calls below
are written from training-data knowledge of the RhinoCommon API and are
NOT guaranteed current. Before relying on this script, run these in the
ScriptEditor Python console and confirm:
  - Rhino.Geometry.Extrusion.ToBrep()               -- exact overload/arity
  - Rhino.Geometry.BrepFace.ClosestPoint(Point3d)   -- confirmed pattern per
    the out-parameter rule (returns a tuple: (bool, u, v)); confirm arg/return
    order with help(Rhino.Geometry.BrepFace.ClosestPoint)
  - Rhino.Geometry.BrepFace.FaceIndex / .PointAt(u, v)
  - Rhino.DocObjects.ObjectTable.FindId(Guid)        -- vs. the older/possibly
    obsolete .Find(Guid) overload; try FindId first, fall back to Find
  - Rhino.Input.RhinoGet.GetOneObject / .GetPoint exact signatures and
    return-tuple shape, and Rhino.Input.Custom.GetObjectGeometryFilter.Surface
    (used only in the interactive demo at the bottom of this file, not in
    the core face-lookup function -- if these don't match, swap in whatever
    rs.GetObject()/rs.GetPointOnObject() equivalents work in your version)

The core face-lookup function (find_face_index_at_point) is the part that
matters for the reported bug and depends only on Brep/Extrusion/BrepFace
geometry queries, not on any picker/ComponentIndex API -- so it does not
depend on the specific broken behavior described in the thread.
"""

import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc


def find_face_index_at_point(rhino_obj, test_point, tolerance=None):
    """
    Determine which Brep face of rhino_obj's geometry a known 3D point
    lies on, independent of Rhino's sub-object pick machinery.

    Parameters
    ----------
    rhino_obj : Rhino.DocObjects.RhinoObject
        The whole object already resolved by a normal (non-subobject) pick.
    test_point : Rhino.Geometry.Point3d
        The known pick location (e.g. a TextDot position in the test rig).
    tolerance : float, optional
        Distance tolerance for "on the face". Defaults to
        sc.doc.ModelAbsoluteTolerance.

    Returns
    -------
    int or None
        The BrepFace index (brep.Faces[i].FaceIndex) closest to test_point,
        or None if no face is within tolerance.

    NOTE: Extrusion.ToBrep() call below is UNVERIFIED this session (see
    module docstring) -- confirm the exact overload with help() before
    depending on this in production.
    """
    geo = rhino_obj.Geometry

    if isinstance(geo, rg.Extrusion):
        brep = geo.ToBrep()  # UNVERIFIED: confirm no required args in your Rhino version
    elif isinstance(geo, rg.Brep):
        brep = geo
    else:
        return None

    if brep is None:
        return None

    tol = tolerance if tolerance is not None else sc.doc.ModelAbsoluteTolerance

    best_index = None
    best_dist = float("inf")

    for face in brep.Faces:
        # BrepFace.ClosestPoint has an out u,v signature in RhinoCommon's C#
        # form; under PythonNet that becomes a return tuple per the
        # out-parameter rule -- UNVERIFIED exact tuple shape this session.
        result = face.ClosestPoint(test_point)
        ok, u, v = result  # confirm this unpacks (bool, double, double)
        if not ok:
            continue
        pt_on_face = face.PointAt(u, v)
        dist = pt_on_face.DistanceTo(test_point)
        if dist < best_dist:
            best_dist = dist
            best_index = face.FaceIndex

    if best_index is not None and best_dist <= tol:
        return best_index
    return None


def describe_pick(rhino_obj, test_point, tolerance=None):
    """
    Build a diagnostic string in the same spirit as the thread's own
    "ComponentType, Index" reporting (e.g. "PolycurveSegment, 2"), but
    computed independently of the broken picker path for solids.
    """
    geo = rhino_obj.Geometry
    type_name = geo.GetType().Name  # e.g. "Extrusion", "Brep", "PolyCurve"

    if isinstance(geo, (rg.Extrusion, rg.Brep)):
        face_index = find_face_index_at_point(rhino_obj, test_point, tolerance)
        if face_index is None:
            return "{0}, no face within tolerance".format(type_name)
        return "{0}, BrepFace, {1}".format(type_name, face_index)

    # Fall back to whatever Rhino's normal picker reports for non-solid
    # geometry -- this path is NOT the one reported as broken in the thread.
    return "{0}, (use normal SubObjectSelectionEnabled pick path)".format(type_name)


def run_face_pick_tests(test_cases):
    """
    Batch-mode harness matching the reported use case: an automated
    integration test iterating over known (object, point) pairs rather
    than live mouse picks.

    Parameters
    ----------
    test_cases : list of (System.Guid, Rhino.Geometry.Point3d)
        Object id and the known TextDot/test point on that object.
    """
    doc = sc.doc
    for obj_id, pt in test_cases:
        rhino_obj = doc.Objects.FindId(obj_id)  # UNVERIFIED vs. .Find(obj_id) fallback
        if rhino_obj is None:
            print("Object {0} not found".format(obj_id))
            continue
        result = describe_pick(rhino_obj, pt)
        print("{0} @ {1}: {2}".format(obj_id, pt, result))


def _demo_interactive():
    """
    Small interactive sanity check: pick a solid, then a point on it,
    and report the computed face index. Not part of the automated test
    framework itself -- just a way to confirm find_face_index_at_point
    behaves correctly against real geometry before wiring it into the
    test rig.
    """
    rc, obj_ref = Rhino.Input.RhinoGet.GetOneObject(
        "Select a solid (Extrusion/Brep) face to test", False,
        Rhino.Input.Custom.GetObjectGeometryFilter.Surface
    )
    if rc != Rhino.Commands.Result.Success or obj_ref is None:
        print("No object selected.")
        return

    rhino_obj = obj_ref.Object()
    if rhino_obj is None:
        print("Could not resolve RhinoObject from ObjRef.")
        return

    rc2, pt = Rhino.Input.RhinoGet.GetPoint("Pick a point on that solid", False)
    if rc2 != Rhino.Commands.Result.Success:
        print("No point selected.")
        return

    result = describe_pick(rhino_obj, pt)
    print("Result: {0}".format(result))


if __name__ == "__main__":
    _demo_interactive()
