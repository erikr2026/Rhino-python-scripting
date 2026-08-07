import System
import re
import Rhino
import Rhino.Geometry as rg
import Rhino.UI
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Eto.Forms as forms
import Eto.Drawing as drawing

# --- DATA-ACCURACY CAVEAT (2026-08-07) ---------------------------------
# This alloy list was intended to be sourced from alaskancopper.com's
# Aluminum Sheet & Plate page, but that domain is blocked by this Claude
# Code environment's outbound network policy (403 on both the page and
# their catalog PDF) and could NOT be live-verified. Densities/specs below
# are standard published values for well-established alloys, but the
# owner should cross-check this table against alaskancopper.com (or
# another stock distributor) directly before relying on it for real
# quoting. The 5383-H116 entry was dropped (European alloy designation,
# unlikely to be part of a standard US distributor's stock lineup and
# unverifiable here) and replaced with 3003-H14.
# -------------------------------------------------------------------------

# Standard densities and specs for common aluminum sheet and plate alloys
ALUMINUM_DATA = {
    "5086-H116": {
        "density": 0.0961,
        "spec": "ASTM B 928 / Marine Grade",
        "desc": "Primary marine hull & structural plate. Superior corrosion resistance."
    },
    "5083-H116": {
        "density": 0.0961,
        "spec": "ASTM B 928 / Marine Grade",
        "desc": "High-strength welded marine plate. Maximum joint efficiency."
    },
    "5052-H32": {
        "density": 0.0968,
        "spec": "ASTM B 209",
        "desc": "General marine & industrial sheet. Good formability."
    },
    "3003-H14": {
        "density": 0.0980,
        "spec": "ASTM B209",
        "desc": "General-purpose non-marine sheet. Excellent formability, lower strength than 5000-series."
    },
    "6061-T6": {
        "density": 0.0980,
        "spec": "ASTM B 209",
        "desc": "Structural heat-treated plate/sheet. Good machinability."
    }
}

# Nested by Material -> Product Form -> Alloy, so a future session can add
# other materials (Copper, Brass, Steel) or other product forms under an
# existing material without restructuring the UI code. Today there is only
# one material ("Aluminum") and one product form ("Sheet & Plate"), so this
# nesting is a no-op wrapper around ALUMINUM_DATA.
MATERIALS = {
    "Aluminum": {
        "Sheet & Plate": ALUMINUM_DATA
    }
}

def get_material_alloys(material_key):
    """
    Flatten all product-form alloy dicts under a given material into one
    dict for the Alloy/Type dropdown. Today every material has exactly one
    product form, so this is a no-op merge, but it keeps the lookup generic
    for when a second product form (e.g. Aluminum Extrusion, Aluminum Bar)
    gets added under the same material without needing new UI code.
    """
    product_forms = MATERIALS.get(material_key, {})
    alloys = {}
    for form_alloys in product_forms.values():
        alloys.update(form_alloys)
    return alloys

def parse_fabrication_input(input_str):
    if not input_str:
        return 0.0
    s = str(input_str).strip()
    if not s:
        return 0.0
    try:
        if "/" in s:
            parts = s.split()
            if len(parts) == 2:
                whole = float(parts[0])
                num, denom = parts[1].split("/")
                return whole + (float(num) / float(denom))
            elif len(parts) == 1:
                num, denom = parts[0].split("/")
                return float(num) / float(denom)
        return float(s)
    except Exception:
        return 0.0

class AluminumWeightCalculatorForm(forms.Form):
    def __init__(self):
        super().__init__()
        self.Title = "Aluminum Sheet & Plate Weight Estimator"
        self.ClientSize = drawing.Size(950, 480)
        self.Resizable = True
        self.Padding = drawing.Padding(12)

        self._init_controls()
        self._init_layout()
        self.OnModeChanged(None, None)

    def _init_controls(self):
        # --- Material column ---
        self.lbl_material = forms.Label()
        self.lbl_material.Text = "Material:"

        self.dd_material = forms.DropDown()
        for material in MATERIALS.keys():
            self.dd_material.Items.Add(str(material))
        self.dd_material.SelectedIndex = 0
        self.dd_material.SelectedIndexChanged += self.OnMaterialChanged

        # --- Alloy/Type column ---
        self.lbl_alloy = forms.Label()
        self.lbl_alloy.Text = "Alloy / Temper:"

        self.dd_alloy = forms.DropDown()
        self.dd_alloy.SelectedIndexChanged += self.OnAlloyChanged

        self.lbl_alloy_desc = forms.Label()
        self.lbl_alloy_desc.TextColor = drawing.Colors.Gray
        self.lbl_alloy_desc.Wrap = forms.WrapMode.Word

        # --- Dimensions column ---
        self.lbl_mode = forms.Label()
        self.lbl_mode.Text = "Calculation Mode:"

        self.dd_mode = forms.DropDown()
        self.dd_mode.Items.Add("Sheet & Plate (T x W x L)")
        self.dd_mode.Items.Add("Linear Length")
        self.dd_mode.Items.Add("Surface Area")
        self.dd_mode.Items.Add("Volume")
        self.dd_mode.SelectedIndex = 0
        self.dd_mode.SelectedIndexChanged += self.OnModeChanged

        self.lbl_thickness = forms.Label()
        self.lbl_thickness.Text = "Thickness (in):"

        self.dd_thickness = forms.DropDown()
        thickness_options = [
            '0.060 (16 Ga)', '0.080 (12 Ga)', '0.125 (1/8)', '0.190 (3/16)',
            '0.250 (1/4)', '0.375 (3/8)', '0.500 (1/2)', '0.750 (3/4)', '1.000', 'Custom'
        ]
        for t in thickness_options:
            self.dd_thickness.Items.Add(str(t))
        self.dd_thickness.SelectedIndex = 4
        self.dd_thickness.SelectedIndexChanged += self.OnThicknessComboChanged

        self.txt_thickness = forms.TextBox()
        self.txt_thickness.Text = "0.250"
        self.txt_thickness.TextChanged += self.OnInputChanged

        self.lbl_width = forms.Label()
        self.lbl_width.Text = "Width (in):"
        self.txt_width = forms.TextBox()
        self.txt_width.Text = "48"
        self.txt_width.TextChanged += self.OnInputChanged

        self.lbl_length = forms.Label()
        self.lbl_length.Text = "Length (in):"
        self.txt_length = forms.TextBox()
        self.txt_length.Text = "144"
        self.txt_length.TextChanged += self.OnInputChanged

        self.lbl_qty = forms.Label()
        self.lbl_qty.Text = "Quantity:"
        self.txt_qty = forms.TextBox()
        self.txt_qty.Text = "1"
        self.txt_qty.TextChanged += self.OnInputChanged

        self.lbl_alt_val = forms.Label()
        self.lbl_alt_val.Text = "Value:"
        self.txt_alt_val = forms.TextBox()
        self.txt_alt_val.Text = "1.0"
        self.txt_alt_val.TextChanged += self.OnInputChanged

        self.dd_alt_unit = forms.DropDown()
        self.dd_alt_unit.SelectedIndexChanged += self.OnInputChanged

        # --- Output / results column ---
        self.btn_pick = forms.Button()
        self.btn_pick.Text = "Pick Rhino Geometry"
        self.btn_pick.Click += self.OnPickGeometry

        self.txt_output = forms.TextArea()
        self.txt_output.ReadOnly = True
        self.txt_output.Height = 280

        self.btn_apply = forms.Button()
        self.btn_apply.Text = "Apply to Selected Objects"
        self.btn_apply.Click += self.OnApplyToSelected

        self.btn_copy = forms.Button()
        self.btn_copy.Text = "Copy to Clipboard"
        self.btn_copy.Click += self.OnCopyClipboard

        self.current_result = None

        self.OnMaterialChanged(None, None)

    def _init_layout(self):
        # NOTE: Eto's StackLayoutItem has an implicit C# conversion from
        # Control, but PythonNet (Rhino's CPython bridge) does not apply
        # implicit conversion operators at call sites - Items.Add(a_control)
        # raises TypeError here even though it compiles fine in C#. Every
        # control must be wrapped explicitly in forms.StackLayoutItem(...).
        col_material = forms.StackLayout()
        col_material.Orientation = forms.Orientation.Vertical
        col_material.Spacing = 8
        col_material.Width = 150
        col_material.Items.Add(forms.StackLayoutItem(self.lbl_material))
        col_material.Items.Add(forms.StackLayoutItem(self.dd_material))

        col_alloy = forms.StackLayout()
        col_alloy.Orientation = forms.Orientation.Vertical
        col_alloy.Spacing = 8
        col_alloy.Width = 200
        col_alloy.Items.Add(forms.StackLayoutItem(self.lbl_alloy))
        col_alloy.Items.Add(forms.StackLayoutItem(self.dd_alloy))
        col_alloy.Items.Add(forms.StackLayoutItem(self.lbl_alloy_desc))

        col_dims = forms.StackLayout()
        col_dims.Orientation = forms.Orientation.Vertical
        col_dims.Spacing = 8
        col_dims.Width = 200
        col_dims.Items.Add(forms.StackLayoutItem(self.lbl_mode))
        col_dims.Items.Add(forms.StackLayoutItem(self.dd_mode))
        col_dims.Items.Add(forms.StackLayoutItem(self.lbl_thickness))
        col_dims.Items.Add(forms.StackLayoutItem(self.dd_thickness))
        col_dims.Items.Add(forms.StackLayoutItem(self.txt_thickness))
        col_dims.Items.Add(forms.StackLayoutItem(self.lbl_width))
        col_dims.Items.Add(forms.StackLayoutItem(self.txt_width))
        col_dims.Items.Add(forms.StackLayoutItem(self.lbl_length))
        col_dims.Items.Add(forms.StackLayoutItem(self.txt_length))
        col_dims.Items.Add(forms.StackLayoutItem(self.lbl_alt_val))
        col_dims.Items.Add(forms.StackLayoutItem(self.txt_alt_val))
        col_dims.Items.Add(forms.StackLayoutItem(self.dd_alt_unit))
        col_dims.Items.Add(forms.StackLayoutItem(self.lbl_qty))
        col_dims.Items.Add(forms.StackLayoutItem(self.txt_qty))

        col_output = forms.StackLayout()
        col_output.Orientation = forms.Orientation.Vertical
        col_output.Spacing = 8

        lbl_res = forms.Label()
        lbl_res.Text = "Calculation Summary:"

        col_output.Items.Add(forms.StackLayoutItem(self.btn_pick))
        col_output.Items.Add(forms.StackLayoutItem(lbl_res))
        col_output.Items.Add(forms.StackLayoutItem(self.txt_output, True))
        col_output.Items.Add(forms.StackLayoutItem(self.btn_apply))
        col_output.Items.Add(forms.StackLayoutItem(self.btn_copy))

        main_layout = forms.StackLayout()
        main_layout.Orientation = forms.Orientation.Horizontal
        main_layout.Spacing = 20
        main_layout.Items.Add(forms.StackLayoutItem(col_material))
        main_layout.Items.Add(forms.StackLayoutItem(col_alloy))
        main_layout.Items.Add(forms.StackLayoutItem(col_dims))
        main_layout.Items.Add(forms.StackLayoutItem(col_output, True))

        self.Content = main_layout

    def OnMaterialChanged(self, sender, e):
        material_key = str(self.dd_material.SelectedValue) if self.dd_material.SelectedValue else ""
        alloys = get_material_alloys(material_key)
        self.dd_alloy.Items.Clear()
        for alloy in alloys.keys():
            self.dd_alloy.Items.Add(str(alloy))
        if self.dd_alloy.Items.Count > 0:
            self.dd_alloy.SelectedIndex = 0
        self.OnAlloyChanged(None, None)

    def OnAlloyChanged(self, sender, e):
        material_key = str(self.dd_material.SelectedValue) if self.dd_material.SelectedValue else ""
        alloys = get_material_alloys(material_key)
        key = str(self.dd_alloy.SelectedValue) if self.dd_alloy.SelectedValue else ""
        if key in alloys:
            info = alloys[key]
            self.lbl_alloy_desc.Text = "{0}\n{1}".format(info["spec"], info["desc"])
        self.Calculate()

    def OnThicknessComboChanged(self, sender, e):
        idx = self.dd_thickness.SelectedIndex
        vals = [0.060, 0.080, 0.125, 0.190, 0.250, 0.375, 0.500, 0.750, 1.000]
        if idx >= 0 and idx < len(vals):
            self.txt_thickness.Text = str(vals[idx])
        self.Calculate()

    def OnModeChanged(self, sender, e):
        mode = self.dd_mode.SelectedIndex
        if mode == 0:
            self.lbl_thickness.Visible = True
            self.dd_thickness.Visible = True
            self.txt_thickness.Visible = True
            self.lbl_width.Text = "Width (in):"
            self.lbl_width.Visible = True
            self.txt_width.Visible = True
            self.lbl_length.Visible = True
            self.txt_length.Visible = True
            self.lbl_alt_val.Visible = False
            self.txt_alt_val.Visible = False
            self.dd_alt_unit.Visible = False
        elif mode == 1:
            self.lbl_thickness.Visible = True
            self.dd_thickness.Visible = True
            self.txt_thickness.Visible = True
            self.lbl_width.Text = "Section Width (in):"
            self.lbl_width.Visible = True
            self.txt_width.Visible = True
            self.lbl_length.Visible = False
            self.txt_length.Visible = False
            self.lbl_alt_val.Text = "Linear Length:"
            self.lbl_alt_val.Visible = True
            self.txt_alt_val.Visible = True
            self.dd_alt_unit.Items.Clear()
            self.dd_alt_unit.Items.Add("Feet")
            self.dd_alt_unit.Items.Add("Inches")
            self.dd_alt_unit.SelectedIndex = 0
            self.dd_alt_unit.Visible = True

        elif mode == 2:
            self.lbl_thickness.Visible = True
            self.dd_thickness.Visible = True
            self.txt_thickness.Visible = True
            self.lbl_width.Visible = False
            self.txt_width.Visible = False
            self.lbl_length.Visible = False
            self.txt_length.Visible = False
            self.lbl_alt_val.Text = "Surface Area:"
            self.lbl_alt_val.Visible = True
            self.txt_alt_val.Visible = True
            self.dd_alt_unit.Items.Clear()
            self.dd_alt_unit.Items.Add("Sq. Feet")
            self.dd_alt_unit.Items.Add("Sq. Inches")
            self.dd_alt_unit.SelectedIndex = 0
            self.dd_alt_unit.Visible = True
        elif mode == 3:
            self.lbl_thickness.Visible = False
            self.dd_thickness.Visible = False
            self.txt_thickness.Visible = False
            self.lbl_width.Visible = False
            self.txt_width.Visible = False
            self.lbl_length.Visible = False
            self.txt_length.Visible = False
            self.lbl_alt_val.Text = "Volume:"
            self.lbl_alt_val.Visible = True
            self.txt_alt_val.Visible = True
            self.dd_alt_unit.Items.Clear()
            self.dd_alt_unit.Items.Add("Cubic Inches")
            self.dd_alt_unit.Items.Add("Cubic Feet")
            self.dd_alt_unit.SelectedIndex = 0
            self.dd_alt_unit.Visible = True
        self.Calculate()

    def OnInputChanged(self, sender, e):
        self.Calculate()

    def Calculate(self):
        self.current_result = None
        try:
            material_key = str(self.dd_material.SelectedValue) if self.dd_material.SelectedValue else ""
            alloys = get_material_alloys(material_key)
            key = str(self.dd_alloy.SelectedValue) if self.dd_alloy.SelectedValue else ""
            if key not in alloys:
                return
            alloy_info = alloys[key]
            rho = alloy_info["density"]
            spec = alloy_info["spec"]

            mode = self.dd_mode.SelectedIndex
            qty_val = parse_fabrication_input(self.txt_qty.Text)
            qty = max(1, int(qty_val)) if qty_val > 0 else 1

            # Thickness only genuinely applies to modes that use it in the
            # math below (T x W x L, Linear, Area) - Volume mode computes
            # weight straight from volume and never touches thickness.
            thickness_applies = False
            thickness_val = 0.0

            lines = []
            lines.append("=== ALUMINUM WEIGHT ESTIMATOR ===")
            lines.append("Material: {0}".format(material_key))
            lines.append("Alloy: {0}".format(key))
            lines.append("Spec:  {0}".format(spec))
            lines.append("Density: {0:.4f} lbs/cu.in".format(rho))
            lines.append("--------------------------------")

            if mode == 0:
                t = parse_fabrication_input(self.txt_thickness.Text)
                w = parse_fabrication_input(self.txt_width.Text)
                l = parse_fabrication_input(self.txt_length.Text)

                piece_sqin = w * l
                piece_cuin = piece_sqin * t
                unit_lbs_sqft = t * 144.0 * rho
                piece_weight = piece_cuin * rho
                total_weight = piece_weight * qty
                thickness_applies = True
                thickness_val = t

                lines.append("Dim: {0:.3f} in T x {1:.2f} in W x {2:.2f} in L".format(t, w, l))
                lines.append("Unit Rate: {0:.3f} lbs/sq.ft".format(unit_lbs_sqft))
                lines.append("Piece Wgt: {0:.2f} lbs".format(piece_weight))
                lines.append("Quantity: {0}".format(qty))
                lines.append("--------------------------------")
                lines.append("TOTAL WGT: {0:.2f} lbs".format(total_weight))

            elif mode == 1:
                l_raw = parse_fabrication_input(self.txt_alt_val.Text)
                unit = str(self.dd_alt_unit.SelectedValue) if self.dd_alt_unit.SelectedValue else "Feet"
                l_in = l_raw * 12.0 if unit == "Feet" else l_raw

                t = parse_fabrication_input(self.txt_thickness.Text)
                w = parse_fabrication_input(self.txt_width.Text)
                section_sqin = t * w
                total_cuin = section_sqin * l_in
                piece_weight = total_cuin * rho
                total_weight = piece_weight * qty
                thickness_applies = True
                thickness_val = t

                lines.append("Length: {0:.2f} {1}".format(l_raw, unit))
                lines.append("Piece Wgt: {0:.2f} lbs".format(piece_weight))
                lines.append("Quantity: {0}".format(qty))
                lines.append("--------------------------------")
                lines.append("TOTAL WGT: {0:.2f} lbs".format(total_weight))

            elif mode == 2:
                a_raw = parse_fabrication_input(self.txt_alt_val.Text)
                unit = str(self.dd_alt_unit.SelectedValue) if self.dd_alt_unit.SelectedValue else "Sq. Feet"
                a_sqin = a_raw * 144.0 if unit == "Sq. Feet" else a_raw

                t = parse_fabrication_input(self.txt_thickness.Text)
                total_cuin = a_sqin * t
                piece_weight = total_cuin * rho
                total_weight = piece_weight * qty
                thickness_applies = True
                thickness_val = t

                lines.append("Area: {0:.2f} {1}".format(a_raw, unit))
                lines.append("Piece Wgt: {0:.2f} lbs".format(piece_weight))
                lines.append("Quantity: {0}".format(qty))
                lines.append("--------------------------------")
                lines.append("TOTAL WGT: {0:.2f} lbs".format(total_weight))

            elif mode == 3:
                v_raw = parse_fabrication_input(self.txt_alt_val.Text)
                unit = str(self.dd_alt_unit.SelectedValue) if self.dd_alt_unit.SelectedValue else "Cubic Inches"
                v_cuin = v_raw * 1728.0 if unit == "Cubic Feet" else v_raw

                piece_weight = v_cuin * rho
                total_weight = piece_weight * qty

                lines.append("Volume: {0:.4f} {1}".format(v_raw, unit))
                lines.append("Piece Wgt: {0:.2f} lbs".format(piece_weight))
                lines.append("Quantity: {0}".format(qty))
                lines.append("--------------------------------")
                lines.append("TOTAL WGT: {0:.2f} lbs".format(total_weight))

            self.txt_output.Text = "\n".join(lines)

            self.current_result = {
                "material": material_key,
                "alloy": key,
                "spec": spec,
                "piece_weight": piece_weight,
                "thickness_applies": thickness_applies,
                "thickness": thickness_val,
            }
        except Exception as ex:
            self.txt_output.Text = "Calculation error: {0}".format(str(ex))

    def OnPickGeometry(self, sender, e):
        self.Visible = False
        try:
            objs = rs.GetObjects("Select curves (length), surfaces (area), or solids (volume)", preselect=True)
            if not objs:
                return

            doc_unit = sc.doc.ModelUnitSystem
            scale_to_in = Rhino.RhinoMath.UnitScale(doc_unit, Rhino.UnitSystem.Inches)

            total_length_in = 0.0
            total_area_sqin = 0.0
            total_vol_cuin = 0.0

            for obj_id in objs:
                rh_obj = sc.doc.Objects.FindId(obj_id)
                if not rh_obj:
                    continue
                geom = rh_obj.Geometry

                if isinstance(geom, rg.Curve):
                    total_length_in += geom.GetLength() * scale_to_in
                elif isinstance(geom, (rg.Brep, rg.Extrusion, rg.Mesh, rg.Hatch, rg.Surface)):
                    is_closed_solid = False
                    if isinstance(geom, rg.Brep) and geom.IsSolid:
                        is_closed_solid = True
                    elif isinstance(geom, rg.Extrusion) and geom.IsSolid:
                        is_closed_solid = True
                    elif isinstance(geom, rg.Mesh) and geom.IsClosed:
                        is_closed_solid = True

                    # Extrusions need to be converted to Brep before mass-properties calcs;
                    # Surface/Mesh/Hatch/Brep all support AreaMassProperties.Compute directly.
                    calc_geom = geom.ToBrep() if isinstance(geom, rg.Extrusion) else geom

                    if is_closed_solid:
                        mp = rg.VolumeMassProperties.Compute(calc_geom)
                        if mp:
                            total_vol_cuin += mp.Volume * (scale_to_in ** 3)
                    else:
                        amp = rg.AreaMassProperties.Compute(calc_geom)
                        if amp:
                            total_area_sqin += amp.Area * (scale_to_in ** 2)

            categories_found = sum([total_vol_cuin > 0, total_area_sqin > 0, total_length_in > 0])
            if categories_found > 1:
                Rhino.RhinoApp.WriteLine(
                    "Aluminum Estimator: selection mixed solids/surfaces/curves - "
                    "using volume/area/length priority, other measurements were not applied."
                )

            if total_vol_cuin > 0:
                self.dd_mode.SelectedIndex = 3
                self.txt_alt_val.Text = "{0:.3f}".format(total_vol_cuin)
                self.dd_alt_unit.SelectedIndex = 0
            elif total_area_sqin > 0:
                self.dd_mode.SelectedIndex = 2
                self.txt_alt_val.Text = "{0:.3f}".format(total_area_sqin)
                self.dd_alt_unit.SelectedIndex = 1
            elif total_length_in > 0:
                self.dd_mode.SelectedIndex = 1
                self.txt_alt_val.Text = "{0:.3f}".format(total_length_in)
                self.dd_alt_unit.SelectedIndex = 1

        except Exception as ex:
            Rhino.RhinoApp.WriteLine("Pick error: {0}".format(str(ex)))
        finally:
            self.Visible = True
            self.Calculate()

    def OnApplyToSelected(self, sender, e):
        if not self.current_result:
            Rhino.RhinoApp.WriteLine("Aluminum Estimator: no valid calculation to apply - check alloy selection.")
            return

        self.Visible = False
        try:
            objs = rs.GetObjects("Select objects to apply calculator parameters to", preselect=True)
            if not objs:
                return

            result = self.current_result
            doc = Rhino.RhinoDoc.ActiveDoc
            undo_record = doc.BeginUndoRecord("Apply Aluminum Calculator Parameters")
            try:
                count = 0
                for obj_id in objs:
                    rs.SetUserText(obj_id, "Material", result["material"])
                    rs.SetUserText(obj_id, "Alloy", result["alloy"])
                    rs.SetUserText(obj_id, "Spec", result["spec"])
                    rs.SetUserText(obj_id, "Weight (lbs)", "{0:.2f}".format(result["piece_weight"]))
                    if result["thickness_applies"]:
                        rs.SetUserText(obj_id, "Thickness (in)", "{0:.3f}".format(result["thickness"]))
                    count += 1
            finally:
                doc.EndUndoRecord(undo_record)

            Rhino.RhinoApp.WriteLine("Aluminum Estimator: applied parameters to {0} object(s).".format(count))
            self.txt_output.Text = self.txt_output.Text + "\n--------------------------------\nApplied to {0} selected object(s).".format(count)
        except Exception as e:
            Rhino.RhinoApp.WriteLine("Apply error: {0}".format(str(e)))
        finally:
            self.Visible = True

    def OnCopyClipboard(self, sender, e):
        try:
            forms.Clipboard.Instance.Text = self.txt_output.Text
            rs.Prompt("Results copied to clipboard.")
        except Exception as ex:
            Rhino.RhinoApp.WriteLine("Clipboard error: {0}".format(str(ex)))

def main():
    form = AluminumWeightCalculatorForm()
    # Non-modal: OnPickGeometry/OnApplyToSelected hide the form and prompt
    # for a Rhino viewport selection, which needs the viewport interactive
    # while the form is open - a true modal dialog would block that even
    # while hidden. forms.Form only has Show(), not ShowModal() (that's
    # Eto.Forms.Dialog only).
    form.Show()

if __name__ == "__main__":
    main()
