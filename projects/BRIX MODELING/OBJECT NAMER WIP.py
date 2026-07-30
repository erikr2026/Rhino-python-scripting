import Rhino
import Rhino.DocObjects
import Rhino.Input
import Rhino.Commands
import scriptcontext as sc
import Eto.Forms as forms
import Eto.Drawing as drawing
import re

# Pre-compile regular expressions for performance
NUM_RE = re.compile(r'\d+')
LETTER_RE = re.compile(r'\b[a-zA-Z]\b')

def is_numeric(s):
    """Checks if a string represents an integer."""
    try:
        int(s)
        return True
    except ValueError:
        return False

def get_designator(name):
    """
    Extracts the alphanumeric designator from the last 3 characters of the name,
    barring (excluding) any hyphens.
    """
    if not name:
        return ""
    cleaned = name.replace("-", "").strip()
    if not cleaned:
        return ""
    if len(cleaned) >= 3:
        return cleaned[-3:]
    return cleaned

def generate_sequence(core_start, obj_refs, count):
    """
    Generates a sequence of strings of length 'count' starting from 'core_start'.
    If obj_refs are provided, it analyzes the last 3 characters of existing names
    (barring hyphens) to detect and fill sequence gaps before continuing past the maximum.
    """
    if count <= 0:
        return []

    # Case 1: Numeric sequence
    if is_numeric(core_start):
        existing_vals = []
        for obj_ref in obj_refs:
            obj = obj_ref.Object()
            if not obj:
                continue
            name = obj.Attributes.Name
            if name and name.strip():
                des = get_designator(name)
                nums = NUM_RE.findall(des)
                if nums:
                    existing_vals.append(int(nums[-1]))
        
        start_val = int(core_start)
        if existing_vals:
            max_val = max(existing_vals)
        else:
            max_val = start_val - 1
            
        existing_set = set(existing_vals)
        missing = []
        for x in range(start_val, max_val + 1):
            if x not in existing_set:
                missing.append(x)
                
        sequence = []
        # First, fill the gaps
        for val in missing:
            if len(sequence) < count:
                sequence.append(val)
            else:
                break
                
        # Then, continue beyond the highest maximum value
        curr = max(max_val + 1, start_val)
        while len(sequence) < count:
            if curr not in existing_set:
                sequence.append(curr)
            curr += 1
            
        # Match padding format to the core start (default to 3-digit padding for 'Fill in the Blank')
        padding_len = len(core_start) if core_start.startswith('0') or len(core_start) >= 3 else len(core_start)
        sequence_strs = []
        for val in sequence:
            if padding_len > 1:
                sequence_strs.append("{:0{}d}".format(val, padding_len))
            else:
                sequence_strs.append(str(val))
        return sequence_strs

    # Case 2: Alphabetical sequence (single letter designator)
    elif len(core_start) == 1 and core_start.isalpha():
        is_upper = core_start.isupper()
        existing_vals = []
        for obj_ref in obj_refs:
            obj = obj_ref.Object()
            if not obj:
                continue
            name = obj.Attributes.Name
            if name and name.strip():
                des = get_designator(name)
                letters = LETTER_RE.findall(des)
                if letters:
                    last_letter = letters[-1]
                    if (is_upper and last_letter.isupper()) or (not is_upper and last_letter.islower()):
                        existing_vals.append(ord(last_letter))
                        
        start_val = ord(core_start)
        if existing_vals:
            max_val = max(existing_vals)
        else:
            max_val = start_val - 1
            
        existing_set = set(existing_vals)
        missing = []
        for x in range(start_val, max_val + 1):
            if x not in existing_set:
                missing.append(x)
                
        sequence = []
        for val in missing:
            if len(sequence) < count:
                sequence.append(val)
            else:
                break
                
        curr = max(max_val + 1, start_val)
        while len(sequence) < count:
            if curr not in existing_set:
                sequence.append(curr)
            curr += 1
            
        return [chr(val) for val in sequence]

    # Case 3: Fallback for custom labels
    else:
        sequence_strs = []
        for i in range(count):
            sequence_strs.append("{}_{}".format(core_start, i))
        return sequence_strs

class UniversalSequentialNamerDialog(forms.Dialog[bool]):
    def __init__(self, obj_refs):
        self.obj_refs = obj_refs
        self.Title = "Sequential Object Namer"
        self.ClientSize = drawing.Size(420, 240)
        self.Padding = drawing.Padding(15)
        
        # --- UI Controls ---
        self.lbl_mode = forms.Label(Text="Operation Mode:")
        self.drop_mode = forms.DropDown()
        self.drop_mode.DataStore = ["Rename All Selected", "Fill in the Blank"]
        self.drop_mode.SelectedIndex = 0
        
        self.cb_prefix = forms.CheckBox(Text="Enable Prefix:")
        self.txt_prefix = forms.TextBox(Enabled=False)
        
        self.lbl_core = forms.Label(Text="Start Name/Number/Letter:")
        self.txt_core = forms.TextBox(Text="1")
        
        self.cb_suffix = forms.CheckBox(Text="Enable Suffix:")
        self.txt_suffix = forms.TextBox(Enabled=False)
        
        self.btn_ok = forms.Button(Text="Execute")
        self.btn_cancel = forms.Button(Text="Cancel")
        
        # --- Event Bindings ---
        self.drop_mode.SelectedIndexChanged += self.OnModeChanged
        self.cb_prefix.CheckedChanged += self.OnPrefixChanged
        self.cb_suffix.CheckedChanged += self.OnSuffixChanged
        self.btn_ok.Click += self.OnOkClick
        self.btn_cancel.Click += self.OnCancelClick
        
        # --- Layout (Safe for Rhino 9 Eto engine) ---
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(5, 12)
        
        layout.AddRow(self.lbl_mode, self.drop_mode)
        layout.AddRow(self.cb_prefix, self.txt_prefix)
        layout.AddRow(self.lbl_core, self.txt_core)
        layout.AddRow(self.cb_suffix, self.txt_suffix)
        layout.Add(None) 
        
        button_layout = forms.DynamicLayout()
        button_layout.Spacing = drawing.Size(10, 0)
        button_layout.AddRow(None, self.btn_ok, self.btn_cancel, None)
        layout.AddRow(button_layout)
        
        self.Content = layout
        self.UpdateUiForMode()

    def OnPrefixChanged(self, sender, e):
        self.txt_prefix.Enabled = self.cb_prefix.Checked
        
    def OnSuffixChanged(self, sender, e):
        self.txt_suffix.Enabled = self.cb_suffix.Checked
        
    def OnModeChanged(self, sender, e):
        self.UpdateUiForMode()
        
    def UpdateUiForMode(self):
        existing_count = 0
        new_count = 0
        highest_num = -1
        highest_char_code = -1
        
        for obj_ref in self.obj_refs:
            obj = obj_ref.Object()
            if not obj: 
                continue
            name = obj.Attributes.Name
            if name and name.strip():
                existing_count += 1
                des = get_designator(name)
                
                # Check numeric components inside designator
                numbers = NUM_RE.findall(des)
                if numbers:
                    last_num = int(numbers[-1])
                    if last_num > highest_num: 
                        highest_num = last_num
                        
                # Check alphabetical components inside designator
                letters = LETTER_RE.findall(des)
                if letters:
                    code = ord(letters[-1])
                    if code > highest_char_code: 
                        highest_char_code = code
            else:
                new_count += 1

        if self.drop_mode.SelectedIndex == 0:
            self.Title = "Rename All {} Selected Objects".format(len(self.obj_refs))
            self.btn_ok.Text = "Rename All"
            self.txt_core.Text = "001"
        else:
            self.Title = "Fill in the Blank ({} Blanks, {} Existing)".format(new_count, existing_count)
            self.btn_ok.Text = "Fill in the Blank"
            
            # Smart detection: scan to find the lowest missing designator key
            if highest_num != -1:
                existing_nums = []
                for obj_ref in self.obj_refs:
                    obj = obj_ref.Object()
                    if not obj: 
                        continue
                    name = obj.Attributes.Name
                    if name and name.strip():
                        des = get_designator(name)
                        nums = NUM_RE.findall(des)
                        if nums:
                            existing_nums.append(int(nums[-1]))
                existing_set = set(existing_nums)
                first_missing = 1
                while first_missing in existing_set:
                    first_missing += 1
                
                # If there are 3-digit designators in context, maintain the padding formatting
                has_padded = any(len(get_designator(o.Object().Attributes.Name)) == 3 for o in self.obj_refs if o.Object() and o.Object().Attributes.Name)
                if has_padded or first_missing < 100:
                    self.txt_core.Text = "{:03d}".format(first_missing)
                else:
                    self.txt_core.Text = str(first_missing)
                    
            elif highest_char_code != -1:
                existing_chars = []
                for obj_ref in self.obj_refs:
                    obj = obj_ref.Object()
                    if not obj: 
                        continue
                    name = obj.Attributes.Name
                    if name and name.strip():
                        des = get_designator(name)
                        letters = LETTER_RE.findall(des)
                        if letters:
                            existing_chars.append(ord(letters[-1]))
                existing_set = set(existing_chars)
                start_char_code = ord('A') if chr(highest_char_code).isupper() else ord('a')
                first_missing = start_char_code
                while first_missing in existing_set:
                    first_missing += 1
                self.txt_core.Text = chr(first_missing)
            else:
                self.txt_core.Text = "001"
        
    def OnOkClick(self, sender, e):
        self.Result = True
        self.Close()
        
    def OnCancelClick(self, sender, e):
        self.Result = False
        self.Close()

def main():
    geometry_filter = Rhino.DocObjects.ObjectType.Surface | Rhino.DocObjects.ObjectType.PolysrfFilter
    
    rc, obj_refs = Rhino.Input.RhinoGet.GetMultipleObjects(
        "Select surfaces and polysurfaces to process", 
        True, 
        geometry_filter
    )
    if rc != Rhino.Commands.Result.Success or not obj_refs:
        return

    dialog = UniversalSequentialNamerDialog(obj_refs)
    rc_dialog = dialog.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)
    
    if not rc_dialog:
        print("Renaming canceled.")
        return
        
    mode = dialog.drop_mode.SelectedIndex
    raw_prefix = dialog.txt_prefix.Text if dialog.txt_prefix.Text else ""
    raw_suffix = dialog.txt_suffix.Text if dialog.txt_suffix.Text else ""
    core_start = dialog.txt_core.Text if dialog.txt_core.Text else "001"
    
    # MODIFIED: Use hyphen delimiters without spaces
    prefix = raw_prefix + "-" if dialog.cb_prefix.Checked and raw_prefix else ""
    suffix = "-" + raw_suffix if dialog.cb_suffix.Checked and raw_suffix else ""
    
    targets = []
    if mode == 0:
        targets = obj_refs
    else:
        for obj_ref in obj_refs:
            obj = obj_ref.Object()
            if obj and (not obj.Attributes.Name or not obj.Attributes.Name.strip()):
                targets.append(obj_ref)
                
    if not targets:
        Rhino.UI.Dialogs.ShowMessageBox("No valid target objects found for the chosen mode.", "Script Warning")
        return

    # Generate the exact sequence of designators to fill gaps and continue
    if mode == 0:
        # Sequence ignores existing names during total override
        sequence_cores = generate_sequence(core_start, [], len(targets))
    else:
        # Sequence utilizes existing designators to find and fill missing keys first
        sequence_cores = generate_sequence(core_start, obj_refs, len(targets))

    # Disable redrawing for execution speed gains
    sc.doc.Views.RedrawEnabled = False
    
    try:
        for i, obj_ref in enumerate(targets):
            obj = obj_ref.Object()
            if not obj or i >= len(sequence_cores):
                continue
                
            dynamic_core = sequence_cores[i]
            final_name = "{}{}{}".format(prefix, dynamic_core, suffix)
            
            attrs = obj.Attributes.Duplicate()
            attrs.Name = final_name
            sc.doc.Objects.ModifyAttributes(obj_ref.ObjectId, attrs, True)
            
    finally:
        sc.doc.Views.RedrawEnabled = True
        sc.doc.Views.Redraw()
        
    print("Successfully processed renaming for {} surfaces/polysurfaces.".format(len(targets)))

if __name__ == "__main__":
    main()