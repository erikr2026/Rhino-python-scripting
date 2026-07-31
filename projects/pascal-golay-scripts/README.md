# Pascal Golay's Scripted Utilities (mirrored 2026-07-31)

Local mirror of the free scripts and plugins published by Pascal Golay
(McNeel developer, `pascal@mcneel.com`) on McNeel's wiki:

https://wiki.mcneel.com/people/pascalgolay

Each subfolder here is one script or plugin, unzipped exactly as published —
nothing has been edited, renamed, or "streamlined." This is a raw mirror for
reference/prior-art, not a Vincent-authored project.

## Important: most of these are NOT Python

Despite this repo being called `rhino-python-scripting`, the bulk of Pascal's
utilities predate rhinoscriptsyntax/Python-era Rhino — they're legacy
**RhinoScript** (`.rvb`, VBScript-based, the pre-Python 5/6-era scripting
engine) files:

- **44 `.rvb`** scripts — legacy RhinoScript, run via Rhino's old `RunScript`
  command, not `-_ScriptEditor _Run`. Will need porting to
  rhinoscriptsyntax/RhinoCommon Python to use in a modern Python workflow.
- **5 `.rhp`** — compiled Rhino plugins (binary, install via drag-and-drop
  or the Plug-ins panel): `Light_Utilities.rhp`, `EllipseViewAngle.rhp`,
  `ExtractTangentFaces.rhp`, `SelectionSets.rhp`, `Numberer.rhp`.
- **1 `.py`** — `numberer/numberer.py`, the only actual Python file in the
  set (companion script alongside the compiled `Numberer.rhp` plugin).
- **6 `.txt`** — readme/notes files bundled inside some zips.
- **1 `.tb`** — `selectionsets/SelectionSet.tb`, a Rhino toolbar file bundled
  with the SelectionSets plugin.

## What's missing (dead links, not mirrored)

4 of the 53 links on Pascal's page point to `github.com/downloads/...` —
GitHub's old file-hosting service, retired years ago. All 4 returned
HTTP 403 and were **not** downloaded:

- `Isolate_2.zip`
- `HowMany.zip`
- `UnderlyingSrf.zip`
- `MoveProject (2).zip`

If these are needed, the only path is finding another mirror or archive.org
snapshot — they are not recoverable from McNeel's wiki page itself.

## Folder list (49 mirrored)

aligngrips, alignplus, balljoint, clippingplanecurves, convertcurvedegree,
createoutline, curvesymmetryauto, dimensionoffset, distribute,
dividelengthx, ellipseviewangle, extracttangentfaces, extractunderlyingsrfs,
extractwiresdir, facecamera, fileinfo, filletnonplanar, findclearance,
findstackedpoints, hatchdirection, highpt, intersectplane, light_utilities,
matchcrvtansrf, matchoncrv, mirror_ex, numberer, offsetx, orient2ptcrv,
planarizecurve, planarsrfpt, popupplanes, project_direction, projectobjects,
qinfo, radialsections, retrim, rotateonnormal, scalecenters,
selectionsets, selparalleltoaxis, setbackfillet, setvolume, silhouette_vp,
sprinkler, surfacetangent, updateselectedblocks, worldcplanetoview, zoomsame

Source: https://wiki.mcneel.com/people/pascalgolay (fetched 2026-07-31).

## Rhino 8/9 Python ports (2026-07-31)

All 44 `.rvb` scripts, plus a Rhino 8/9-compat pass on the one pre-existing
`.py` file, have been individually reviewed and ported to modern
rhinoscriptsyntax/RhinoCommon Python targeting Rhino 8's Script Editor
(CPython3 mode). Reasoning: classic RhinoScript/VBScript is Windows-only,
was dropped from Rhino 8's new Script Editor (only restored in 8.3 as a
stripped-down legacy fallback with no autocomplete or formatting), and
McNeel staff have publicly said its long-term future is uncertain
(RH-78855 discussion) — porting to Python is the actual fix for lasting
Rhino 8/9 compatibility, not a patch to the VBScript itself.

**Every original file is untouched.** Each port is a new `.py` file added
alongside its `.rvb` sibling (e.g. `aligngrips/AlignGrips.py` next to
`aligngrips/AlignGrips.rvb`).

**Ground rules used for every port:**
- Function/signature mappings verified against the live `mcneel/rhinoscriptsyntax`
  GitHub source (rhino-8.x branch) or developer.rhino3d.com, not trained memory —
  several functions the originals relied on turned out not to exist in modern
  rhinoscriptsyntax at all (flagged per-file below).
- Real bugs found in the originals are called out in each file's docstring,
  not silently fixed or silently reproduced — with one exception noted
  per-file where reproducing broken behavior seemed safer than guessing at
  "correct" without a live Rhino test.
- **No live Rhino was available in this session.** Every port is syntax-valid
  (`ast.parse`/`py_compile`) but NOT runtime-tested. Treat "confidence" below
  as "how straightforward the port was," not "confirmed working" — run each
  one in Rhino 8's Script Editor (F5) before relying on it, especially the
  medium/low-confidence ones.

| Script | Confidence | Caveat |
|---|---|---|
| AlignGrips | Medium | `Rhino.AddAlias` has no CPython3 equivalent, dropped; replaced with an interactive picker. |
| AlignPlus | Medium | Legacy 3-arg `MoveObject` rewritten for the modern 2-arg (translation-vector) signature; `CullDuplicateStrings` replaced with plain dedupe (no rs equivalent). |
| BallJoint | Low-medium | Final `Orient ... Onsrf` macro string carried over as literally as possible; exact token/spacing unverified without live Rhino. |
| ClippingPlaneCurves | Medium | `Rhino.ClippingPlaneDefinition` has no rs wrapper; rebuilt via RhinoCommon `ClippingPlaneObject`. |
| ConvertCurveDegree | High | 1:1 rs mapping. `Rhino.ObjectURL` has no equivalent, dropped with a TODO. Flagged (not fixed) an apparent argument-order bug in the original's grip-copy line. |
| CreateOutline | High | Straightforward; `_CurveBoolean` pick-point macro not live-tested. |
| CurveSymmetryAuto | Medium | Most complex file (CV-mirroring math, knot-vector construction) — worth sanity-checking first in Rhino. Three debug-only helper subs omitted as dead code. |
| DimensionOffset | High | Assumes grip indices 0-3 map the same as in the original; not independently re-verified live. |
| Distribute | Medium | Large state-machine port; two original dead-code quirks preserved (documented, no behavioral effect) rather than "cleaned up." |
| DivideLengthX | High | Reinterpreted an ambiguous original command chain as explicit macro syntax — functionally equivalent, not live-tested. |
| ExtractUnderlyingSrfs | High | Dropped `AddTorus`'s undocumented direction arg (modern API errors if both a plane base and direction are passed). |
| ExtractWiresDir | High | Filters deleted-curve IDs out of the final selection, which the original didn't. |
| FaceCamera | Medium | `ExtractRenderMesh` + best-fit-plane reimplemented in RhinoCommon (no rs equivalent); fixed an apparent missing vector-reversal assignment; added an iteration cap to an unbounded loop. |
| FileInfo | High | Replaced Windows-only COM (`Scripting.FileSystemObject`) with `os.path` — required under CPython3, not optional. |
| FilletNonPlanar | Medium | `rs.LineCurveIntersection` doesn't exist in modern rhinoscriptsyntax at all — replaced with a hand-built probe-line helper. Most structurally complex port; worth a real Rhino test pass first. |
| FindClearance2 | High | Straightforward; original's 512-iteration convergence loop preserved as-is. |
| FindStackedPoints | Medium | Preserves an original bug (grip-restore flag set once before the loop, not per-object) — documented, not silently fixed. Dedup changed from exact-string-match to tolerance-based (documented behavior change). |
| HatchDirection | High | `Rhino.Pt2Str` has no equivalent, replaced with a local formatter. Original's misleading "no hatches changed" count preserved and flagged. |
| HighPt | High | VBScript array-style plane assignment ported to RhinoCommon property setters. |
| IntersectPlane | Medium | Most complex port — rebuilt via raw RhinoCommon since `Rhino.ClippingPlaneDefinition` doesn't exist in rs. Two wrong axis-index mappings caught and fixed during the port itself. `TrimWithPlane`/`SplitWithPlane`/`BooleanSplitWithPlane` variants are untested code paths. |
| MatchCrvTanSrf | Medium | `GetPoint`'s old 2-point overload has no exact modern equivalent — test the tension-drag visual on a real curve. |
| MatchOnCrv | Medium-high | Fixed `MatchObjectAttributes` to take a list (API changed); `_-Match` macro behavior itself untested live. |
| Mirror_ex | Medium-high | Fixed `CopyObject` (now takes one translation vector, not two points) and plane-array indexing. |
| OffsetX | Medium | **Real bug found and fixed**: SubCurves/Span modes were dead code from a wrong API call (`LastCommandResult()` instead of `LastCreatedObjects()`). Flag if the original (broken) behavior was actually wanted. |
| Orient2ptCrv | Medium | Reproduces a real original bug unchanged: the "Copy?" prompt is read but never used (copy is hard-coded true) — documented, not fixed. |
| PlanarizeCurve | Medium | Reproduces the closed-curve "Vertical" branch's odd point-discarding behavior verbatim — worth an eyeball check against the original comment. |
| PlanarSrfPt | High | Original's point-count guard only actually requires 2 points despite a "3 points" comment; wrapped the resulting index access in try/except so it degrades cleanly instead of raw traceback. |
| PopUpPlanes | High | Fixed a real bug: original always restores a CPlane after cancel due to a check against an unused variable. |
| Project_Direction | Medium | Fixed a real bug: original indexed picked points before checking for cancel. Collapsed 3 separate command aliases into one file with a dispatcher menu (a deliberate entry-point simplification, documented). |
| ProjectObjects | Medium | Cage-morph filter constant confirmed live; runtime cage-edit/grip flow not testable without Rhino. |
| QInfo | High | Fixed a real bug: a stale flag was leaking into the mesh-section branch from a prior loop iteration. |
| RadialSections | Medium | Dense vector/plane math — a `Plane`-indexing mistake was caught and fixed during the port itself; still worth visual verification in Rhino. |
| ReTrim | Medium | Ported a convoluted split-picking heuristic verbatim rather than redesigning it; fixed a singular/plural grammar bug in a failure message. |
| RotateOnNormal | Low-medium | The original's repeat-loop logic was dead code (could never actually loop) — replaced with the apparent intended repeat-rotation behavior. This is a real behavior change, not a mechanical port; flagged clearly in the file. |
| ScaleCenters | High | Keeps the original's literal scale-type prompt text ("OneD"/"Two2D"/"3D") verbatim — that's the source's own wording, not a typo introduced here. |
| SelParallelToAxis | High | Straightforward port, no significant caveats. |
| SetbackFillet | Medium | Preserves a real original bug: arc/param state only resets when new corner-discontinuities are found, so a smooth curve later in a multi-curve selection can inherit stale state from the previous curve. Complex enough to want a real Rhino test pass before production use. |
| SetVolume | Medium-high | `rs.MeshVolume()` return shape differs from the legacy COM call (volume is at a different index) — adjusted and verified against source. Sticky-persistence behavior for "last value" defaults inferred, not independently re-confirmed live. |
| Silhouette_VP | High | Kept an original internal naming mismatch (Sub named `SilhouetteEyePt` inside a file named differently) for continuity. Repeated runs still accumulate duplicate named-view entries, same as the original — not fixed. |
| Sprinkler | Medium | `rs.ProjectPointToSurface`/`ProjectPointToMesh` don't exist in rhinoscriptsyntax — rewritten using RhinoCommon's `Intersection.ProjectPointsToBreps`/`ProjectPointsToMeshes`. Fixed two cancel-check typos in the original (wrong variable checked). |
| SurfaceTangent | Medium | Grip-index flattening formula reverse-engineered from the original's arithmetic, matched against confirmed `SurfacePointCount` order — not live-tested. Fixed a missing space in a command macro that would have broken parsing. |
| UpdateSelectedBlocks | High | Straightforward; `Rhino.CullDuplicateStrings` replaced with plain Python dedupe (no rs equivalent). |
| WorldCPlaneToView | Medium | The "pick largest angle" logic looks backwards at first glance but is correct given `ViewCameraPlane`'s Z-axis convention — reasoning documented in the file, not independently verified live. |
| ZoomSame | High | All calls and return shapes confirmed directly against source; straightforward 1:1 port. |
| numberer (the pre-existing `.py`) | High | Original used Python-2-only syntax (`print` statement, `.has_key()`) that would fail outright under Rhino 8's CPython3 Script Editor — fixed as `numberer/numberer_py3.py`, original `numberer.py` left untouched. Also fixed a real bug where cancelling the Suffix prompt wiped the remembered suffix state. |

**Scripts most worth a real Rhino test pass first** (medium-complexity
rebuilds or behavior changes, not simple mappings): `FilletNonPlanar`,
`IntersectPlane`, `SetbackFillet`, `CurveSymmetryAuto`, `RotateOnNormal`,
`Sprinkler`, `RadialSections`.
