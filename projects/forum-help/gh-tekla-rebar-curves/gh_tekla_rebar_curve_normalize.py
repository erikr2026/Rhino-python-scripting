"""
GH Tekla rebar control-polyline normalizer (pre-processing, upstream of the
Tekla-Grasshopper connector).

Context: McNeel forum thread (posted 2026-07-21, unresolved, zero replies):
https://discourse.mcneel.com/t/rebar-in-tekla-doesnt-follow-control-polylines-from-gh/221046
Reported against Rhino 8 + Tekla 2023 + "Live-link 2023.1.15" (third-party
Tekla-GH connector). Symptoms: some tapered rebar groups land ~offset from
their control polyline despite zero offset set; reversing a guide curve's
direction sometimes fixes placement; polylines with more than 4 control
points misbehave; identical inputs sometimes produce different results
across solves (non-deterministic).

THIS IS A MITIGATION TO TRY, NOT A CONFIRMED FIX. The bug is very likely
inside the Live-link connector's own coordinate transform / curve-reading
code, which lives outside Grasshopper and outside this script's reach. If
that's where it actually lives, nothing run upstream in GH can guarantee a
fix - this script only removes a few plausible *inputs* to that bug (mixed
curve types/parameterizations, inconsistent start-tangent direction across
a batch, unusually high point counts) so you can test whether they're
contributing factors. If the offset/non-determinism persists after running
every curve through this, that's evidence the bug is downstream, inside the
connector, and needs to be reported to Live-link's vendor with a repro.

Component compatibility: written in Python 2/3 compatible syntax (no
f-strings, no type hints) so it runs unmodified in either GH component type:
  - Classic "GhPython Script" component (IronPython 2 engine) - most GH
    definitions still use this by default.
  - Rhino 8's newer "Script" component set to Python 3 (CPython/PythonNet).
Wire it in ahead of whatever component feeds curves into the Live-link
Tekla connector; feed its "curves_out" output into the connector instead of
your original curves.

Inputs (GH component inputs, injected as globals by Grasshopper):
  curves        : list[Curve]  - the control polylines/curves as currently
                  built, before being handed to the Tekla connector.
  ref_dir       : Vector3d, optional - a fixed reference direction used to
                  force a consistent curve direction across the whole
                  batch (see "Direction normalization" below). Defaults to
                  world Z (0,0,1) if not wired; pick whatever global axis
                  is roughly aligned with your hull's long axis / rebar run
                  direction for a more meaningful flip decision.
  max_points    : int, optional - control-point-count threshold above which
                  a curve is flagged (default 4, matching the forum report
                  that >4 points is where it misbehaves).
  do_rebuild    : bool, optional - if True, attempt Curve.Rebuild(...) on
                  flagged curves (see "Point-count normalization" below).
                  Default False - this path is UNVERIFIED (see note below)
                  and lossy-by-nature for any curve that isn't already a
                  degree-3 NURBS with exactly max_points control points, so
                  treat it as an experiment, not a default-safe transform.

Outputs:
  curves_out    : list[Curve]  - normalized curves, same order/count as
                  input. Feed this into the Tekla connector.
  report        : list[str]    - one diagnostic line per curve: original
                  point count, whether it was reversed, whether/why a
                  rebuild was attempted or skipped. Read this in a GH Panel
                  before trusting the output - it tells you exactly what
                  was changed on each curve.

What this does and why:

(a) Direction normalization (default ON, non-destructive to shape).
    The forum report that "unflipping the guide curve direction" fixes
    placement points at the connector reading *some* orientation-dependent
    quantity off each curve (its seam, start point, or start tangent) and
    using it inconsistently depending on which way the curve happens to be
    built - which is exactly the kind of thing that looks "random" if
    curves in a batch have no enforced common direction. This forces every
    curve to point the same way relative to a fixed reference: reverses it
    only if its start tangent opposes ref_dir. This does not change the
    curve's geometry at all, only which end is "start" - so it's the
    lowest-risk thing to try first, and the most consistent with what
    the forum poster already observed empirically.

(b) Type/parameterization normalization (default ON, shape-preserving).
    Runs every curve through Curve.ToNurbsCurve() regardless of point
    count. This doesn't change point count or degree - it converts
    PolylineCurve/ArcCurve/etc. into their exact-shape NurbsCurve
    equivalent. Rationale: if curves in the same GH definition get built by
    different paths (e.g. some via explicit Polyline, some via
    Curve.CreateInterpolatedCurve, some rebuilt by a prior operation), the
    connector may be reading them through different code paths internally
    and behaving differently depending on which one it got - which would
    also explain the reported non-determinism (identical *shape*, but not
    necessarily identical *underlying object type*, especially if any part
    of the GH history involves caching/rebuild across solves). Handing the
    connector one consistent object type for every curve removes that
    variable without changing the shape at all.

(c) Point-count / rebuild normalization (default OFF, opt-in, LOSSY).
    Curve.Rebuild(pointCount, degree, preserveTangents) is a documented
    RhinoCommon method for re-fitting a curve to a target point count and
    degree, but ITS EXACT SIGNATURE WAS NOT LIVE-VERIFIED THIS SESSION -
    every attempt to fetch the live RhinoCommon/compute.rhino3d API pages
    for it returned empty content or a 403 through the network path
    available here. The call below is wrapped in try/except specifically
    because of that: if the signature is wrong for your Rhino build, it
    will report the failure per-curve instead of crashing the whole batch
    or silently doing nothing. Before relying on this path, run this in
    Rhino 8's ScriptEditor Python 3 console to confirm the signature on
    your own install:
        import Rhino
        help(Rhino.Geometry.Curve.Rebuild)
    Even if the signature is right, rebuilding a >4-point curve down to
    fewer points throws away the exact taper detail the forum poster said
    they need - do NOT default this on. It's here so you can test, on a
    couple of known-bad bars, whether point count specifically is the
    trigger, isolated from (a) and (b) above. If it turns out the connector
    truly can't handle >4 control points at all, that's a hard ceiling this
    script cannot fix - the polyline data has to change to work around it,
    which is a modeling decision, not a scripting one.

Run/engine notes:
  - No file I/O, no document modification - pure curve transform. Safe to
    re-run repeatedly while iterating on the rest of the definition.
  - `report` is deliberately verbose per-curve; if you're running batches
    of dozens of bars, pipe it through a Panel with word-wrap on, or filter
    it in GH for lines containing "REVERSED" or "REBUILD FAILED" to spot
    what actually changed.
"""

import Rhino.Geometry as rg


def _get_ref_dir(ref_dir):
    if ref_dir is None:
        return rg.Vector3d(0, 0, 1)
    v = rg.Vector3d(ref_dir)
    if not v.Unitize():
        return rg.Vector3d(0, 0, 1)
    return v


def _normalize_one(crv, ref_dir, max_pts, do_rebuild):
    """Returns (normalized_curve, report_line)."""
    if crv is None:
        return None, "SKIPPED: null input curve"

    log = []

    # Work on a duplicate - never mutate the caller's original curve object.
    working = crv.DuplicateCurve()
    if working is None:
        return crv, "SKIPPED: DuplicateCurve() failed, passing input through unchanged"

    # --- (b) type/parameterization normalization ------------------------
    as_nurbs = working.ToNurbsCurve()
    if as_nurbs is not None:
        working = as_nurbs
        log.append("converted to NurbsCurve")
    else:
        log.append("ToNurbsCurve() failed, kept original curve type")

    orig_pt_count = None
    try:
        orig_pt_count = working.Points.Count
    except AttributeError:
        # working isn't a NurbsCurve (ToNurbsCurve failed above) - fall back
        # to control-point count via a generic curve query where possible.
        orig_pt_count = None

    # --- (a) direction normalization --------------------------------------
    reversed_flag = False
    tangent = working.TangentAtStart
    if tangent.IsValid and tangent.Length > 1e-9:
        dot = tangent * ref_dir
        if dot < 0.0:
            ok = working.Reverse()
            if ok:
                reversed_flag = True
                log.append("REVERSED (start tangent opposed ref_dir)")
            else:
                log.append("Reverse() FAILED - direction left as-is, check manually")
    else:
        log.append("start tangent invalid/zero-length - direction check skipped")

    # --- (c) optional point-count rebuild (experimental, off by default) --
    if do_rebuild and orig_pt_count is not None and orig_pt_count > max_pts:
        try:
            rebuilt = working.Rebuild(max_pts, 3, True)
            if rebuilt is not None:
                working = rebuilt
                log.append(
                    "REBUILD applied: {0} pts -> {1} pts, degree 3 "
                    "(UNVERIFIED signature - confirm result visually)".format(
                        orig_pt_count, max_pts
                    )
                )
            else:
                log.append(
                    "REBUILD FAILED: Rebuild() returned None, kept "
                    "{0}-point curve unchanged".format(orig_pt_count)
                )
        except Exception as ex:
            log.append(
                "REBUILD FAILED: {0} - Curve.Rebuild signature may not match "
                "this Rhino build, kept {1}-point curve unchanged".format(
                    ex, orig_pt_count
                )
            )
    elif orig_pt_count is not None and orig_pt_count > max_pts:
        log.append(
            "FLAGGED: {0} control points > max_points={1} threshold from the "
            "forum report - do_rebuild is off, curve passed through as-is. "
            "Set do_rebuild=True to test the lossy rebuild path.".format(
                orig_pt_count, max_pts
            )
        )

    pt_count_str = str(orig_pt_count) if orig_pt_count is not None else "unknown"
    summary = "pts={0} | {1}".format(pt_count_str, "; ".join(log) if log else "no changes")
    return working, summary


# ---------------------------------------------------------------------------
# GH component entry point. `curves`, `ref_dir`, `max_points`, `do_rebuild`
# are injected as globals by Grasshopper when this file is the content of a
# Script/GhPython component with matching input names.
# ---------------------------------------------------------------------------

_ref_dir = _get_ref_dir(globals().get("ref_dir", None))
_max_pts = globals().get("max_points", None)
if _max_pts is None:
    _max_pts = 4
_do_rebuild = bool(globals().get("do_rebuild", False))

_input_curves = globals().get("curves", None)
if _input_curves is None:
    _input_curves = []
elif not isinstance(_input_curves, list):
    _input_curves = [_input_curves]

curves_out = []
report = []

for _i, _c in enumerate(_input_curves):
    _norm, _line = _normalize_one(_c, _ref_dir, _max_pts, _do_rebuild)
    curves_out.append(_norm)
    report.append("curve[{0}]: {1}".format(_i, _line))
