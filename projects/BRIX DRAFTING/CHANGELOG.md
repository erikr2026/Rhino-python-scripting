# BRIX DRAFTING — changelog

Streamlining pass, 2026-07-31. Base state on `main` at commit `c2b7d8e`
(pre-streamline tag creation was blocked by the git proxy). No behavior
changes intended anywhere in this pass — every rewrite is a new,
higher-versioned file; originals are untouched. Each script's own docstring
also documents what changed. Two entries below note a deliberate,
explicitly-flagged behavior change on an *error path only* (not the normal
success path) — called out so you can decide whether to keep it on review.

## Select_All_Details_v1.py -> Select_All_Details_v2.py
- Dropped an unused `import Rhino`.
- Added docstrings, including engine ambiguity note.
- Added `or []` fallback on view-getter calls (defensive, currently a no-op
  since Rhino returns empty arrays not None).
- `select_all_details()` now returns a count — doesn't affect Rhino-side
  behavior.

## Leader_LayerName_v1.py -> Leader_LayerName_v2.py
- Docstrings added; cached a repeated `objref.Object()` call.
- **Flagged behavior change (error path only):** added a null check on
  `rhobj` before use. v1 would raise `AttributeError` on that edge case;
  v2 exits silently, matching the script's own convention elsewhere. Normal
  success path unaffected.
- Left the `if not layer:` truthiness check verbatim — uncertain whether it
  should test `Layer.Index == -1` instead, not verified live.

## Leader_ObjectName_v1.py -> Leader_ObjectName_v2.py
- Deduped filter/formatter logic into `_has_object_name()`.
- **Flagged behavior change (error path only):** same null-check pattern as
  Leader_LayerName above — `AttributeError` on empty objref becomes an
  early return instead.
- Renamed functions to snake_case; corrected a stale docstring that
  described an unrelated "convex hull" (leftover boilerplate) and fixed a
  typo ("Novemeber").

## Select_AnnontationStyle_All_Layouts_v1.py -> ...v2.py
(Filename spelling of "Annontation" kept as-is to match the original.)
- Extracted 3 helpers from inline blocks.
- Wrapped the main loop in `try/finally` so `EnableRedraw(True)` always
  restores, even on an unexpected error mid-loop (v1 could leave redraw
  disabled if an exception hit mid-loop — arguably a bug fix, flagged here
  since it's a behavior difference on the error path).
- Added a top-level `try/except` for a clean one-line error instead of a
  raw traceback.
- Left `DimStyleTable.FindName`/`ObjectType.Annotation`/etc. signatures
  untouched — couldn't verify live docs this session.

## ISOLATEINDETAIL_v1.py -> ISOLATEINDETAIL_v2.py
- Extracted `_is_inside_detail()` helper.
- Wrapped the `-_HideInDetail` command call in `try/except`, printing a
  plain message on failure instead of a raw traceback — safety net only;
  unclear whether `rs.Command` actually raises here or just returns False.

## AJR_WINDOW__DOOR_WIDGET_V5.py -> AJR_WINDOW__DOOR_WIDGET_V6.py
- Dropped two unused imports (`Rhino.Geometry`/`rg`, `scriptcontext`/`sc`).
- Added `_set_visible()` helper collapsing repeated label/control visibility
  toggle pairs; simplified a redundant if/else to one call.
- Extracted clamp-thickness validation into `_is_valid_measurement()`.
- Added docstrings; fixed a comment-numbering slip.
- Left the apparent double-invocation of `UpdateFormState()`/
  `OnMountingChanged()` exactly as-is — looks redundant but touching it
  risks changing UI update timing.

## WS_DETAIL_MANIFEST_ETO_WIP7.py -> WS_DETAIL_MANIFEST_ETO_WIP8.py
(695 lines, largest script in this folder — README reviewed for context
before editing.)
- Extracted `_make_button()`, `_get_all_scene_objects()`,
  `_select_object_ids()`/`_run_command_on_ids()`, and
  `_resolve_reference_path()` helpers, each collapsing 2-8 duplicated
  inline blocks into one call site.
- Dropped unused exception-variable bindings in ~8 no-op handlers
  (`except Exception as e: pass` → `except Exception: pass` where `e` was
  never used).
- Replaced the `'undo_record' in locals()` idiom with an explicit
  `undo_record = None` initialization — same effective behavior.
- Left the unused `page_view` return value from `get_active_detail()` in 5
  click handlers exactly as WIP7 has it — flagged as dead-ish but low value
  to touch.
