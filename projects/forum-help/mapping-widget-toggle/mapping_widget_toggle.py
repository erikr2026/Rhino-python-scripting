"""
Mapping Widget toggle - multi-object version.

Forum thread (base script + requirements):
https://discourse.mcneel.com/t/code-request-mapping-widget-toggle/220443

Base script credit: Dale Fugier (McNeel staff), posted 2026-06-30 in the
thread above. This file extends his original single-object script with the
two follow-up enhancements the OP (Stanity Now) requested and that went
unanswered in the thread:

  (a) act on ALL currently selected objects, not just the first one
  (b) drop the scriptcontext.sticky global-dict hack for tracking widget
      on/off state

Engine: Python 3 via Rhino 8's ScriptEditor command (F5 to run). The source
is plain ASCII with no Python-3-only syntax, so it should also run
unmodified under the legacy RunPythonScript (IronPython 2) command if you
need that instead - but it has only been checked for syntax, not run live
in either engine (see "UNVERIFIED" note below).

--- UNVERIFIED / FLAGGED ---
Dale's own post in the thread says, verbatim: "There isn't a clean,
non-interactive way to ask whether the widget is currently shown" - that's
a McNeel staff statement, not a guess, and I could not find any
contradicting RhinoCommon API during this session (doc-site fetches for
Rhino.Render.TextureMapping and a MappingWidget search both failed to
return real page content - genuinely inaccessible this session, not
skipped). So true UI-level "is the widget gumball currently drawn"
detection is NOT implemented here, because no such API is confirmed to
exist.

Instead of Dale's global scriptcontext.sticky dict, this version persists
the on/off flag as a per-object user string
(obj.Attributes.GetUserString / SetUserString), keyed per object ID. This
still eliminates the specific hack (a single sticky dict, keyed on Id,
that resets whenever the sticky store is cleared and lives only in
session memory) in favor of state stored on the object itself in the
document, which survives Save/Open and Undo more predictably. It is a
best-effort compromise, not literal widget-state introspection - flag
this to the OP if precision here matters to their workflow, and suggest
they confirm with McNeel/Dale whether a newer Rhino 8 SDK build has since
added a real widget-state query, since this API surface may have changed
after Dale's July 2026 post.

Also unverified without live testing: doc.Objects.Unselect(Guid) and
doc.Objects.ModifyAttributes(RhinoObject, ObjectAttributes, bool) are used
below with signatures recalled from general RhinoCommon convention, not
confirmed against a live API fetch this session (doc-site fetches failed
to return real content, as noted above) - if either throws an
AttributeError/argument-count error, check the RhinoCommon
Rhino.DocObjects.Tables.ObjectTable page directly before debugging
further.

Also unverified without live testing: doc.Objects.GetSelectedObjects(False,
False) returning grouped objects as their group members (rather than a
single group proxy) when a user selects a "grouped set of objects" per
the OP's second follow-up point. Dale's original used this same call, so
group-expansion behavior is inherited unchanged from his script, not new
in this version - if grouped selections behave unexpectedly, that is a
pre-existing question, not a regression added here.
"""

import Rhino
import scriptcontext as sc
from Rhino.Render import TextureMapping, TextureMappingType
from Rhino.Geometry import Plane, Interval, Vector3d

CHANNEL = 1
USERSTRING_KEY = "mapping_widget_active"


def has_box_mapping(obj):
    for ch in (obj.GetTextureChannels() or []):
        tm = obj.GetTextureMapping(ch)
        if tm and tm.MappingType == TextureMappingType.BoxMapping:
            return ch
    return None


def apply_bbox_box_mapping(obj):
    bb = obj.Geometry.GetBoundingBox(True)
    c = bb.Center
    plane = Plane(c, Vector3d.XAxis, Vector3d.YAxis)
    dx = Interval(bb.Min.X - c.X, bb.Max.X - c.X)
    dy = Interval(bb.Min.Y - c.Y, bb.Max.Y - c.Y)
    dz = Interval(bb.Min.Z - c.Z, bb.Max.Z - c.Z)
    obj.SetTextureMapping(
        CHANNEL, TextureMapping.CreateBoxMapping(plane, dx, dy, dz, True)
    )


def widget_is_active(obj):
    """Best-effort replacement for scriptcontext.sticky state tracking.

    Reads a persistent per-object user string instead of a global sticky
    dict. This is NOT a query of the actual widget UI state (see module
    docstring) - it only tells us what this script last set for this
    object.
    """
    return obj.Attributes.GetUserString(USERSTRING_KEY) == "1"


def set_widget_active(obj, active):
    attrs = obj.Attributes
    if active:
        attrs.SetUserString(USERSTRING_KEY, "1")
    else:
        # Delete rather than set "0" so old files don't accumulate stale
        # user strings on objects that never had the widget toggled on.
        attrs.SetUserString(USERSTRING_KEY, None)
    sc.doc.Objects.ModifyAttributes(obj, attrs, True)


def toggle():
    doc = sc.doc
    sel = list(doc.Objects.GetSelectedObjects(False, False))
    if not sel:
        print("Select one or more objects first.")
        return

    doc.Objects.UnselectAll()

    turned_on = 0
    turned_off = 0

    for obj in sel:
        doc.Objects.Select(obj.Id)

        if widget_is_active(obj):
            Rhino.RhinoApp.RunScript("_MappingWidgetOff", False)
            set_widget_active(obj, False)
            turned_off += 1
        else:
            ch = has_box_mapping(obj)
            if ch is None:
                apply_bbox_box_mapping(obj)
                ch = CHANNEL
            Rhino.RhinoApp.RunScript("_MappingWidget %d" % ch, False)
            set_widget_active(obj, True)
            turned_on += 1

        doc.Objects.Unselect(obj.Id)

    # Restore the full original selection so the user's working set is
    # unchanged after the toggle pass.
    for obj in sel:
        doc.Objects.Select(obj.Id)

    doc.Views.Redraw()
    print("Mapping widget: {} turned on, {} turned off ({} object(s)).".format(
        turned_on, turned_off, len(sel)
    ))


if __name__ == "__main__":
    toggle()
