# Louvre facade - Stage 2 (void spheres + fabrication tiling)

Forum thread: https://discourse.mcneel.com/t/custom-louvre-facades-script/221044
(posted 2026-07-21, unresolved as of this writing - only a screenshot
exchange between the poster and other users, no working solution posted).

## Important limitation

I could not see the poster's reference image ("ref b") or their existing
Stage 1 `.gh` file (`CONCEPT_LOUVRE_FILE.gh`). A WebFetch pass on the thread
returned only a text summary of the discussion - no image content came
through, and there's no code snippet posted in the thread either. So this
is **a general-purpose starting point for "randomly placed, evenly
distributed void spheres subtracted from a solid," not a script tuned to
match their specific target pattern.** The poster (or whoever picks this
up) needs to plug in their own Stage 1 geometry and eyeball-tune the
radius/spacing/count parameters against the actual reference image, which
I have no visibility into.

## What it does

`gh_louvre_facade.py` is written for a **Python 3 GhPython/Script component
inside Grasshopper** - it expects `louvre_breps` and the other inputs listed
in its header docstring to arrive as declared GH component inputs, not as
values you set by hand. It will not run standalone (no GH canvas = no
inputs) - say so if a standalone `.py` version is wanted instead.

Two independent pieces:

**1. Randomized void placement + boolean subtraction**
Plain per-louvre `random.uniform` sampling tends to clump (birthday-paradox
clustering) rather than look like the deliberate, fairly-even scatter
typical of perforated/louvre reference patterns - which is likely why the
poster's own attempt "didn't get the random pattern." This script instead:
- Samples a **jittered grid** across each louvre's face UV domain (regular
  grid + per-cell random offset) so coverage stays even.
- Runs a **greedy min-spacing rejection pass** on top (Poisson-disc-style,
  not a full Bridson sampler - fine at this point count) so spheres don't
  overlap or bunch.
- Assigns each accepted point a random radius between `sphere_radius_min`
  and `sphere_radius_max`.
- Subtracts the resulting sphere breps from each louvre via
  `Rhino.Geometry.Brep.CreateBooleanDifference`, gated behind a
  `run_boolean` toggle so placement can be checked visually first (booleans
  are the slow, fragile step - iterate on the scatter pattern with it off).

**2. Fabrication segmentation**
Computes the combined bounding box of the voided facade and lays a grid of
boxes sized to `tile_max_x/y/z`, then boolean-intersects the facade against
each box to produce trimmed per-tile fragments plus a `tile_index` mapping
fragment -> tile. This directly answers "one big panel vs. repeating
tiles": set generous tile_max values and it produces one tile; shrink them
and it splits into a fabricatable grid. It does not do seam/tab joinery,
nesting, or labeling - it's the "can this even be one panel" sizing step,
not a finished shop-drawing tool.

## Unverified / flagged items

- `Brep.CreateBooleanDifference`'s exact signature and empty-array-on-failure
  behavior is stated from training knowledge; a live doc fetch of
  developer.rhino3d.com didn't return usable page content this session.
  Confirm with `help(Rhino.Geometry.Brep.CreateBooleanDifference)` in the
  Rhino Python console before relying on it.
- Tiling assumes a roughly planar, world-axis-aligned facade. A curved or
  angled-in-plan facade would need tiling against a local plane instead -
  not attempted here.
- Sphere radius/count/spacing defaults are not set in the script (component
  inputs, no hardcoded defaults) - there was nothing in the thread to derive
  sensible starting values from, so pick them by eye against the reference.
