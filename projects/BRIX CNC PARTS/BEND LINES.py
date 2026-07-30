# rdk:command_name: BEND_LINES
# rdk:command_alias: BEND_LINES
import Rhino
import Rhino.Geometry as rg
import Rhino.Input.Custom as ric
import scriptcontext as sc

def create_lines_on_internal_edges():
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
    
    line_length = 2.0
    processed_count = 0
    
    # We track edges by their physical location in space.
    # This works across multiple objects and does not require Solids.
    seen_edge_coords = set()
    
    for objref in go.Objects():
        edge = objref.Edge()
        if not edge:
            continue
            
        # 1. STRICT FILTER: Skip Naked edges
        if edge.Valence != rg.EdgeAdjacency.Interior:
            continue
            
        # 2. COORDINATE-BASED DUPLICATE CHECK
        # Create a unique key based on the start/end points rounded to 3 decimals.
        p1 = edge.PointAtStart
        p2 = edge.PointAtEnd
        # Sort points so direction doesn't matter (A-B is the same as B-A)
        pts = sorted([(round(p1.X, 3), round(p1.Y, 3), round(p1.Z, 3)), 
                      (round(p2.X, 3), round(p2.Y, 3), round(p2.Z, 3))])
        edge_key = tuple(pts)
        
        if edge_key in seen_edge_coords:
            continue
        
        crv = edge.EdgeCurve.DuplicateCurve()
        if not crv:
            continue
            
        total_len = crv.GetLength()
        crv.Domain = rg.Interval(0, total_len)
        
        # 3. SHORT EDGE LOGIC
        # If edge is 4 inches or less, make one line the full length.
        if total_len <= 4.0:
            sc.doc.Objects.AddLine(rg.Line(crv.PointAt(0.0), crv.PointAt(total_len)))
        else:
            # Otherwise, make two 2-inch lines at the ends.
            sc.doc.Objects.AddLine(rg.Line(crv.PointAt(0.0), crv.PointAt(line_length)))
            sc.doc.Objects.AddLine(rg.Line(crv.PointAt(total_len), crv.PointAt(total_len - line_length)))
        
        seen_edge_coords.add(edge_key)
        processed_count += 1
    
    sc.doc.Views.Redraw()
    print("Finished - Processed {0} unique internal edges. Naked edges were skipped.".format(processed_count))

if __name__ == "__main__":
    create_lines_on_internal_edges()