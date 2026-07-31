# rdk:command_name: BEND_LINES
# rdk:command_alias: BEND_LINES
"""
BEND LINES v2 - streamlined/cleanup pass over BEND LINES.py (v1).

Behavior is unchanged from v1: for every selected INTERNAL (non-naked) brep
edge, draw short reference "bend lines" at its ends (or one full-length line
if the edge is short). Naked edges are ignored. Duplicate edges shared by
multiple selected faces/objects are only processed once, matched by rounded
endpoint coordinates (not by GUID), so this also de-dupes edges picked
across separate objects.

Engine: uses only Rhino/RhinoCommon + scriptcontext (no rhinoscriptsyntax),
so it should run unchanged under either Rhino 8 script engine (Python 3 via
ScriptEditor, or legacy IronPython via RunPythonScript). This was not
runtime-verified against either engine this pass - confirm which one the
owner actually invokes if that ever matters.
"""
import Rhino
import Rhino.Geometry as rg
import Rhino.Input.Custom as ric
import scriptcontext as sc

# Tunables (unchanged values from v1, just named for clarity)
SHORT_LINE_LENGTH = 2.0      # length (units) of each end-line on a long edge
SHORT_EDGE_THRESHOLD = 4.0   # edges at or under this length get one full-length line instead
COORD_ROUND_DIGITS = 3       # rounding precision used to de-dupe edges by endpoint coordinates


def _edge_key(edge):
    """
    Build a direction-independent identity key for an edge based on its
    rounded endpoint coordinates, so the same physical edge picked from
    two different objects/faces is recognized as a duplicate.
    """
    p1 = edge.PointAtStart
    p2 = edge.PointAtEnd
    pts = sorted([
        (round(p1.X, COORD_ROUND_DIGITS), round(p1.Y, COORD_ROUND_DIGITS), round(p1.Z, COORD_ROUND_DIGITS)),
        (round(p2.X, COORD_ROUND_DIGITS), round(p2.Y, COORD_ROUND_DIGITS), round(p2.Z, COORD_ROUND_DIGITS)),
    ])
    return tuple(pts)


def _add_bend_lines_for_edge(crv):
    """
    Add the reference line(s) for one already-validated edge curve.
    crv.Domain is expected to already be reparameterized to (0, length).
    """
    total_len = crv.GetLength()
    if total_len <= SHORT_EDGE_THRESHOLD:
        sc.doc.Objects.AddLine(rg.Line(crv.PointAt(0.0), crv.PointAt(total_len)))
    else:
        sc.doc.Objects.AddLine(rg.Line(crv.PointAt(0.0), crv.PointAt(SHORT_LINE_LENGTH)))
        sc.doc.Objects.AddLine(rg.Line(crv.PointAt(total_len), crv.PointAt(total_len - SHORT_LINE_LENGTH)))


def create_lines_on_internal_edges():
    """
    Prompt the user to pick edges (sub-object selection enabled so
    individual faces of a polysurface can be clicked), then draw bend-line
    markers on every unique internal edge selected. Naked edges are skipped.
    """
    # Clear selection to ensure we don't accidentally modify the surface
    sc.doc.Objects.UnselectAll()

    go = ric.GetObject()
    go.SetCommandPrompt("Select edges. Only INTERNAL edges will get lines. Naked edges will be ignored.")
    go.GeometryFilter = Rhino.DocObjects.ObjectType.EdgeFilter
    go.SubObjectSelect = True
    go.DeselectAllBeforePostSelect = False
    go.AcceptNothing(True)

    result = go.GetMultiple(1, 0)
    if result != Rhino.Input.GetResult.Object:
        print("No edges selected.")
        return

    processed_count = 0
    # Track edges by their physical location in space (rounded endpoint
    # coords). This works across multiple objects and does not require Solids.
    seen_edge_coords = set()

    for objref in go.Objects():
        edge = objref.Edge()
        if not edge:
            continue

        # Skip naked edges - only interior (internal) edges get lines.
        if edge.Valence != rg.EdgeAdjacency.Interior:
            continue

        edge_key = _edge_key(edge)
        if edge_key in seen_edge_coords:
            continue

        crv = edge.EdgeCurve.DuplicateCurve()
        if not crv:
            continue

        crv.Domain = rg.Interval(0, crv.GetLength())
        _add_bend_lines_for_edge(crv)

        seen_edge_coords.add(edge_key)
        processed_count += 1

    sc.doc.Views.Redraw()
    print("Finished - Processed {0} unique internal edges. Naked edges were skipped.".format(processed_count))


if __name__ == "__main__":
    create_lines_on_internal_edges()
