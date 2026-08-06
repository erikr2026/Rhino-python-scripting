import math
import rhinoscriptsyntax as rs
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc


def debug_log(step_name, status, details=""):
    """Prints diagnostic information to the Rhino Command Line."""
    msg = "[OFFSET PARALLEL LINES] [{0}] {1}".format(step_name, status)
    if details:
        msg += " | {0}".format(details)
    print(msg)


def get_line(prompt):
    """Prompts for a single straight line curve and returns its Line geometry + object id."""
    obj_id = rs.GetObject(prompt, rs.filter.curve, preselect=False)
    if not obj_id:
        return None, None

    if not rs.IsLine(obj_id):
        debug_log("Selection", "FAILED", "Selected curve is not a straight line")
        return None, None

    return rs.coerceline(obj_id), obj_id


def check_parallel(line1, line2, tolerance_deg=1.0):
    """Warns (non-fatal) if the two selected lines aren't parallel within tolerance_deg."""
    d1 = line1.Direction
    d2 = line2.Direction
    d1.Unitize()
    d2.Unitize()

    angle_deg = math.degrees(rg.Vector3d.VectorAngle(d1, d2))
    if angle_deg > 90:
        angle_deg = 180 - angle_deg

    if angle_deg > tolerance_deg:
        debug_log("Parallel Check", "WARNING", "Lines are {0:.2f} degrees apart, not exactly parallel".format(angle_deg))


def perpendicular_offset_direction(line1, line2, tolerance):
    """Returns the unit vector perpendicular to line1, pointing from line1 toward line2."""
    t = line1.ClosestParameter(line2.From)
    closest_pt = line1.PointAt(t)

    separation = line2.From - closest_pt

    line1_dir = line1.Direction
    line1_dir.Unitize()
    along = line1_dir * (separation * line1_dir)
    perp = separation - along

    if perp.Length < tolerance:
        debug_log("Direction", "FAILED", "Lines are coincident - no perpendicular direction between them")
        return None

    perp.Unitize()
    return perp


def get_settable_distance(prompt, default=1.0):
    """Prompts for a distance either by typing a number directly, or by clicking two points to measure it."""
    gp1 = Rhino.Input.Custom.GetPoint()
    gp1.SetCommandPrompt(prompt)
    gp1.AcceptNumber(True, False)
    gp1.AcceptNothing(True)
    gp1.SetDefaultNumber(default)
    res1 = gp1.Get()

    if res1 == Rhino.Input.GetResult.Cancel:
        gp1.Dispose()
        return None
    if res1 == Rhino.Input.GetResult.Nothing:
        gp1.Dispose()
        return default
    if res1 == Rhino.Input.GetResult.Number:
        dist = gp1.Number()
        gp1.Dispose()
        return dist
    if res1 != Rhino.Input.GetResult.Point:
        gp1.Dispose()
        return None

    pt1 = gp1.Point()
    gp1.Dispose()

    gp2 = Rhino.Input.Custom.GetPoint()
    gp2.SetCommandPrompt("Second point to measure distance (or type a number)")
    gp2.AcceptNumber(True, False)
    gp2.DrawLineFromPoint(pt1, True)
    gp2.EnableDrawLineFromPoint(True)
    res2 = gp2.Get()
    gp2.Dispose()

    if res2 == Rhino.Input.GetResult.Number:
        return gp2.Number()
    if res2 == Rhino.Input.GetResult.Point:
        return pt1.DistanceTo(gp2.Point())

    return None


def main():
    print("==========================================")
    print("OFFSET 2 PARALLEL LINES APART")
    print("==========================================")

    line1, id1 = get_line("Select FIRST line")
    if not line1:
        debug_log("Step 1", "ABORTED", "No valid first line selected")
        return

    line2, id2 = get_line("Select SECOND line")
    if not line2:
        debug_log("Step 2", "ABORTED", "No valid second line selected")
        return

    tol = sc.doc.ModelAbsoluteTolerance
    check_parallel(line1, line2)

    perp = perpendicular_offset_direction(line1, line2, tol)
    if not perp:
        return

    # Distance = how far EACH line moves away from the other (matches the
    # standard Rhino "Offset distance" convention), not the total new gap.
    distance = get_settable_distance("Offset distance - type a number, or click a point to start measuring", 1.0)
    if distance is None:
        debug_log("Step 3", "ABORTED", "No distance provided")
        return
    if distance <= 0:
        debug_log("Step 3", "FAILED", "Distance must be greater than zero")
        return

    xform1 = rg.Transform.Translation(perp * -distance)
    xform2 = rg.Transform.Translation(perp * distance)

    rs.TransformObject(id1, xform1)
    rs.TransformObject(id2, xform2)

    sc.doc.Views.Redraw()
    debug_log("Complete", "SUCCESS", "Each line moved {0} units away from the other".format(distance))


if __name__ == "__main__":
    main()
