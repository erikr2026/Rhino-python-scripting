# BRIX JOINERY — changelog

Streamlining pass, 2026-07-31. Base state on `main` at commit `c2b7d8e`
(pre-streamline tag creation was blocked by the git proxy). No behavior
changes intended anywhere in this pass — every rewrite is a new,
higher-versioned file; originals are untouched.

## JOINERY ISOLATE BLUE WIP.py -> JOINERY ISOLATE BLUE WIP2.py
- Collapsed a three-pass classify/show/hide structure into one pass —
  same objects shown/hidden, same order, same counts.
- Extracted the Brep/face-color check into `has_blue_face()`.
- Replaced three loose RGB locals with one `TARGET_COLOR` constant (also
  puts the previously-unused `System.Drawing` import to actual use).

## JOINERYSETBLUEFACEWIP.py -> JOINERYSETBLUEFACEWIP2.py
- Hoisted the target-color `Color.FromArgb` call to a module-level
  constant instead of recomputing it per object in the loop.
- Added docstrings, including an explicit (unverified) note on dual-engine
  (Python 3 / IronPython 2) compatibility.
- Left the odd prompt text `"Select Brep faces to color blue (255)"`
  untouched — could be an intentional shop convention, not confirmed
  either way, and user-facing text wasn't in scope to change.

## JOINERY_ORIENT_BLUE_FACE_with_NAME_v2.py -> ...v3.py
- Extracted a duplicated centroid-fallback block into `get_centroid()`.
- Extracted a repeated non-empty-string check into `has_text()`.
- **Flagged, not fixed — likely real bug in the original (present in both
  v2 and this v3, since fixing it would be a behavior change):** the
  `if __name__ == "__main__":` block at the end of the script calls
  `orient_layout_and_label()` **twice** in a row. That means every run of
  this script does the full select → orient → label flow twice — two
  Rhino selection prompts, two project-name dialogs. This looks like an
  unintentional copy-paste duplication rather than a deliberate double
  pass. Left exactly as-is per the no-behavior-change rule for this pass,
  with an inline comment flagging it — **worth confirming with whoever
  runs this script whether the double invocation is intentional.**

## New: JOINERY_INTERSECTION_SLOT_CUTTER.py (2026-08-06)

New script, not a rewrite of an existing one. Cuts notch/dado intersection
slots into a 1st set of zero-thickness surfaces, sized to receive a 2nd
set of "cutting" surfaces that pass through them — the standard BRIX
flat-panel notch joint. Workflow: select 1st-set surfaces, select 2nd-set
(cutting) surfaces, enter 2nd-set material thickness. Slot width =
thickness + 1/16" oversize, converted to the document's actual model unit
system (not hardcoded assuming inches). The slot's open end is
auto-detected against S1's nearest naked boundary edge — never
user-picked. Handles three cases per S1/S2 intersection: (1) the common
case, one end already on S1's boundary → open end there, semicircular cap
at the far (interior) end where S2's own edge sits; (2) neither
intersection-curve endpoint starts on a boundary → ray-casts a line from
the interior end, extended past the nearer endpoint, to find where it
actually crosses S1's boundary, then treats that as case (1); (3) both
ends already on a boundary (S2 passes fully through S1) → straight
full-width channel, no semicircle.

**NOT TESTED AGAINST LIVE RHINO GEOMETRY.** No Rhino install is available
in the authoring environment. Every RhinoCommon call was checked against a
live pull of developer.rhino3d.com's RhinoCommon API JSON data source this
session (method signatures, out/ref-parameter shapes, return types) — not
against a running Rhino instance. Flagging the specific parts most likely
to need real-world correction on first run:

- **`BrepFace.Split(curves, tolerance)` + face-removal pass (algorithm
  step 7).** Confirmed via live docs that `Split` returns a whole new
  `Brep` (or `None` on failure) rather than modifying the face's parent
  Brep in place — the script is written for that return-a-new-Brep
  behavior, but the *practical* success rate of `Split` against
  real-world outline curves it's never been fed before (near-boundary
  curves that graze S1's edge, multiple overlapping slot outlines on one
  panel, an outline curve whose extended segments land just outside S1's
  original trim) is unverified. If `Split` returns `None` or an
  unexpected face count on real geometry, that's the first thing to
  debug.
- **The ray-cast boundary-crossing search** (`find_boundary_crossing`,
  used when neither end of an S1/S2 intersection curve starts near a
  naked edge) picks the crossing point nearest the approximate near
  endpoint out of all `Intersection.CurveCurve` hits against every naked
  boundary curve. This is a reasonable heuristic for typical convex-ish
  panel edges but hasn't been tested against a concave or multi-edge
  panel boundary where the ray could cross more than one naked edge
  before reaching the intended exit.
- **`BOUNDARY_SNAP_MULTIPLE` (25x tolerance) and `EDGE_OVERSHOOT_MULTIPLE`
  (10x tolerance)** module constants are development placeholders, not
  tuned against real fabrication tolerances — same caveat pattern as the
  side-extension/offset placeholders already flagged in this repo's
  `shell-bisector-t-surface` project.
- The semicircular-cap construction (`Arc(pointA, tangentA, pointB)` with
  the chord perpendicular to the tangent) is standard, low-risk geometry,
  but the very first real run should visually confirm the cap actually
  lands centered on S2's edge and bulges the correct direction (away from
  the open end, into the panel) before trusting it on production parts.

## Fix: polysurface support (2026-08-06, same day)

First real-Rhino run immediately hit a hard failure: both sets were
restricted to single-face Breps, and the owner's actual 2nd-set objects
are polysurfaces (2 faces) — every 2nd-set surface got skipped, aborting
the whole run. The "zero-thickness surfaces" requirement never meant
single-face only; that restriction was an unnecessary narrowing of the
original algorithm design, not something the owner asked for.

Reworked the core geometry to support single-face or multi-face Breps on
both sets:
- `Intersection.SurfaceSurface(face, face, ...)` (looped per S1-face ×
  S2-face pair) replaced with a single `Intersection.BrepBrep(brep1,
  brep2, tolerance)` call per S1/S2 pair — intersects across every face of
  both Breps at once, confirmed via live docs to have the identical
  `(bool, Curve[], Point3d[])` return shape as `SurfaceSurface`.
- New `face_and_plane_for_curve()` matches each resulting intersection
  curve back to the specific S1 face it actually lies on, via
  `Brep.ClosestPoint(midpoint, 0.0)` → `ComponentIndex` → that face's
  `TryGetPlane()`. Necessary because a polysurface's faces can sit in
  different planes — the slot outline has to be built in the plane of the
  face it actually crosses, not one plane assumed for the whole S1
  object. Confirmed via live docs: `maximumDistance <= 0` means
  unlimited-range search (not zero-range), and `ci.ComponentIndexType`
  can come back `BrepEdge` as well as `BrepFace` (a curve landing exactly
  on a seam) — that case is treated as a skip-with-warning, not a crash.
- The single-face `BrepFace.Split(curves, tolerance)` + per-face-index
  removal loop from the first draft is gone entirely, replaced by a
  whole-Brep `Brep.Split(curves, tolerance)` (confirmed via live docs:
  returns `Brep[]` piece array, not a single Brep) done ONCE per S1 across
  all its faces and all its slot outlines together. This sidesteps a real
  problem the per-face approach would have hit on a polysurface needing
  cuts on more than one face: splitting face 0 first would shift face 1's
  index in the result, corrupting a second sequential per-face split.
  Piece classification (keep vs. discard-as-slot-hole) now checks each
  piece's centroid against every outline's own stored plane (each outline
  now carries the plane it was built in, since different outlines on the
  same S1 can belong to different faces), and multiple surviving material
  pieces are rejoined with `Brep.JoinBreps` (confirmed via live docs: a
  2-arg `(breps, tolerance)` overload exists, no `angleTolerance` required).

Still **NOT TESTED AGAINST LIVE RHINO GEOMETRY** — same caveat as above,
now also covering the new `Brep.ClosestPoint`/whole-Brep-`Split`/
`JoinBreps` calls specifically. The face-matching step
(`face_and_plane_for_curve`) is the newest, least-exercised part of the
algorithm and the first thing to check if a polysurface run behaves
unexpectedly.

## Fix: PythonNet overload ambiguity on Brep.Split (2026-08-06, same day)

Second real-Rhino run, immediately after the polysurface fix above, hit:
`Multiple targets could match: Split(IEnumerable[Brep], float),
Split(IEnumerable[Curve], float)`. `Brep` has both a
`Split(IEnumerable<Brep>, tolerance)` overload (splitting with cutter
Breps) and a `Split(IEnumerable<Curve>, tolerance)` overload (splitting
with curves, the one this script actually wants) at the identical 2-arg
arity — PythonNet can resolve overloads by argument *type*, but a plain
Python `list` carries no static CLR element type, so it can't tell which
overload a bare `[curve1, curve2, ...]` list is meant to satisfy.

Fixed by explicitly typing the argument as a real `Curve[]` before the
call: `curve_array = System.Array[rg.Curve](outline_curves)` (new `import
System` added), then `brep1.Split(curve_array, tolerance)`. Checked the
rest of the script for the same failure mode: `Curve.JoinCurves` and
`Brep.JoinBreps` calls are safe as-is, since neither has a same-arity
overload set spanning two different element types the way `Brep.Split`
does — only `Brep.Split` needed the explicit array typing.

**General lesson for this whole class of RhinoCommon method (any method
overloaded across different collection *element* types at the same
argument count):** a plain Python list is not enough under PythonNet:
wrap it as `System.Array[ElementType](python_list)` before the call. Adding
this as a standing rule to `keel.md` / this project's coding-conventions
section, since it's a real, hit-on-first-run bug class, not a one-off.

Still **NOT TESTED AGAINST LIVE RHINO GEOMETRY** beyond confirming this
specific error no longer reproduces on paper (no Rhino available in the
authoring environment) — needs a real re-run to confirm the fix actually
clears the error and the resulting cut geometry is correct.

## Fix: leftover sliver at the opening + slot length pullback
(2026-08-06, same day, first successful real-Rhino run + owner feedback)

Third real run actually produced correct-looking geometry, with two real
issues the owner caught by eye on the result:

1. **Leftover material sliver right at the slot's opening.** The open
   end's closing segment was built at a fixed, tiny overshoot
   (`EDGE_OVERSHOOT_MULTIPLE = 10x` the document's absolute tolerance —
   typically a few thousandths of a unit). Wherever S1's actual boundary
   edge isn't exactly perpendicular to the slot's own direction (the
   normal case — panel edges are rarely square to every slot crossing
   them), that tiny fixed-distance overshoot doesn't reliably clear the
   true edge on both corners of the outline, leaving a small triangular
   sliver of material behind. Fixed by removing the tolerance-based
   overshoot entirely and reusing the panel-scaled `search_length` value
   (2x the S1 bounding-box diagonal, already computed per-S1 for the
   ray-cast search) as the overshoot distance instead. This is safe and
   free: `Brep.Split()` already trims the cutting curve to S1's actual
   surface domain, so overshooting generously past the true edge changes
   nothing about where the final cut lands — it just guarantees the
   outline always fully clears the boundary regardless of its local
   angle. `EDGE_OVERSHOOT_MULTIPLE` constant removed.
2. **Slot ran too far in — the round cap should stop short of the actual
   S2 intersection by half the 2nd-set thickness**, not sit exactly at
   it. Added a new `cap_pullback` parameter, threaded through
   `outlines_for_intersection_curve()` into `build_capped_outline()`
   only (a full-through channel has no cap, so it's unaffected). In
   `main()`, `cap_pullback = thickness / 2.0` is computed from the
   owner-entered 2nd-set thickness and passed down. `build_capped_outline`
   clamps the pullback so it can never invert the slot (always keeps at
   least `join_tolerance` of length even if `cap_pullback` exceeds the
   curve's natural length).

Still **NOT TESTED AGAINST LIVE RHINO GEOMETRY beyond this one owner
screenshot** — the sliver fix in particular (generous overshoot relying
on `Brep.Split()`'s own trimming) should be re-checked on the next real
run to confirm no new artifacts appear at the opening.
