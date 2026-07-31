# Grasshopper: applying the same routine across several offset lines (data trees)

Forum thread: https://discourse.mcneel.com/t/applying-the-same-gh-routine-across-several-objects/221292
(posted 2026-07-29 by Juan Esteban Velasquez Rojas)

## The problem, as described

A GH routine projects a geology profile (soil-layer interface curves) onto a
topography mesh along ~40 parallel offset lines (cross-sections), and computes
soil-layer thickness at each cross-section. It works for one offset line.
With all ~40 connected, the OP says the graph "is not doing the right thing" -
he tried graft/flatten combinations without getting consistent results.

## Existing partial answers in the thread (credit)

- **Joseph_Oster** pointed at Hops and/or Data Input/Output components as a
  possible restructuring approach - a reasonable direction (Hops lets you
  wrap the single-line logic as a black box and iterate it), but no worked
  example was posted.
- **Artstep** posted a corrected `.gh`/`.ghx` file with an offer to walk
  through it live, plus a tip to enable *Display > Draw Full Names* to see
  already-available component outputs that were hidden by default names.
  That's a real, working fix - if the OP's actual file is a good match for
  it, it's likely the faster path for him specifically.

Neither reply had a public follow-up from the OP confirming resolution as of
this writing, and the file-based fix isn't reproducible or explainable in a
GH-agnostic text answer, which is the gap this addresses.

## What this adds

`gh_datatree_multi_object.py` is a from-scratch GHPython (Python 3) script
component that reconstructs the described workflow, built specifically to
demonstrate *why* native graft/flatten breaks down here and what the correct
fix actually is, rather than to hand over a working replacement file.

**Important limitation:** the OP's original script, exact component graph,
and real geometry (mesh, curves, offset lines) were not available - only his
prose description and the thread replies. Treat the script as a teaching
template to adapt to his actual inputs, not a drop-in fix. It has not been
run inside Rhino/Grasshopper (no install available in this environment);
correctness was reasoned through against RhinoCommon API knowledge, and one
piece (see caveat below) is flagged explicitly as unverified rather than
asserted with false confidence.

## The core data-tree concept

Native GH components apply one operation across whole data trees using a
fixed branch-matching rule (longest-list, cross-reference, etc). That's
invisible and harmless with exactly one branch - there's nothing to match
against. With ~40 offset lines, every component downstream that takes more
than one tree input has to decide how to zip branch `{0}` of the offset
lines against branch `{0}` of the geology curves, the mesh-projection
results, and the thickness maths. If those trees don't already share
identical path structure, GH's default matching silently reuses the wrong
branch or merges unrelated cross-sections - which looks exactly like "it's
not doing the right thing" without an outright error.

**Graft and Flatten change WHERE data lives in the tree. They don't tell a
component HOW to iterate row-by-row.** Once there are several independent
"rows" (cross-sections) that each need their own computation against shared
reference data (one mesh, one set of geology curves), the fix isn't more
graft/flatten juggling - it's iterating branches explicitly and keeping
purely-reference data (mesh, geology curves) un-treed, so nothing can
cross-contaminate between lines regardless of how many there are.

The script does this with a plain Python loop over `offset_lines.Paths`,
using `Grasshopper.DataTree` and setting each output branch's `GH_Path`
explicitly equal to the corresponding input path - so line 12's thickness
values can never end up computed against line 3's ground curve.

## Unverified item

The exact RhinoCommon signatures for
`Rhino.Geometry.Intersect.Intersection.ProjectPointsToMeshes` and
`Intersection.CurvePlane` were not confirmed against the live API docs this
session (the docs site is JS-rendered and WebFetch could not retrieve
content beyond the page title). They're written from API knowledge and are
plausible, but should be checked with `help(...)` in the Rhino Python
editor before trusting argument order or `CurvePlane`'s exact return shape
(assumed here to return `(bool, CurveIntersections)`).
