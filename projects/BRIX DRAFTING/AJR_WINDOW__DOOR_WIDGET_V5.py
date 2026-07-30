import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Eto.Forms as forms
import Eto.Drawing as drawing
import Rhino.Geometry as rg

class MarineOrderDialog(forms.Dialog[bool]):
    # Class-level constants for decoupling window and door specifications
    WINDOW_PRODUCTS = [
        "A5 FIXED WINDOW", "A15 SLIDING WINDOW NO SCREEN",
        "A150 SLIDING WINDOW WITH SCREEN", "A106 HINGED WINDOW",
        "A500 SEALED UNIT", "BONDED WINDOW"
    ]
    
    DOOR_PRODUCTS = [
        "A250 DUTCH DOOR", "A250 INSULATED DOOR",
        "2007 INSULATED SLIDING DOOR", "A55 NON-INSULATED HINGED DOOR FULL GLASS",
        "A55 NON-INSULATED HINGED DOOR", "2018 NON-INSULATED SLIDING DOOR",
        "ENCLOSURE DOOR/HATCH"
    ]
    
    GLASS_STANDARD = ["1/4\" CLEAR", "1/4\" 44% GREY", "1/4\" TEMPERED CLEAR", "1/4\" 20% GREY", "OPAQUE"]
    GLASS_EXTENDED = ["1/4\" CLEAR", "1/4\" 44% GREY", "1/4\" TEMPERED CLEAR", "3/8\" LAMINATED", "3/8\" TEMPERED", "1/4\" 20% GREY", "OPAQUE"]

    def __init__(self):
        super(MarineOrderDialog, self).__init__()
        self.Title = "Marine Window/Door Order Specs"
        self.Padding = drawing.Padding(12)
        self.Resizable = True
        self.ClientSize = drawing.Size(460, 640)

        # Guard flag to prevent recursive updates during event chains
        self._is_updating = False

        # Initialize the layout and event handlers
        self.InitUI()

        self.product_type_dd.SelectedIndexChanged += self.OnProductTypeChanged
        self.product_dd.SelectedIndexChanged += self.OnProductChanged
        self.window_type_dd.SelectedIndexChanged += self.OnWindowTypeChanged
        self.mount_dd.SelectedIndexChanged += self.OnMountingChanged

        # Initial trigger to populate child controls cleanly
        self.OnProductTypeChanged(None, None)

    def _create_label(self, text):
        """Helper method to instantiate a label cleanly without using keyword arguments."""
        lbl = forms.Label()
        lbl.Text = text
        return lbl

    def _create_textbox(self, placeholder=""):
        """Helper to safely build input boxes."""
        tb = forms.TextBox()
        if placeholder:
            tb.PlaceholderText = placeholder
        return tb

    def _create_button(self, text):
        """Helper to build actions cleanly."""
        btn = forms.Button()
        btn.Text = text
        return btn

    def InitUI(self):
        """Initializes the physical interface rows using a reflow-safe dynamic layout."""
        self.layout = forms.DynamicLayout()
        self.layout.Spacing = drawing.Size(10, 10)

        # 1. PRODUCT TYPE
        self.product_type_dd = forms.DropDown()
        self.product_type_dd.DataStore = ["Window", "Door"]
        self.product_type_dd.SelectedIndex = 0
        self.layout.AddRow(self._create_label("Product Type:"), self.product_type_dd)

        # 2. PRODUCT MODEL
        self.product_dd = forms.DropDown()
        self.layout.AddRow(self._create_label("Product Model:"), self.product_dd)

        # 3. DOOR CORNER TYPE (Contextual for Non-Sliding Doors)
        self.door_corner_label = self._create_label("Door Corner Type:")
        self.door_corner_dd = forms.DropDown()
        self.door_corner_dd.DataStore = ["4\" RADIUS", "MITERED"]
        self.door_corner_dd.SelectedIndex = 0
        self.layout.AddRow(self.door_corner_label, self.door_corner_dd)

        # 4. MOUNTING STYLE
        self.mount_dd = forms.DropDown()
        self.layout.AddRow(self._create_label("Mounting Style:"), self.mount_dd)

        # 5. CLAMP WALL THICKNESS
        self.clamp_thickness_label = self._create_label("Clamp Wall Thickness:")
        self.clamp_thickness_tb = self._create_textbox("e.g. 1 3/4 or 3/16")
        self.layout.AddRow(self.clamp_thickness_label, self.clamp_thickness_tb)

        # 6. LOCKSET OPTIONS (Contextual for Doors)
        self.lockset_label = self._create_label("Lockset Options:")
        self.lockset_dd = forms.DropDown()
        self.lockset_dd.DataStore = ["Trioving", "Privacy Lock", "No Lock"]
        self.lockset_dd.SelectedIndex = 0
        self.layout.AddRow(self.lockset_label, self.lockset_dd)

        # 7. DOOR HANDLING / SWING (Contextual for Doors)
        self.door_handing_label = self._create_label("Door Handling / Swing:")
        self.door_handing_dd = forms.DropDown()
        self.layout.AddRow(self.door_handing_label, self.door_handing_dd)

        # 8. INCLUDED WINDOW TYPE (Contextual for Doors)
        self.window_type_label = self._create_label("Included Window Type:")
        self.window_type_dd = forms.DropDown()
        self.layout.AddRow(self.window_type_label, self.window_type_dd)

        # 9. WINDOW CORNER STYLE
        self.corners_dd = forms.DropDown()
        self.layout.AddRow(self._create_label("Window Corner Style:"), self.corners_dd)

        # 10. GLASS TINT SPEC
        self.glass_dd = forms.DropDown()
        self.layout.AddRow(self._create_label("Glass & Tint Spec:"), self.glass_dd)

        # 10b. VENT OPTIONS (Dynamically configured with updated terminology)
        self.vent_label = self._create_label("Vent:")
        self.vent_dd = forms.DropDown()
        self.vent_dd.DataStore = ["Vent Upper", "Vent Lower", "No Vent"]
        self.vent_dd.SelectedIndex = 2  # Default to "No Vent"
        self.layout.AddRow(self.vent_label, self.vent_dd)

        # 11. FINISH / PAINT
        self.paint_dd = forms.DropDown()
        self.paint_dd.DataStore = ["ANODIZED ALUM", "BLACK", "OFF-WHITE", "BRIGHT WHITE", "SILVER PAINTED"]
        self.paint_dd.SelectedIndex = 0
        self.layout.AddRow(self._create_label("Finish / Paint:"), self.paint_dd)

        # 12. QUANTITY REQUIRED
        self.quantity_tb = self._create_textbox("e.g. 1")
        self.layout.AddRow(self._create_label("Quantity Required:"), self.quantity_tb)

        # Dynamic spacers
        self.layout.AddRow(None)

        # Confirmations
        self.ok_button = self._create_button("OK")
        self.ok_button.Click += self.OnOK
        cancel_button = self._create_button("Cancel")
        cancel_button.Click += lambda s, e: self.Close(False)

        self.layout.AddSeparateRow(None, self.ok_button, cancel_button)
        self.DefaultButton = self.ok_button
        self.AbortButton = cancel_button

        self.Content = self.layout

    def OnProductTypeChanged(self, sender, e):
        """Toggles structural parameters based on major categories (Window vs. Door)."""
        is_window = (self.product_type_dd.SelectedValue == "Window")
        
        self.window_type_label.Visible = not is_window
        self.window_type_dd.Visible = not is_window
        self.lockset_label.Visible = not is_window
        self.lockset_dd.Visible = not is_window
        self.door_handing_label.Visible = not is_window
        self.door_handing_dd.Visible = not is_window
        
        self.product_dd.DataStore = self.WINDOW_PRODUCTS if is_window else self.DOOR_PRODUCTS
        self.product_dd.SelectedIndex = 0
        
        self.UpdateFormState()

    def OnProductChanged(self, sender, e):
        self.UpdateFormState()

    def OnWindowTypeChanged(self, sender, e):
        if self._is_updating: return
        self.UpdateFormState()

    def OnMountingChanged(self, sender, e):
        """Manages visibility of the precision wall sizing inputs."""
        is_clamp = (self.mount_dd.SelectedValue == "Clamp Ring")
        self.clamp_thickness_label.Visible = is_clamp
        self.clamp_thickness_tb.Visible = is_clamp
        if not is_clamp:
            self.clamp_thickness_tb.Text = ""

    def UpdateFormState(self):
        """Evaluates chosen models and applies dynamic visibility and data rules."""
        if self._is_updating: return
        self._is_updating = True
        
        try:
            prod_type = self.product_type_dd.SelectedValue
            product = self.product_dd.SelectedValue
            if not product: return

            # Manage Door Corners, Handing, Windows, and Vents
            if prod_type == "Door":
                if "SLIDING" in product.upper():
                    self.door_corner_label.Visible = False
                    self.door_corner_dd.Visible = False
                else:
                    self.door_corner_label.Visible = True
                    self.door_corner_dd.Visible = True

                # Determine window configurations
                if product in ["A250 DUTCH DOOR", "A250 INSULATED DOOR", "A55 NON-INSULATED HINGED DOOR"]:
                    opts = ["A5 FIXED WINDOW", "A15 SLIDING WINDOW NO SCREEN", "A150 SLIDING WINDOW WITH SCREEN", "A15 DROP SLIDER NO SCREEN", "A150 DROP SLIDER WINDOW WITH SCREEN"]
                elif product == "2007 INSULATED SLIDING DOOR":
                    opts = ["A5 FIXED WINDOW", "A15 SLIDING WINDOW NO SCREEN", "A15 DROP SLIDER NO SCREEN"]
                elif product == "A55 NON-INSULATED HINGED DOOR FULL GLASS":
                    opts = ["FULL GLASS 1/4\" TEMPERED"]
                elif product == "2018 NON-INSULATED SLIDING DOOR":
                    opts = ["A5 FIXED WINDOW"]
                elif product == "ENCLOSURE DOOR/HATCH":
                    opts = ["3/16\" ALUMINUM SHEET"]
                else:
                    opts = []
                
                new_opts = opts + ["NO WINDOW"]
                current_win_type = self.window_type_dd.SelectedValue
                self.window_type_dd.DataStore = new_opts
                if current_win_type in new_opts:
                    self.window_type_dd.SelectedValue = current_win_type
                else:
                    self.window_type_dd.SelectedIndex = 0

                # Set sliding vs swinging direction descriptors
                if "SLIDING" in product.upper():
                    self.door_handing_dd.DataStore = ["Left Sliding", "Right Sliding"]
                else:
                    self.door_handing_dd.DataStore = ["Left Hinged", "Right Hinged"]
                self.door_handing_dd.SelectedIndex = 0

                # Dynamically check if the selected door model supports ventilation vents
                # Non-insulated solid/partial doors like A55 support lower/upper vents.
                can_have_vents = ("A55" in product.upper() and "FULL GLASS" not in product.upper()) or ("2018" in product.upper())
                
                self.vent_label.Visible = can_have_vents
                self.vent_dd.Visible = can_have_vents
                
                if can_have_vents:
                    # Update option store with shop-floor descriptive text
                    self.vent_dd.DataStore = ["Vent Upper", "Vent Lower", "No Vent"]
                    if self.vent_dd.SelectedValue not in ["Vent Upper", "Vent Lower", "No Vent"]:
                        self.vent_dd.SelectedIndex = 2 # Default to No Vent
                else:
                    self.vent_dd.DataStore = ["No Vent"]
                    self.vent_dd.SelectedIndex = 0
            else:
                self.door_corner_label.Visible = False
                self.door_corner_dd.Visible = False
                self.vent_label.Visible = False
                self.vent_dd.Visible = False
                self.vent_dd.DataStore = ["No Vent"]
                self.vent_dd.SelectedIndex = 0

            # Evaluate Bounding Corners
            if product == "ENCLOSURE DOOR/HATCH":
                self.corners_dd.DataStore = ["MITERED"]
                self.corners_dd.Enabled = False
            elif product == "BONDED WINDOW":
                self.corners_dd.DataStore = ["CAD FILE"]
                self.corners_dd.Enabled = False
            elif product == "A55 NON-INSULATED HINGED DOOR" and self.window_type_dd.SelectedValue == "NO WINDOW":
                self.corners_dd.DataStore = ["NONE"]
                self.corners_dd.Enabled = False
            else:
                self.corners_dd.Enabled = True
                if prod_type == "Window":
                    self.corners_dd.DataStore = ["2.5\" RADIUS", "3\" RADIUS", "MITERED", "3\" RADIUS & MITERED"]
                else:
                    self.corners_dd.DataStore = ["2.5\" RADIUS", "3\" RADIUS", "MITERED", "3\" RADIUS & MITERED", "CAD FILE"]
            self.corners_dd.SelectedIndex = 0

            # Evaluate Mounting Specifications
            if prod_type == "Window":
                self.mount_dd.DataStore = ["Bonded"] if product == "BONDED WINDOW" else ["Clamp Ring"]
                self.mount_dd.Enabled = False
            else:
                clamp_only = ["A250 DUTCH DOOR", "A250 INSULATED DOOR", "A55 NON-INSULATED HINGED DOOR FULL GLASS", "A55 NON-INSULATED HINGED DOOR"]
                surface_only = ["2007 INSULATED SLIDING DOOR", "2018 NON-INSULATED SLIDING DOOR", "ENCLOSURE DOOR/HATCH"]
                
                if product in clamp_only:
                    self.mount_dd.DataStore = ["Clamp Ring"]
                    self.mount_dd.Enabled = False
                elif product in surface_only:
                    self.mount_dd.DataStore = ["Surface"]
                    self.mount_dd.Enabled = False
                else:
                    self.mount_dd.DataStore = ["Clamp Ring", "Surface"]
                    self.mount_dd.Enabled = True
                    
            self.mount_dd.SelectedIndex = 0
            self.OnMountingChanged(None, None)

            self.paint_dd.Enabled = (product != "BONDED WINDOW")
            self.UpdateGlassOptions()
            
        finally:
            self._is_updating = False

    def UpdateGlassOptions(self):
        """Applies valid options based on parent configurations."""
        prod_type = self.product_type_dd.SelectedValue
        product = self.product_dd.SelectedValue

        if prod_type == "Door":
            win_type = self.window_type_dd.SelectedValue
            if win_type == "NO WINDOW":
                self.glass_dd.DataStore = ["NONE"]
            elif win_type == "FULL GLASS 1/4\" TEMPERED":
                self.glass_dd.DataStore = ["FULL GLASS 1/4\" TEMPERED"]
            elif win_type == "3/16\" ALUMINUM SHEET":
                self.glass_dd.DataStore = ["3/16\" ALUMINUM SHEET"]
            elif win_type in ["A5 FIXED WINDOW", "A106 HINGED WINDOW"]:
                self.glass_dd.DataStore = self.GLASS_EXTENDED
            else:
                self.glass_dd.DataStore = self.GLASS_STANDARD
        else:
            if product == "BONDED WINDOW":
                self.glass_dd.DataStore = ["1/4\" CLEAR", "1/4\" 44% GREY", "3/8\" CLEAR", "3/8\" 44% GREY"]
            elif product in ["A5 FIXED WINDOW", "A106 HINGED WINDOW"]:
                self.glass_dd.DataStore = self.GLASS_EXTENDED
            else:
                self.glass_dd.DataStore = self.GLASS_STANDARD

        self.glass_dd.SelectedIndex = 0

    def OnOK(self, sender, e):
        """Enforces absolute dimension checks and formats before dialog close."""
        qty_input = self.quantity_tb.Text.strip() if self.quantity_tb.Text else ""
        try:
            if not qty_input or int(qty_input) <= 0:
                raise ValueError
        except ValueError:
            forms.MessageBox.Show("Quantity must be a positive whole number.", "Validation Error")
            return

        if self.mount_dd.SelectedValue == "Clamp Ring":
            thick_input = self.clamp_thickness_tb.Text.strip() if self.clamp_thickness_tb.Text else ""
            is_valid = False
            normalized = thick_input.replace("-", " ")
            parts = normalized.split()
            
            if len(parts) == 2:
                whole_str = parts[0]
                frac_str = parts[1]
                if "/" in frac_str:
                    frac_parts = frac_str.split("/")
                    if len(frac_parts) == 2:
                        try:
                            whole_val = float(whole_str)
                            num = float(frac_parts[0].strip())
                            den = float(frac_parts[1].strip())
                            if whole_val >= 0 and num > 0 and den > 0:
                                is_valid = True
                        except ValueError:
                            pass
                            
            elif len(parts) == 1:
                token = parts[0]
                if "/" in token:
                    frac_parts = token.split("/")
                    if len(frac_parts) == 2:
                        try:
                            num = float(frac_parts[0].strip())
                            den = float(frac_parts[1].strip())
                            if num > 0 and den > 0:
                                is_valid = True
                        except ValueError:
                            pass
                else:
                    try:
                        if float(token) > 0:
                            is_valid = True
                    except ValueError:
                        pass
                        
            if not is_valid:
                forms.MessageBox.Show("Clamp Wall Thickness must be a valid positive measurement.", "Validation Error")
                return

        self.Close(True)


def main():
    dialog = MarineOrderDialog()
    rc = dialog.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)
    
    if rc:
        lines = []
        is_door = (dialog.product_type_dd.SelectedValue == "Door")
        
        # 1. PRODUCT TYPE
        lines.append("Product Type: {}".format(dialog.product_type_dd.SelectedValue))
        
        # 2. PRODUCT MODEL
        lines.append("Product Model: {}".format(dialog.product_dd.SelectedValue))
        
        # 3. DOOR CORNER TYPE
        if is_door and dialog.door_corner_dd.Visible:
            lines.append("Door Corner Type: {}".format(dialog.door_corner_dd.SelectedValue))
            
        # 4. MOUNTING STYLE
        lines.append("Mounting Style: {}".format(dialog.mount_dd.SelectedValue))
        
        # 5. CLAMP WALL THICKNESS
        if dialog.mount_dd.SelectedValue == "Clamp Ring":
            lines.append("Clamp Wall Thickness: {}".format(dialog.clamp_thickness_tb.Text.strip()))
            
        # 6. LOCKSET OPTIONS
        if is_door and dialog.lockset_dd.Visible:
            lines.append("Lockset Options: {}".format(dialog.lockset_dd.SelectedValue))
            
        # 7. DOOR HANDLING / SWING
        if is_door and dialog.door_handing_dd.Visible:
            lines.append("Door Handling / Swing: {}".format(dialog.door_handing_dd.SelectedValue))
            
        # 8. INCLUDED WINDOW TYPE
        if is_door and dialog.window_type_dd.Visible:
            lines.append("Included Window Type: {}".format(dialog.window_type_dd.SelectedValue))
            
        # 9. WINDOW CORNER STYLE
        lines.append("Window Corner Style: {}".format(dialog.corners_dd.SelectedValue))
        
        # 10. GLASS TINT SPEC
        lines.append("Glass & Tint Spec: {}".format(dialog.glass_dd.SelectedValue))
        
        # 10b. VENT OPTIONS (Included conditionally if visible)
        if dialog.vent_dd.Visible:
            lines.append("Vent: {}".format(dialog.vent_dd.SelectedValue))
        
        # 11. FINISH / PAINT
        lines.append("Finish / Paint: {}".format(dialog.paint_dd.SelectedValue))
        
        # 12. QUANTITY REQUIRED
        lines.append("Quantity Required: {}".format(dialog.quantity_tb.Text.strip()))
        
        # Fabrication details
        lines.append("-CUT OUT IS SHOWING ROUGH OPENING\nIN ALUMINUM ON BOAT")
        lines.append("-VIEW IS FROM OUTSIDE LOOKING IN")

        output_text = "\n\n".join(lines)
        pt = rs.GetPoint("Pick insertion point for text label")
        if pt:
            doc = Rhino.RhinoDoc.ActiveDoc
            # Wrap modifications in a safe transactional undo record
            undo_record = doc.BeginUndoRecord("Create Marine Spec Text")
            try:
                text_id = rs.AddText(output_text, pt, height=0.375, font="Arial")
                if text_id and rs.IsDimStyle("WINDOW & DOOR TEMPLATE"):
                    rs.DimensionStyle(text_id, "WINDOW & DOOR TEMPLATE")
                doc.Views.Redraw()
            except Exception as e:
                print("Error drawing spec text: {0}".format(e))
            finally:
                doc.EndUndoRecord(undo_record)

if __name__ == "__main__":
    main()