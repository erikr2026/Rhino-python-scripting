# Detail Manifest

Standalone Rhino Python script (raw `RhinoCommon` + `rhinoscriptsyntax` +
`Eto.Forms`/`Eto.Drawing`, CPython 3 via Rhino 8's PythonNet bridge). Run via
Rhino 8's **ScriptEditor** command (type `ScriptEditor`, open this file,
press F5) — **not** `RunPythonScript`, which invokes the legacy IronPython 2
engine and will fail on this codebase's syntax/imports.

**Status (2026-07-23): working.**

## What it does

A modeless Eto dialog ("WS Detail Manifest Manager") for managing a
per-detail visibility "manifest" on layout page details:

- **Set / Overwrite Manifest** — prompts the user to select objects to keep
  visible in the active detail, and saves that exact selection as the
  detail's manifest (stored as a GUID list in the detail object's user
  strings).
- **Add / Remove Selected to/from Manifest** — incrementally edit an
  existing manifest.
- **Single Detail / All Details Apply Manifest** — hides every object not in
  a detail's manifest via `HideInDetailOverride`, with a command-line
  (`_HideInDetail`/`_ShowInDetail`) fallback for write-protected worksession
  reference objects.
- **Clear / Reset Manifest** — deletes the stored manifest and restores full
  visibility in that detail.
- **Load References from .WS / .RWS** — parses a Rhino worksession file's
  binary stream for `.3dm`/`.dwg` reference paths, resolves them relative to
  the worksession file or the active document, and attaches them; also
  auto-restores any worksession references recorded in document user text
  that are missing when the dialog opens (e.g. after reopening the file on
  another machine).

## Fixed since WIP6

**Set/Overwrite Manifest offered every object in the model, not just what
was currently visible (2026-07-23).** `on_save_click` called
`_show_all_in_detail(detail_obj)` before prompting for selection, which
strips every `HideInDetailOverride` on the detail — including objects the
user had deliberately hidden in it — making everything pickable. That
defeated the point of "keep visible" selection. Fixed by removing the
force-show step (and the selection-capture/restore workaround it required):
`rs.GetObjects` now only lets the user pick from what's actually visible in
the detail already. `Add Selected to Manifest` intentionally still uses the
force-show behavior — that's for building a manifest from scratch/adding to
it, not for saving what's currently shown.
