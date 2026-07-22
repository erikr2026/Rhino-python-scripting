# shell-bisector-t-surface

Standalone Rhino Python script (`rhinoscriptsyntax` + `RhinoCommon`, CPython 3 via
Rhino 8's PythonNet bridge). Run via Rhino 8's **ScriptEditor** command (type
`ScriptEditor`, open this file, press F5) — **not** `RunPythonScript`, which
invokes the legacy IronPython 2 engine instead and will fail on this script
(confirmed 2026-07-22: `RunPythonScript` choked on a non-ASCII docstring
character with a Python-2-only encoding-declaration error). Also **not** a
Grasshopper component (this script gathers its own input with `rs.GetObject`;
GH components get inputs injected as globals instead).

**Status (2026-07-22): implementation written, in progress on real-Rhino
testing.** The geometry algorithm below was worked out, reviewed, and
implemented in `shell_bisector_t_surface.py`. First real-hull test run
surfaced a real design issue (see Lessons in the project memory file):
Stage 1 originally offset the *entire* multi-panel hull as one polysurface
before picking the two panels it needed, which fails silently on complex
real geometry. Fixed to explode the shell first and offset only the two
selected panels individually — that's all anything downstream ever uses.
Expect several more revisions once testing continues — see Testing plan
below.

## What it does

Takes a shell polysurface, explodes it, offsets the two selected panels
individually (not the whole shell — offsetting an entire multi-panel hull at
once is fragile on real geometry and unnecessary, since nothing downstream
needs the other panels offset), computes a "bisector surface" between them
(the surface bisecting the dihedral angle along their shared seam), builds a
T-shaped junction off that bisector, offsets the bisector both directions,
intersects those offsets against the *original* (unoffset) shell, and lofts
connecting surfaces between those intersection curves and the T's long edges.

## Parameters

```python
OFFSET_DISTANCE = 2.0              # distance to offset the two selected panels
BISECT_SURFACE_1_INDEX = 0         # index of first surface to bisect (within the exploded original shell)
BISECT_SURFACE_2_INDEX = 1         # index of second surface to bisect
BISECTOR_DIRECTION = 1             # 1 outward, -1 inward
BISECTOR_OFFSET_DISTANCE = 0.5     # offset the bisector surface both directions (thin sandwich)
T_ARM_PERPENDICULAR_OFFSET = 1.0   # T-arm perpendicular to bisector
T_ARM_PARALLEL_OFFSET = 0.75       # T-arm parallel (along bisector)
BISECTOR_START_POINT_PARAMETER = 0.5  # 0-1 param along bisector seam for T origin

# Two gaps in the original spec — assumed defaults, confirm/tune during testing:
BISECTOR_SURFACE_REACH = OFFSET_DISTANCE * 1.5  # how far the bisector extends from the seam
T_ARM_WIDTH = min(T_ARM_PERPENDICULAR_OFFSET, T_ARM_PARALLEL_OFFSET) * 0.2  # T-arm strip width

# Tuning knobs
BISECTOR_SAMPLE_COUNT = 20          # points sampled along the seam for bisector construction
DEBUG = True
STOP_AFTER_STAGE = None             # "offset" | "bisector" | "t_geometry" | "bisector_offset" | "intersect" | "loft"
```

**Why the two new parameters exist:** the original spec had no length/reach for
the bisector surface itself (only `BISECTOR_OFFSET_DISTANCE`, a thin ±0.5 *sandwich*
offset of the whole surface, not a footprint extension) — but for the later
intersection step against the original shell to be geometrically possible, the
bisector has to physically reach back across roughly `OFFSET_DISTANCE`. Similarly
there was no width/thickness for the T-arms, only offset *lengths*. Both defaults
above are starting points, not verified-correct values — expect to retune both
once testing on a real shell.

## Algorithm

**`compute_bisector_surface`** — no built-in Rhino bisector primitive, so:
1. Find the shared seam between the two chosen offset panels: try matching naked
   edges first (`brep.DuplicateNakedEdgeCurves(True, True)` on each single-face
   Brep, match by endpoint/midpoint distance within tolerance); fall back to
   `Rhino.Geometry.Intersect.Intersection.BrepBrep(brep_a, brep_b, tol)` if no
   naked-edge match is found (offset can introduce small gaps on curved panels).
2. Sample the seam curve (`Curve.DivideByCount`); at each sample get each
   surface's normal via `Face.ClosestPoint` + `Face.NormalAt` — **flip sign if
   `BrepFace.OrientationIsReversed`** (`NormalAt` ignores that flag, a real
   gotcha).
3. Bisecting vector per sample = `normalize(normal_a + normal_b)`, negated if
   `BISECTOR_DIRECTION == -1`. This assumes the two panels' face normals are
   already consistently oriented — if the real hull shell has mixed-orientation
   panels after `ExplodePolysurfaces`, add a pre-flight sanity check (e.g. compare
   against a bounding-box-center-to-panel-centroid heuristic) before trusting this.
4. Project each seam point along its bisecting vector by `BISECTOR_SURFACE_REACH`
   to get a second "reach" curve; loft seam curve + reach curve (`rs.AddLoftSrf`,
   straight sections) into the bisector surface. Bake the seam and reach curves to
   a debug layer regardless of downstream success.

**`build_t_geometry` + `extract_t_edges`** — sidesteps "long vs. end-cap edge"
classification by constructing the 4 long edges directly instead of extracting
them after the fact:
1. Get a local frame at `BISECTOR_START_POINT_PARAMETER`: surface normal
   (perpendicular-arm direction), seam tangent (parallel-arm direction), their
   cross product (shared width axis). Re-orthogonalize if the two aren't close to
   perpendicular in practice.
2. Build the 4 long edges as explicit line pairs offset by `±T_ARM_WIDTH/2` along
   the width axis (2 for the perpendicular arm, 2 for the parallel arm).
3. Loft each pair into a strip, join into one T-Brep (non-fatal if join doesn't
   fully merge — the 4 tracked curves don't depend on it).
4. `extract_t_edges` returns those 4 tracked curves directly, plus an optional
   debug cross-check against `DuplicateNakedEdgeCurves` count (never used to make
   the actual long/short decision).

**`intersect_surfaces`** — brute-force pairwise, don't assume index correspondence
between offset-shell panel indices and the original shell's exploded surface list
(not guaranteed stable). Test each of the 2 bisector-offset Breps against every
original-shell surface via `Intersection.BrepBrep`. Most pairs legitimately return
empty; zero curves across *all* pairs for one offset-bisector Brep is the real
error case (surface a message pointing at `BISECTOR_SURFACE_REACH` being too
short). Bake all found curves regardless.

**`loft_surfaces`** — combine intersection curves + T long-edges, sort by
projecting each curve's midpoint (`PointAtNormalizedLength(0.5)`) onto the seam
tangent axis, reverse any curve whose start point is closer to the previous
curve's end than its start (anti-twist prep), then `rs.AddLoftSrf`.

**`main()`** — one undo record wrapping the whole run
(`Rhino.RhinoDoc.ActiveDoc.BeginUndoRecord`/`EndUndoRecord` directly — the
`rs.BeginUndoRecord` wrapper is known-unreliable). Each stage bakes its own output
as it computes, so partial progress stays visible even if a later stage fails.
`rs.EnableRedraw(False)` only after all `rs.GetObject` prompts finish.

## Layer scheme

```
ShellBisector::01_OffsetShell
ShellBisector::02_BisectorSeam        (seam + reach curves, debug)
ShellBisector::03_BisectorSurface
ShellBisector::04_TGeometry
ShellBisector::05_BisectorOffsets
ShellBisector::06_IntersectionCurves
ShellBisector::07_FinalLoft
```

Final `rs.AddObjectsToGroup` covers only the "real" outputs (T surface, bisector,
bisector offsets, final loft) — debug/intermediate curves stay ungrouped so you
can hide/delete them independently.

## Testing plan

0. **Verify API signatures in Rhino's own Python console first** —
   `help(rs.AddLoftSrf)`, `help(rs.OffsetSurface)`, and a scratch test of
   `Intersection.BrepBrep(...)` / `Curve.DivideByCount(...)` return shapes. This
   queries the actual installed API rather than possibly-stale docs and needs no
   network access. Note confirmed signatures as a comment at the top of the script
   once done — the implementation below used trained-knowledge signatures where
   not otherwise notable, since live doc domains (`developer.rhino3d.com`,
   McNeel forum) weren't reachable from the Claude Code environment used to design
   this (network policy gap, not a permanent block — see
   `memory/projects/rhino-python-scripting.md` for the environment note).
1. Start on a trivial 2-panel test shell (e.g. an open box corner), not the real
   hull — isolates bisector-algorithm bugs from shell-complexity bugs.
2. Use `DEBUG` / `STOP_AFTER_STAGE` to stop after any named stage and inspect the
   just-baked layer before moving on.
3. With `DEBUG = True`, print seam curve length, sample points that projected
   successfully, resolved `BISECTOR_SURFACE_REACH`, naked-edge count on the
   T-Brep, intersection-curve counts per pair, final ordered curve count.
4. Toggle `ShellBisector::*` layers individually to confirm each stage before
   trusting the next.
5. Once clean on the trivial shell, re-run on the real hull shell, retuning
   `BISECTOR_SAMPLE_COUNT` / `BISECTOR_SURFACE_REACH` / `T_ARM_WIDTH` as needed.
   Keep `STOP_AFTER_STAGE` in the shipped script rather than removing it once
   "done" — more revisions are expected.
