# BRIX MODELING — changelog

Streamlining pass, 2026-07-31. Base state on `main` at commit `c2b7d8e`
(pre-streamline tag creation was blocked by the git proxy). No behavior
changes intended anywhere in this pass except where explicitly flagged
below (error-path/latent-bug fixes only, never the normal success path).

## OBJECT NAMER WIP.py -> OBJECT NAMER WIP2.py
- Extracted 3 helpers (`_iter_named_objects`, `_last_number_in`/
  `_last_letter_in`, `_fill_gaps_then_continue`) collapsing duplicated scan
  and gap-fill logic.
- Collapsed 3 separate passes over `obj_refs` in `UpdateUiForMode` into one
  — verified the one behavioral difference in the merge (a stricter
  `.strip()` filter) is a no-op given how `get_designator()` already
  normalizes blank names.
- Removed a dead conditional (`padding_len = len(core_start) if ... else
  len(core_start)` — both branches were identical).
- Docstrings added throughout.

## OFFSET SRF with NAME v1.py / Offset_Srf_with_Name_v2.py -> Offset_Srf_with_Name_v3.py
- **v1 vs v2 note:** v2 is a strict superset of v1 (adds `MergeCoplanarFaces`,
  `angle_tolerance`, a native undo record, a `Guid.Empty` check, and a
  Python-3-safe `GetBoolean` args fix) — nothing in v1 is missing from v2,
  so v3 builds on v2 per the owner's call. v1 and v2 both remain untouched
  in this folder.
- Extracted 4 helpers from the monolithic function (selection, distance
  prompt, offset+add, reversed-offset retry).
- Hoisted a redundant `rs.ObjectName()` re-read out of the per-result-piece
  loop (same value every iteration).
- **Flagged fixes, error paths only:** wrapped `brep.Dispose()` in
  `try/finally` (v2 leaked the handle if the offset/merge call threw) and
  guarded `b.Dispose()` against `b` being `None` (v2 called it
  unconditionally, which would `AttributeError` on a `None` result piece —
  a latent bug, likely never hit in practice). Normal success-path
  behavior and output are unchanged.

## POLYSURFACE DUPE EDGE V1.py -> POLYSURFACE DUPE EDGE V2.py
- Replaced magic bitmask `8+16` with `rs.filter.surface | rs.filter.polysurface`
  (confirmed equivalent live against developer.rhino3d.com's RhinoScriptSyntax
  reference).
- **Flagged fix, error path only:** added a null-check on `rs.JoinCurves`'s
  return value before `len()`/`SelectObjects` — that call can return `None`
  on failure per the live docs, and v1 would raise `TypeError` in that case.
  Normal success-path behavior unchanged.
