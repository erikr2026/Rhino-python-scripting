# SubObjectSelectionEnabled: polylines work, solid faces don't

Forum thread: https://discourse.mcneel.com/t/subobjectselectionenabled-works-for-polylines-not-solid-faces/220842
(Stefano Menci, posted 2026-07-14, unanswered as of 2026-07-31)

## Problem (from the thread)

An automated integration-testing framework drives `ObjectTable.PickObjects`
with a `PickContext`, simulating picks at known `TextDot` positions (no real
mouse involved), with `SubObjectSelectionEnabled = True`. Test file
`TestPickObjects.3dm` has two polylines and two solids (Extrusions), each
with a TextDot marking a pick location; script `TestPickObjects.py`
reproduces the issue.

- Pick on a **polyline segment** -> correctly reports the sub-object,
  e.g. `PolycurveSegment, 2`.
- Pick on a **solid (Extrusion) face** -> always reports
  `Extrusion, InvalidType, -1`, with the flag both on and off. Rhino never
  fills in a component type/index for the Extrusion face.

No Rhino version was given in the thread. This looks like a genuine gap or
bug in Rhino's picking machinery for Extrusion sub-object component
reporting, not something under script control to fix directly.

## Workaround approach

Don't try to make the picker report the face correctly — sidestep it. The
integration-test setup already has the one fact the picker fails to derive:
the 3D point where the "pick" happened (the TextDot location itself, or the
`PickContext`'s pick point/ray).

1. Resolve the whole object with a normal pick, as already works.
2. Independently test that known 3D point against every face of the
   object's Brep form:
   - `Extrusion` -> `Extrusion.ToBrep()` to get a real `Brep`.
   - `Brep`/polysurface -> use directly.
3. For each `BrepFace`, call `ClosestPoint` to project the test point onto
   that face's surface, measure the distance back to the test point, and
   take the closest face within `ModelAbsoluteTolerance`.
4. Report that face index directly — equivalent information to
   `PolycurveSegment, 2` for a test comparator, without needing a correctly
   populated `ComponentIndex`/`ObjRef` from the picker (the exact part
   that's broken for Extrusions per the thread).

This is a workaround, not a fix for Rhino's internals — there's no public
API surface to patch the picker's Extrusion component reporting from a
script.

## File

`subobject_face_pick.py` — targets Rhino 8's **Python 3** engine via the
`ScriptEditor` command (open the file, press F5). Do **not** run it via
`RunPythonScript` — that always uses the legacy IronPython 2 engine
regardless of the file's contents.

Key functions:

- `find_face_index_at_point(rhino_obj, test_point, tolerance=None)` — the
  actual workaround. Geometry-only, no dependency on the broken pick path.
- `describe_pick(rhino_obj, test_point, tolerance=None)` — formats a result
  string in the same spirit as the thread's own `"Type, Index"` reporting.
- `run_face_pick_tests(test_cases)` — batch harness matching the reported
  use case: iterate `(object_guid, Point3d)` pairs from a test fixture
  (e.g. derived from the TextDot positions in `TestPickObjects.3dm`)
  instead of live mouse picks.
- `_demo_interactive()` — small manual sanity check (pick an object, pick a
  point on it, print the computed face index) for verifying the core
  function against real geometry before wiring it into the test framework.

## How to test it

1. Open `TestPickObjects.3dm` (or any file with an Extrusion/polysurface).
2. `ScriptEditor` -> open `subobject_face_pick.py` -> F5. This runs
   `_demo_interactive()`: pick a solid, then pick a point on one of its
   faces, and confirm the printed face index matches the face you clicked.
3. To wire it into the existing integration-test framework: replace the
   framework's dependence on `PickObjects`' component-index result (for
   solids only — polylines can keep using the working path) with a call to
   `find_face_index_at_point(rhino_obj, known_textdot_point)`, using the
   TextDot's own 3D position as `test_point`.

## What's unverified

`developer.rhino3d.com`'s RhinoCommon API reference pages are a JS-rendered
SPA — every fetch attempt this session returned only page chrome ("RhinoCommon
API", no body), and the `mcneel/rhinocommon` GitHub source paths tried also
404'd. So the exact signatures below come from training-data knowledge of
the RhinoCommon API, not a live check this session, and should be confirmed
with `help(...)` in the ScriptEditor Python console before depending on this
in production:

- `Rhino.Geometry.Extrusion.ToBrep()` — exact overload/arity.
- `Rhino.Geometry.BrepFace.ClosestPoint(Point3d)` — this has an `out u, out v`
  signature in C#; under PythonNet, per this repo's documented out-parameter
  rule, that becomes a return tuple. The script assumes `(bool, u, v)` —
  confirm the exact shape.
- `Rhino.DocObjects.ObjectTable.FindId(Guid)` vs. the possibly-obsolete
  `.Find(Guid)` — the script uses `FindId`; swap to `Find` if `FindId` isn't
  present in your Rhino version.
- `Rhino.Input.RhinoGet.GetOneObject` / `.GetPoint` and
  `Rhino.Input.Custom.GetObjectGeometryFilter.Surface` — used only in the
  interactive demo, not in the core workaround function. If these don't
  match your Rhino version, swap in `rs.GetObject()` / a point-picking
  equivalent; it doesn't affect `find_face_index_at_point` itself.

The core workaround (`find_face_index_at_point`) only depends on
`Brep`/`Extrusion`/`BrepFace` geometry queries — it does not touch
`ComponentIndex`, `ObjRef`, or `PickContext` at all, so it isn't exposed to
the specific broken behavior reported in the thread even if the exact
`ClosestPoint`/`ToBrep` call shapes need minor adjustment.
