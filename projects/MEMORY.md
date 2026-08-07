# projects/ — index

Quick-reference status for every folder in `projects/`, so anyone (owner,
future session, no Vincent involved) can tell what's here without opening
each one. Keep this in sync when a folder's status changes — one line or
short paragraph per folder, not a full history (each folder's own
`README.md`/`CHANGELOG.md` has that).

The fuller writeup with cross-session context lives in Vincent's own
memory at `memory/projects/rhino-python-scripting.md` (a separate repo,
`erikr2026/Vincent`) — this file is the in-repo counterpart, scoped to
just this repo's own folders.

| Folder | What it is | Status |
|---|---|---|
| `BRIX CNC PARTS` | CNC-facing scripts (bend lines, DXF export, inside/outside cut duplication, unroll-with-name). Versioned filenames (`v1`/`v2`/...), own `CHANGELOG.md`. | Active, in production use. |
| `BRIX DRAFTING` | Drafting/detailing scripts (window/door widgets, leader-by-layer/object-name, isolate-in-detail). Versioned filenames, own `CHANGELOG.md`. | Active, in production use. |
| `BRIX JOINERY` | Joinery scripts (blue-face isolate/orient/set for joint faces). Some files still tagged `WIP`. Own `CHANGELOG.md`. | Active; a few files not yet promoted past WIP naming. |
| `BRIX MODELING` | Modeling scripts (object namer, offset-surface-with-name, polysurface dupe edge, the intersection slot cutter). Versioned filenames, own `CHANGELOG.md`. | Active, in production use. |
| `_template` | Empty starter folder (`README.md` only) — copy this for any new project folder. | Template, not a real project. |
| `brix-plugin-packaging` | Plan (not started) to turn the 4 `BRIX *` folders into headlessly-buildable Rhino plugins via Script Editor Projects (`.rhproj`/`rhinocode`). | Parked at owner's request — "hold on to it for now." |
| `draft-scripts` | One-off/derivative scripts that don't belong in a permanent project folder yet — each tagged in its own header with its probable eventual home when known. E.g. `MirrorWithText_v1.py`, a hardcoded-options trim of `pascal-golay-scripts/mirror_ex/Mirror_ex.py`, tagged as probably belonging in `BRIX CNC PARTS` (not confirmed). | Active — new folder, 2026-08-07. |
| `offset-parallel-lines` | Moves two selected parallel lines apart by a settable distance (typed or two-click). | WIP — owner testing/tweaking locally; this copy may lag. |
| `pascal-golay-scripts` | 1:1 Python 3 ports of Pascal Golay's (McNeel) public RhinoScript utilities — ~49 scripts, one folder each, paired with the original `.rvb`. Only genuine 1:1 ports live here; owner-requested variants/derivatives (e.g. a trimmed-down version of one of these) go in `draft-scripts` instead, not mixed into this folder. Per-script confidence/caveat table in this folder's own `README.md`; 4-tier test plan in `TESTING.md`. | Mostly untested against real Rhino — `aligngrips/AlignGrips.py` and `mirror_ex/Mirror_ex.py` are the two confirmed-working so far (2026-08-07, after fixing a shared `EvaluateSurface` bug in both). |
| `shell-bisector-t-surface` | Builds a bisector surface + T-fin between two picked faces at a hull junction, multi-junction in one run. | Confirmed working end-to-end on the real hull. |
