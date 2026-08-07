import Rhino
import Rhino.DocObjects as rd
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc


def run_volume_dimension():
    doc = sc.doc
    doc_units = doc.ModelUnitSystem
    feet_units = Rhino.UnitSystem.Feet

    scale_to_feet = Rhino.RhinoMath.UnitScale(doc_units, feet_units)
    vol_scale_to_cuft = scale_to_feet**3

    CUFT_TO_GAL = 7.48051948
    CUFT_TO_LITER = 28.3168466

    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt("Select closed surfaces, polysurfaces, meshes, or SubDs")
    go.GeometryFilter = (
        rd.ObjectType.Surface
        | rd.ObjectType.PolysrfFilter
        | rd.ObjectType.Mesh
        | rd.ObjectType.SubD
    )

    unit_options = ["Gallons", "Liters"]
    unit_index = 0

    unit_opt_idx = go.AddOptionList("Unit", unit_options, unit_index)

    while True:
        res = go.GetMultiple(1, 0)
        if res == Rhino.Input.GetResult.Option:
            if go.Option().Index == unit_opt_idx:
                unit_index = go.Option().CurrentListOptionIndex
            continue
        elif res == Rhino.Input.GetResult.Object:
            break
        else:
            return

    selected_objs = [go.Object(i) for i in range(go.ObjectCount)]
    if not selected_objs:
        return

    selected_unit = unit_options[unit_index]

    undo_record = doc.BeginUndoRecord("Volume Dimension")
    try:
        for obj_ref in selected_objs:
            rh_obj = obj_ref.Object()
            geom = obj_ref.Geometry()

            vol_props = None
            if isinstance(geom, rg.Mesh):
                if geom.IsClosed:
                    vol_props = rg.VolumeMassProperties.Compute(geom)
            elif isinstance(geom, rg.Brep):
                if geom.IsSolid:
                    vol_props = rg.VolumeMassProperties.Compute(geom)
            elif isinstance(geom, rg.SubD):
                if geom.IsSolid:
                    vol_props = rg.VolumeMassProperties.Compute(geom)
            elif isinstance(geom, rg.Extrusion):
                brep = geom.ToBrep()
                if brep and brep.IsSolid:
                    vol_props = rg.VolumeMassProperties.Compute(brep)

            if vol_props is None:
                print(
                    "Object ID {0} is not a closed solid. Skipping.".format(
                        rh_obj.Id
                    )
                )
                continue

            centroid = vol_props.Centroid

            # Rhino 8 text fields evaluate a formula directly inside %<...>% -
            # there is no separate Math() wrapper function, so the field
            # functions (Volume, round, etc.) are combined in one expression.
            vol_expr = 'Volume("{0}")'.format(rh_obj.Id)
            vol_scale_str = repr(vol_scale_to_cuft)

            cuft_expr = '{0} * {1}'.format(vol_expr, vol_scale_str)
            cuft_str = '%<round({0}, 2)>% cu ft'.format(cuft_expr)

            if selected_unit == "Gallons":
                second_expr = '{0} * {1}'.format(cuft_expr, repr(CUFT_TO_GAL))
                second_str = '%<round({0}, 2)>% gal'.format(second_expr)
            else:
                second_expr = '{0} * {1}'.format(cuft_expr, repr(CUFT_TO_LITER))
                second_str = '%<round({0}, 2)>% L'.format(second_expr)

            text_content = "{0}\n{1}".format(cuft_str, second_str)

            rh_obj.Select(True)
            doc.Views.Redraw()

            pts = []

            # 1. Get first point
            gp1 = Rhino.Input.Custom.GetPoint()
            gp1.SetCommandPrompt(
                "Pick leader arrow location for object (Press Enter for Centroid)"
            )
            gp1.AcceptNothing(True)
            res1 = gp1.Get()

            if res1 == Rhino.Input.GetResult.Point:
                pts.append(gp1.Point())
            elif res1 == Rhino.Input.GetResult.Nothing:
                pts.append(centroid)
            else:
                rh_obj.Select(False)
                continue

            # 2. Get subsequent points
            while True:
                gp2 = Rhino.Input.Custom.GetPoint()
                if len(pts) == 1:
                    gp2.SetCommandPrompt("Pick next leader point")
                else:
                    gp2.SetCommandPrompt(
                        "Pick next leader point (Press Enter to finish)"
                    )

                gp2.SetBasePoint(pts[-1], True)
                gp2.DrawLineFromPoint(pts[-1], True)
                gp2.AcceptNothing(True)

                res2 = gp2.Get()
                if res2 == Rhino.Input.GetResult.Point:
                    pts.append(gp2.Point())
                elif res2 == Rhino.Input.GetResult.Nothing:
                    if len(pts) >= 2:
                        break
                    else:
                        print(
                            "Leader requires at least 2 points. Pick another point or press Esc to skip."
                        )
                else:
                    pts = []
                    break

            rh_obj.Select(False)

            if len(pts) >= 2:
                rs.EnableRedraw(False)
                view = doc.Views.ActiveView
                if view:
                    cplane = view.ActiveViewport.ConstructionPlane()
                    # Anchor the annotation plane to the first point so the arrow displays correctly
                    cplane.Origin = pts[0]
                    rs.AddLeader(pts, cplane, text_content)
                else:
                    rs.AddLeader(pts, None, text_content)
                rs.EnableRedraw(True)

            doc.Views.Redraw()

    except Exception as e:
        print("Error processing volume dimension: {0}".format(e))
    finally:
        rs.EnableRedraw(True)
        doc.EndUndoRecord(undo_record)


if __name__ == "__main__":
    run_volume_dimension()
