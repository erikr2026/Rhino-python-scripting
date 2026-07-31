"""
Universal Sequential Object Namer (BRIX Modeling).

Prompts the user to pick surfaces/polysurfaces, choose between renaming all
selected objects or only filling in unnamed ones, and applies a generated
sequence of numeric, single-letter, or custom-label designators (with an
optional hyphenated prefix/suffix) to the selected objects' Name attribute.

Streamlined from OBJECT NAMER WIP.py: same behavior/output, de-duplicated
scan/loop logic via small helper functions, dead conditional removed,
docstrings added. See inline "STREAMLINED" comments for what changed and
why; nothing here alters computed results.

Engine/runtime: unmodified from the original file, which did not document
which Rhino Python engine (Python 3 via ScriptEditor vs. legacy IronPython 2
via RunPythonScript) it targets. Not independently re-verified this pass;
confirm before assuming an engine if you run into import/runtime errors.
"""

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


# STREAMLINED: the four call sites in the original file (two in
# generate_sequence, two in UpdateUiForMode) each repeated the same
# "for obj_ref in obj_refs: obj = obj_ref.Object(); if not obj: continue;
# name = obj.Attributes.Name; if name and name.strip(): ..." boilerplate,
# plus repeated get_designator()+NUM_RE/LETTER_RE.findall() lookups.
# Pulled both into shared helpers below. Purely a de-duplication; every
# call site preserves its original filtering behavior.
def _iter_named_objects(obj_refs):
    """
    Yields (obj_ref, obj, name) for every obj_ref in obj_refs whose
    underlying RhinoObject exists and has a non-blank Name attribute.
    Objects with no Name, or a whitespace-only Name, are skipped.
    """
    for obj_ref in obj_refs:
        obj = obj_ref.Object()
        if not obj:
            continue
        name = obj.Attributes.Name
        if name and name.strip():
            yield obj_ref, obj, name


def _last_number_in(name):
    """Returns the last integer found in name's 3-char designator, or None."""
    nums = NUM_RE.findall(get_designator(name))
    return int(nums[-1]) if nums else None


def _last_letter_in(name):
    """Returns the last single-letter match in name's 3-char designator, or None."""
    letters = LETTER_RE.findall(get_designator(name))
    return letters[-1] if letters else None


def _fill_gaps_then_continue(start_val, existing_vals, count):
    """
    Returns a list of `count` integers >= start_val that are not already in
    existing_vals: gaps between start_val and the current max are filled
    first, then the sequence continues upward past that max.
    (Shared by generate_sequence's numeric and single-letter branches, which
    used identical gap-fill/continue logic on int values in the original.)
    """
    max_val = max(existing_vals) if existing_vals else start_val - 1
    existing_set = set(existing_vals)

    missing = [x for x in range(start_val, max_val + 1) if x not in existing_set]
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

    return sequence


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
        for _, _, name in _iter_named_objects(obj_refs):
            num = _last_number_in(name)
            if num is not None:
                existing_vals.append(num)

        start_val = int(core_start)
        sequence = _fill_gaps_then_continue(start_val, existing_vals, count)

        # Match padding format to the core start (default to 3-digit padding for 'Fill in the Blank')
        # STREAMLINED: original conditional here (`len(core_start) if X else len(core_start)`)
        # evaluated to len(core_start) on both branches -- dead conditional, removed.
        padding_len = len(core_start)
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
        for _, _, name in _iter_named_objects(obj_refs):
            letter = _last_letter_in(name)
            if letter and ((is_upper and letter.isupper()) or (not is_upper and letter.islower())):
                existing_vals.append(ord(letter))

        start_val = ord(core_start)
        sequence = _fill_gaps_then_continue(start_val, existing_vals, count)
        return [chr(val) for val in sequence]

    # Case 3: Fallback for custom labels
    else:
        return ["{}_{}".format(core_start, i) for i in range(count)]


class UniversalSequentialNamerDialog(forms.Dialog[bool]):
    """
    Eto dialog collecting the naming mode (rename-all vs. fill-blanks), an
    optional hyphenated prefix/suffix, and the starting designator. Also
    live-updates its title/suggested start value as the mode changes, based
    on a scan of the currently selected objects' existing names.
    """

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
        """Enable/disable the prefix text box to match its checkbox."""
        self.txt_prefix.Enabled = self.cb_prefix.Checked

    def OnSuffixChanged(self, sender, e):
        """Enable/disable the suffix text box to match its checkbox."""
        self.txt_suffix.Enabled = self.cb_suffix.Checked

    def OnModeChanged(self, sender, e):
        """Refresh title/button text/suggested start value for the new mode."""
        self.UpdateUiForMode()

    def UpdateUiForMode(self):
        """
        Recomputes the dialog title, OK-button label, and suggested start
        value in txt_core based on the currently selected mode and a scan
        of obj_refs' existing names.
        """
        # STREAMLINED: original scanned obj_refs up to three separate times
        # (once for counts/highest-value tracking, once more each for
        # existing_nums and existing_chars in the "Fill in the Blank"
        # branch). Single pass here builds the same existing_nums/
        # existing_chars/has_padded data the rest of the method needs.
        named = list(_iter_named_objects(self.obj_refs))
        existing_count = len(named)
        new_count = len(self.obj_refs) - existing_count

        existing_nums = []
        existing_chars = []
        has_padded = False
        for _, _, name in named:
            des = get_designator(name)
            if len(des) == 3:
                has_padded = True
            num = _last_number_in(name)
            if num is not None:
                existing_nums.append(num)
            letter = _last_letter_in(name)
            if letter is not None:
                existing_chars.append(ord(letter))

        highest_num = max(existing_nums) if existing_nums else -1
        highest_char_code = max(existing_chars) if existing_chars else -1

        if self.drop_mode.SelectedIndex == 0:
            self.Title = "Rename All {} Selected Objects".format(len(self.obj_refs))
            self.btn_ok.Text = "Rename All"
            self.txt_core.Text = "001"
        else:
            self.Title = "Fill in the Blank ({} Blanks, {} Existing)".format(new_count, existing_count)
            self.btn_ok.Text = "Fill in the Blank"

            # Smart detection: scan to find the lowest missing designator key
            if highest_num != -1:
                existing_set = set(existing_nums)
                first_missing = 1
                while first_missing in existing_set:
                    first_missing += 1

                # If there are 3-digit designators in context, maintain the padding formatting
                if has_padded or first_missing < 100:
                    self.txt_core.Text = "{:03d}".format(first_missing)
                else:
                    self.txt_core.Text = str(first_missing)

            elif highest_char_code != -1:
                existing_set = set(existing_chars)
                start_char_code = ord('A') if chr(highest_char_code).isupper() else ord('a')
                first_missing = start_char_code
                while first_missing in existing_set:
                    first_missing += 1
                self.txt_core.Text = chr(first_missing)
            else:
                self.txt_core.Text = "001"

    def OnOkClick(self, sender, e):
        """Accept the dialog and close."""
        self.Result = True
        self.Close()

    def OnCancelClick(self, sender, e):
        """Cancel the dialog and close."""
        self.Result = False
        self.Close()


def main():
    """
    Entry point: prompts for surface/polysurface selection, shows the
    naming dialog, computes the designator sequence for the chosen mode,
    and writes the resulting names to each target object's attributes.
    """
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

    # Hyphen delimiters without spaces
    prefix = raw_prefix + "-" if dialog.cb_prefix.Checked and raw_prefix else ""
    suffix = "-" + raw_suffix if dialog.cb_suffix.Checked and raw_suffix else ""

    if mode == 0:
        targets = obj_refs
    else:
        targets = []
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
