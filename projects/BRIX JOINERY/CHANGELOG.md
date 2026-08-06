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


## Note: JOINERY_INTERSECTION_SLOT_CUTTER.py moved to BRIX MODELING (2026-08-06)

This script (and its full changelog history — the "New:"/"Fix:" entries
that used to follow this line) was developed here, then moved to
`projects/BRIX MODELING/` at the owner's request once confirmed working.
See that folder's `CHANGELOG.md` for the complete development history —
polysurface support, the opening-sliver and cap-pullback fixes, and the
rathole cutout feature.
