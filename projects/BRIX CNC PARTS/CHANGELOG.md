# BRIX CNC PARTS — changelog

Streamlining pass, 2026-07-31. Base state tagged locally as
`pre-streamline-2026-07-31` (tag push blocked by the git proxy — see repo
history at commit `c2b7d8e` on `main` for the pre-streamline state). No
behavior changes intended anywhere in this pass — every rewrite is a new,
higher-versioned file; originals are untouched. Each script's own docstring
also documents what changed.

## BEND LINES.py -> BEND LINES v2.py
- Added module docstring.
- Extracted magic numbers into named constants (`SHORT_LINE_LENGTH`,
  `SHORT_EDGE_THRESHOLD`, `COORD_ROUND_DIGITS`).
- Extracted duplicate-edge coordinate-key logic and bend-line-drawing logic
  into helper functions (`_edge_key`, `_add_bend_lines_for_edge`).
- Uncertain/left alone: whether the script targets `RunPythonScript`
  (IronPython) or ScriptEditor (Py3) — noted in the docstring, doesn't
  affect behavior either way.

## EXPORT DXF v1.py -> EXPORT DXF v2.py
- Split into `get_export_selection()`, `prepare_output_path()`,
  `run_dxf_export()`, with `export_selected_dxf()` as orchestrator.
- Pulled repeated magic strings ("CAM Imperial", ".dxf", prompt text) into
  constants.
- Added docstrings explaining the *why* behind redraw suppression,
  pre-existing-file removal, and backslash normalization.
- Uncertain/left alone: a trailing `#! python 3` engine marker glued onto
  the last line in v1 looks misplaced (normally belongs on line 1) — kept
  in the same relative position rather than moving it, since moving it
  could change how ScriptEditor interprets the file.

## DUPINSIDEOUTSIDECUTS v1.py -> DUPINSIDEOUTSIDECUTS v2.py
- Replaced a magic-number object filter bitmask with the equivalent named
  `rs.filter.surface | rs.filter.polysurface | rs.filter.extrusion` (same
  values, confirmed against rhinoscriptsyntax's `filter` class).
- Extracted per-brep curve-duplication/layer-sort logic into
  `duplicate_and_sort_edges()`.
- Dropped an unused loop variable (`for cfg in layers.values()` instead of
  `.items()`).
- Uncertain/left alone: no null/failure handling added for `rs.AddLayer` or
  `sc.doc.Objects.AddCurve` — matches v1's existing unguarded error paths.

## UNROLL MULTIPLE with NAME v5.py -> UNROLL MULTIPLE with NAME v6.py
- Extracted `_bake_id()` (collapses a guard pattern repeated ~10x) and
  `_bbox_average()` (bounding-box centroid math repeated 3x).
- Split the ~200-line `arrange_unrolled_surfaces()` into 8 named helpers
  (geometry lookup, baking, bend lines, centroid resolution, labeling,
  orientation, per-surface unroll) — same logic per step, just named.
- Standardized on the `rg.` alias for `Rhino.Geometry` throughout (v5 mixed
  `Rhino.Geometry.X` and `rg.X` for the same classes).
- Named constants for previously-inline magic values (layer/style names,
  bend-line lengths, grid spacing, label offset).
- Uncertain/left alone: execution engine (RunPythonScript vs. ScriptEditor)
  unconfirmed — live docs 404'd this session; `_get_following_geometry`
  only reading the object's first group matches v5 exactly and wasn't
  treated as a bug; `DimStyles.FindName`/`.Find` fallback pair left as-is,
  out of scope for this cleanup.
