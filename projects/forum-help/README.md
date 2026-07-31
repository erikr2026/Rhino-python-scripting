# forum-help

Scripts written in response to real, unresolved (or incompletely-resolved)
threads on McNeel's official community forum (discourse.mcneel.com),
surfaced by a research pass on 2026-07-31 looking for genuine workflow pain
points from roughly the last month. **None of these have been posted to the
forum** — Vincent has no forum-posting capability yet (a deliberately
not-yet-enabled future capability); these are handed to the owner to post
themselves, or not, at their discretion.

Every script here was written without access to a live Rhino instance —
each README documents what's confirmed against live docs/the source thread
vs. what's carried over from training knowledge and flagged as unverified.
Test before relying on any of these in production.

## Contents

| Folder | Forum thread | What it does |
|---|---|---|
| `subobject-face-pick/` | [220842](https://discourse.mcneel.com/t/subobjectselectionenabled-works-for-polylines-not-solid-faces/220842) | Workaround for `SubObjectSelectionEnabled` returning the whole solid instead of the picked face on an Extrusion/Brep — bypasses the picker bug via closest-point-to-face lookup. Most speculative of the five (couldn't reach live API docs this session); flagged clearly in its README. |
| `mapping-widget-toggle/` | [220443](https://discourse.mcneel.com/t/code-request-mapping-widget-toggle/220443) | Extends Dale Fugier's (McNeel) mapping-widget toggle script for multi-selection. The "no sticky-state hack" ask is only partially met — Dale himself said there's no clean way to query widget UI state, so this swaps the sticky dict for a per-object tag rather than true state detection. |
| `print-command-wrapper/` | [219958](https://discourse.mcneel.com/t/fulfill-arguments-for-rhino-command-print/219958) | Python wrapper around `-Print`'s command-line args. McNeel doesn't publish `-Print`'s full grammar anywhere — only `destination`/`printer`/`run_setup` are confirmed; `layout_name`/`scale`/`filename` are best-guess and clearly flagged. Read the caveats before running (an unconfirmed filename arg could hang on an interactive dialog). |
| `shortcut-conflict-finder/` | [220451](https://discourse.mcneel.com/t/list-currently-defined-keyboard-shortcuts/220451) | Extends the OP's own shortcut-lister script to actually flag duplicate key-combo assignments — the problem that motivated them to write the original script in the first place. |
| `cpython-toolbar-button/` | [220056](https://discourse.mcneel.com/t/better-object-properties-export/220056) / [220021](https://discourse.mcneel.com/t/running-a-cpython-script-from-a-rhino-button-icon-instead-of-ironpython/220021) | Documents the confirmed fix (`-_ScriptEditor _Run` instead of `RunPythonScript`) for running CPython/openpyxl scripts from a toolbar button, plus an example object-properties-to-Excel export script. |

## Skipped this pass

Thread [220727](https://discourse.mcneel.com/t/add-remove-alias-silently-resets-display-mode-list-at-next-check/220727)
(alias/display-mode persistence bug, escalated to McNeel ticket RH-97159) and
the Grasshopper category were intentionally not covered in this pass — owner
asked to revisit those later.
