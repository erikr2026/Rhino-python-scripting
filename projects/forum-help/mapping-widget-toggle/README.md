# Mapping Widget toggle - multi-object extension

Forum thread: https://discourse.mcneel.com/t/code-request-mapping-widget-toggle/220443
(posted 2026-06-30)

## Base script

Dale Fugier (McNeel staff) posted the original working script in the
thread. It:

- reads the current selection, acting only on `sel[0]` (the first
  selected object)
- checks the object's texture channels for existing box mapping
  (`TextureMappingType.BoxMapping`); if none, builds one from the
  object's bounding box and applies it via
  `TextureMapping.CreateBoxMapping`
- runs `_MappingWidget <channel>` / `_MappingWidgetOff` via
  `Rhino.RhinoApp.RunScript` to show/hide the widget
- tracks on/off state per object in a global `scriptcontext.sticky`
  dict, keyed on `"mapwidget_" + str(obj.Id)`, because (Dale's own
  words) "there isn't a clean, non-interactive way to ask whether the
  widget is currently shown"

That script is reproduced in full in the "Post 2 - Dale Fugier" section
this project's fetch captured, and is the base `mapping_widget_toggle.py`
extends.

## What's in `mapping_widget_toggle.py`

Two unanswered follow-up requests from the OP (Stanity Now), both
implemented:

1. **Multi-object support.** The script now loops over every object in
   `doc.Objects.GetSelectedObjects(False, False)` instead of indexing
   `sel[0]`. Each object is individually selected, toggled, then
   restored to the original full selection at the end so the user's
   working set is unchanged.

2. **Drop `scriptcontext.sticky`.** Per-object on/off state is now stored
   as a persistent user string on the object's attributes
   (`obj.Attributes.GetUserString` / `SetUserString` +
   `doc.Objects.ModifyAttributes`) rather than in a global sticky dict.
   This is a genuine improvement in the "no more fragile global
   state" sense the OP asked for, but it is **not** true widget-UI-state
   detection - it's still a flag the script itself sets and reads, just
   stored on the object (survives Save/Open, Undo) instead of in
   session memory. Dale explicitly said in the thread there's no clean
   non-interactive query for "is the widget currently shown," and that
   held up this session too: two live-doc fetches (RhinoCommon
   `TextureMapping` class page and a site search for `MappingWidget`)
   both failed to return real page content, so no contradicting API was
   found - and none was assumed into existence either.

## Unverified without live Rhino testing

Flagging explicitly per the no-hallucinated-confidence rule:

- `doc.Objects.Unselect(Guid)` and
  `doc.Objects.ModifyAttributes(RhinoObject, ObjectAttributes, bool)` are
  used with signatures recalled from general RhinoCommon convention, not
  confirmed via a live docs fetch this session.
- Whether `GetSelectedObjects` expands a selected *group* into its member
  objects (relevant to the OP's "grouped set of objects" case) is
  inherited unchanged from Dale's original call - not newly verified or
  newly broken here.
- The per-object-user-string approach to (b) has not been run against
  a real Mapping Widget session to confirm it doesn't fight with
  whatever Rhino's own widget conduit does internally when a channel
  already has a widget open on a different object.

## How to run / test

1. Rhino 8, `ScriptEditor` command, open this `.py` file, F5.
2. Select one object with no mapping: confirm box mapping gets applied
   and the widget appears; running again should hide it (verify the
   user-string toggle round-trips - print statements report on/off
   counts to the command line).
3. Select 3-4 mixed objects (some with existing box mapping, some
   without) and repeat: confirm each is handled independently and the
   original full selection is restored after the pass.
4. If it needs to run via the legacy `RunPythonScript` command instead,
   it should work as-is (pure ASCII, no Python-3-only syntax) but has
   only been checked for syntax, not run live in either engine.
