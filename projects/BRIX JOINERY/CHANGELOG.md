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
