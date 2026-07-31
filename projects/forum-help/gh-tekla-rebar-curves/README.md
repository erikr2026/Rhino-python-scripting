# gh-tekla-rebar-curves

Forum thread this responds to (posted 2026-07-21, unresolved, zero replies):
https://discourse.mcneel.com/t/rebar-in-tekla-doesnt-follow-control-polylines-from-gh/221046

## The report

Rhino 8 + Tekla 2023, using the third-party "Live-link 2023.1.15" connector
to push tapered rebar groups from Grasshopper control polylines into Tekla.
Reported symptoms:

- Some rebar groups land significantly offset (poster estimates ~100mm) from
  their control polyline, in an inconsistent direction, despite all offsets
  in the connector set to zero.
- Reversing a guide curve's direction and re-running sometimes fixes the
  placement for the curves it's applied to - but not all problem cases.
- Control polylines with more than 4 points misbehave; the poster's groups
  work correctly up to 4 points but they need more detail than that for
  non-planar tapered shapes.
- Identical input geometry sometimes produces different placement results
  across otherwise-identical solves ("exactly the same input... produce
  different geometry in Tekla").
- No replies on the thread as of this writing.

## Hypothesis

This is a third-party plugin (Live-link), not Grasshopper or
rhinoscriptsyntax/RhinoCommon. Nothing that runs upstream of it, inside GH,
can inspect or change what it does internally with the curve data once it's
handed over. If the bug is in the connector's own coordinate transform
(e.g. it derives a local frame from the curve's seam/start-tangent, or
branches its point-reading logic differently past some internal buffer
size), no amount of GH scripting fixes that - only the vendor can.

What GH scripting *can* do is control what the connector receives, and the
three reported symptoms all point at plausible input-side triggers:

1. **Direction-dependent placement** ("reversing the curve fixes it") means
   the connector is reading *some* orientation-dependent value off each
   curve (start point, start tangent, or seam) and is doing it
   inconsistently across a batch that has no enforced common direction.
2. **>4-point misbehavior** suggests either a hard internal limit, or that
   the connector handles different curve subtypes (Polyline vs interpolated
   NurbsCurve vs whatever GH happened to build) differently, and higher
   point counts are more likely to hit whichever code path is broken.
3. **Non-determinism on identical input** is the most telling symptom: if
   the *shape* is identical but the *underlying object type or internal
   representation* differs between GH solves (e.g. due to caching, rebuild
   order, or how a component reconstructs a curve), the connector could be
   silently taking a different internal path each time even though nothing
   looks different to the user.

None of this is confirmed - it's the most plausible explanation given the
symptoms, and testable without needing access to the connector's source.

## What the script does

`gh_tekla_rebar_curve_normalize.py` is a GH Script/GhPython component you
wire in between your control-polyline generation and whatever component
feeds the Live-link connector. Per curve, it:

- **(a) Forces a consistent curve direction** across the whole batch, by
  reversing any curve whose start tangent opposes a reference direction you
  supply (default world Z). Non-destructive to shape - only changes which
  end is "start." Directly targets symptom 1.
- **(b) Converts every curve to a NurbsCurve** via `Curve.ToNurbsCurve()`,
  regardless of point count, so the connector always receives one
  consistent object type instead of a mix of Polyline/Arc/NURBS curves that
  happen to look the same but may be read differently internally. Targets
  symptom 3.
- **(c) Optionally (off by default) rebuilds curves with more than
  `max_points` control points** via `Curve.Rebuild(...)`, so you can test
  in isolation whether point count itself is the trigger. This is lossy -
  it refits the curve to fewer points, which throws away exact taper detail
  - and it's the one path in this script whose exact API signature could
  not be live-verified this session (network access to the relevant
  RhinoCommon/compute.rhino3d doc pages returned empty content or 403s
  through the proxy here). It's wrapped in try/except so a wrong signature
  reports a failure per curve instead of crashing silently. Confirm the
  real signature yourself before trusting it:
  ```python
  import Rhino
  help(Rhino.Geometry.Curve.Rebuild)
  ```
  run in Rhino 8's ScriptEditor Python 3 console.

Every curve gets a `report` line (original point count, whether it was
reversed, what happened on the rebuild path if attempted) - read that in a
GH Panel before trusting the output for anything, especially the first time
you run this against real bars.

## Honest ceiling on what this can fix

This is a **mitigation to try, not a confirmed fix.** It removes three
plausible *input-side* variables the connector might be reacting to
inconsistently. If the offset and non-determinism persist after running
every curve through this (same reference direction, same curve type, point
count under the reported working threshold), that's real evidence the bug
lives inside Live-link's own code - specifically its coordinate transform
or curve-reading logic - and no GH/Python script sitting upstream of it can
reach that. At that point the right move is reporting a minimal repro (2-3
known-bad bars, before/after screenshots, connector version) to the
Live-link vendor, not more upstream scripting.

If it turns out point count above 4 is a hard connector limit rather than
something sensitive to curve type/direction, that's also outside this
script's reach to fix - the workaround would be a modeling decision (e.g.
whether shorter multi-segment rebar groups are an acceptable substitute for
one long tapered polyline), not something re-parameterizing the same curve
in Grasshopper can paper over.

## Status

Untested against the real connector - the owner has not yet run this
against an actual Tekla push. Confirm on a small batch of known-bad bars
before trusting it on a full model, and update this file with results
either way (mitigated / no change / made it worse) so the next person
looking at this thread has real data instead of another guess.
