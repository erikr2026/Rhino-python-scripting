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
