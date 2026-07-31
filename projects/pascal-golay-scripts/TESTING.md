# Testing plan: Pascal Golay Rhino 8/9 Python ports

All 44 legacy RhinoScript (.rvb) files, plus the one pre-existing Python
file, were ported to modern rhinoscriptsyntax/RhinoCommon Python (see
`README.md` for the full port and its per-script confidence/caveat table)
targeting Rhino 8's Script Editor in CPython3 mode. Every port was only
syntax-checked (`ast.parse`/`py_compile`) — **none have been run against
live Rhino**, since no Rhino instance is available in the cloud session
that did the porting.

This is a testing procedure for you to execute in a real Rhino 8 session.

## Approach: 4 tiers, easiest/highest-confidence first

Testing in order of confidence means early passes build trust in the
environment/workflow itself before tackling the riskiest rebuilds, and a
failure in an early tier is more likely to be a setup problem than a real
script bug.

### Tier 0 — Environment sanity check (do this once, first)

1. Confirm Rhino 8.3+ is installed (needed for CPython3 Script Editor).
2. Open the Script Editor (`ScriptEditor` command), confirm it's set to
   Python 3 / CPython mode, not IronPython 2.
3. Pick ONE trivial high-confidence script — `zoomsame/ZoomSame.py` is the
   simplest (no geometry input needed, just active-viewport comparison) —
   and confirm it runs at all via F5. This validates rhinoscriptsyntax
   imports correctly and the Script Editor pipeline works before spending
   time on the other 44.

### Tier 1 — High-confidence, simple scripts (18 scripts, quick pass)

Straightforward 1:1 ports per the README table. Run each once against
simple test geometry (a line, a curve, a couple of selected objects) and
confirm it does what its name says — these are "does it run without
crashing" checks, not deep verification:

`ConvertCurveDegree`, `CreateOutline`, `DimensionOffset`, `DivideLengthX`,
`ExtractUnderlyingSrfs`, `ExtractWiresDir`, `FileInfo`, `FindClearance2`,
`HatchDirection`, `HighPt`, `PlanarSrfPt`, `PopUpPlanes`, `QInfo`,
`ScaleCenters`, `SelParallelToAxis`, `Silhouette_VP`, `UpdateSelectedBlocks`,
`ZoomSame`

Specific things worth a closer look while you're in there (from the README):
- **PopUpPlanes**: confirm CPlane is *not* restored after a cancel (that was
  the bug fix — old behavior always restored it).
- **QInfo**: run it in a loop over a multi-object selection including at
  least one mesh, to confirm the stale-flag bug (leaking into the mesh
  branch) is actually gone.
- **Silhouette_VP**: run it twice in the same session — duplicate named-view
  entries accumulating is *expected* (not fixed), confirm that's still true
  and not a surprise regression.

### Tier 2 — Priority scripts flagged for real risk (7 scripts)

These needed the biggest rebuilds (missing rhinoscriptsyntax functions,
dense math, or an actual behavior change) — test with geometry specifically
chosen to exercise the tricky part:

1. **FilletNonPlanar** — test on a genuinely non-planar curve/edge case (not
   just a planar one). `rs.LineCurveIntersection` doesn't exist upstream; a
   hand-built probe-line replacement is doing the real work here.
2. **IntersectPlane** — test all of it, not just the default entry point:
   plain intersect, `TrimWithPlane`, `SplitWithPlane`, and
   `BooleanSplitWithPlane` separately (only the default path got any
   scrutiny during the port). Two axis-index bugs were already caught and
   fixed once — a third could be lurking in the untested variants.
3. **SetbackFillet** — test with a multi-curve selection where one curve is
   smooth (no corners) and comes *after* a curve with corners in the
   selection order, to specifically probe the documented stale
   arc/parameter state bug.
4. **CurveSymmetryAuto** — the most math-dense port (CV mirroring, knot
   vectors). Test against a curve with an odd knot structure or high degree,
   not just a simple symmetric arc.
5. **RotateOnNormal** — this one has a **deliberate behavior change**, not
   just a port: the original's repeat-loop was dead code, replaced with what
   was judged as the intended repeat behavior. Explicitly confirm the new
   repeat behavior is what you actually want; this is the one most likely to
   need a manual adjustment rather than just a bug report.
6. **Sprinkler** — test the point-projection logic against both a surface
   *and* a mesh target (the RhinoCommon rebuild split into
   `ProjectPointsToBreps`/`ProjectPointsToMeshes`) — confirm both paths, not
   just one.
7. **RadialSections** — test with plane/vector setups away from the world
   axes to make sure the already-once-fixed indexing mistake doesn't have a
   sibling bug hiding in an untested orientation.

### Tier 3 — Remaining medium-confidence scripts (17 scripts)

Same "run it, check the specific caveat" pattern as Tier 1, but each of
these has a named behavior detail worth confirming against the README:

- **AlignGrips** — confirm the new interactive curve/line picker (replacing
  the dropped `Rhino.AddAlias` step) is an acceptable substitute workflow.
- **AlignPlus** — confirm move-by-vector math matches the old two-point
  move visually.
- **BallJoint** — the final `Orient ... Onsrf` macro string is the
  least-verified part; watch for a malformed command-line error specifically
  at that step.
- **ClippingPlaneCurves** — confirm the RhinoCommon-rebuilt clipping plane
  behaves like the original COM-based one.
- **Distribute** — confirm the two preserved dead-code quirks really are
  inert (shouldn't visibly matter, but worth eyeballing test output).
- **FaceCamera** — confirm the fixed vector-reversal assignment and the
  8-iteration cap don't cut off a legitimate longer rotation.
- **FindStackedPoints** — the dedup logic changed from exact-string-match to
  tolerance-based; test with points that are *very* close but not identical
  to confirm the new tolerance behavior is what's wanted.
- **MatchCrvTanSrf** — specifically test the tension-drag visual interaction
  (the part with no exact modern `GetPoint` equivalent).
- **MatchOnCrv** / **Mirror_ex** — quick confirmation pass, API signature
  fixes were mechanical and lower-risk.
- **Orient2ptCrv** — confirm the "Copy?" prompt still does nothing (that's
  the preserved original bug, not a new one).
- **PlanarizeCurve** — test specifically on a *closed* curve to hit the
  "Vertical" branch's odd point-discarding behavior, and decide if that's
  actually wanted.
- **Project_Direction** — confirm the new single-file dispatcher menu
  correctly reaches all 3 of the original's separate command aliases.
- **ProjectObjects** — test the cage-edit/grip flow specifically, since that
  path had no live verification at all.
- **ReTrim** — test against a multi-piece split scenario, since the
  split-picking heuristic was ported verbatim without redesign.
- **SetVolume** — confirm the "last value" sticky-persistence default
  actually persists correctly across repeated runs in the same session.
- **SurfaceTangent** — test on a surface with a non-trivial U/V point count
  to confirm the reverse-engineered grip-index formula holds.
- **WorldCPlaneToView** — test from a few different view angles to confirm
  the "largest angle" logic picks the geometrically correct one, not the
  inverse.
- **numberer_py3** — specifically test cancelling the Suffix prompt
  mid-sequence to confirm the state-wipe bug is actually fixed.

## Reporting results back

Track results directly in `README.md`'s existing confidence table — add a
"Tested" column (Pass / Fail / Needs fix) next to Confidence as each script
gets run, so that table stays the single source of truth instead of a
separate log going stale. Commit that update once a batch of testing is
done; no need to test all 45 in one sitting.

## Verification

This is manual testing in a real Rhino 8 session — there is no automated
check possible from a cloud session with no Rhino install. "Done" means
each script has been run at least once against real geometry and either
confirmed to match this doc's/the README's documented expectation
(including preserved-bug cases) or flagged as a real regression to fix in
a follow-up commit.
