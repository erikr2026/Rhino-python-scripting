# aluminum-calculator

**Status: WIP, paused** — runs in Rhino now (bugs #6-#9 fixed, form opens and stays on top), but owner reports it "worked mostly, needs work" — not yet pinned down which parts. Picking back up later; see bottom of journal 2026-08-07 for the fix history so far.

Eto.Forms UI for estimating aluminum sheet/plate weight from marine/structural alloy data (5086, 5083, 5052, 3003, 6061), by thickness x width x length, linear length, surface area, or volume. Can also pick Rhino curves/surfaces/solids directly to auto-fill a mode, and push a calculation's results back onto selected objects as user text.

## How to run

Paste `Aluminum_Weight_Calculator.py` into Rhino's `RunPythonScript` command, or load it via the ScriptEditor and run.

## Data-accuracy caveat

The alloy table (`ALUMINUM_DATA` / `MATERIALS` at the top of the script) was intended to be sourced from alaskancopper.com's Aluminum Sheet & Plate page, but that domain is blocked by the Claude Code environment's outbound network policy (403 on both the page and their catalog PDF) — it could **not** be live-verified against the actual site. Values are standard published alloy densities/specs, not a confirmed distributor's current stock list. Cross-check against alaskancopper.com (or another stock distributor) before relying on this for real quoting.

## Fix history

Initial version (owner-supplied) had five bugs found in review, all fixed in the current copy:
1. Window title/output header/class name said "Alaskan Copper & Brass Estimator" despite the data and math being aluminum-only.
2. `OnPickGeometry`'s geometry-type check omitted `Rhino.Geometry.Surface`, so picking a plain (non-Brep) surface object was silently skipped.
3. Mixed picks (e.g. a solid + a curve together) silently dropped everything but the highest-priority category with no warning — now prints a command-line note when more than one category is found.
4. `OnCopyClipboard` had a stray `rs.StatusBarDistance(0.0)` call unrelated to copying to clipboard — removed.
5. Open `Extrusion` geometry was passed straight to `AreaMassProperties.Compute` instead of being converted to `Brep` first (inconsistent with how solid Extrusions were already handled) — now converts consistently before any mass-properties call.

## 2026-08-07 update: 3-column relayout, Apply-to-Selected, alloy swap

**Relayout.** The form is now four regions left to right, strictly Material → Alloy/Type → Dimensions → Output:
- **Material** column: dropdown, currently just "Aluminum". Data is now nested `MATERIALS = {"Aluminum": {"Sheet & Plate": ALUMINUM_DATA}}` so a future session can add Copper/Brass/Steel or other product forms (e.g. Aluminum Extrusion) without touching the UI code. Changing Material repopulates the Alloy/Type dropdown via a generic handler (`get_material_alloys()`), not one hardcoded to Aluminum.
- **Alloy/Type** column: the alloy dropdown + spec/description label, filtered by the selected Material.
- **Dimensions** column: calculation-mode selector (T×W×L / Linear / Area / Volume) merged with the thickness/width/length/alt-value/unit/quantity fields that used to be split across two columns.
- **Output** column: unchanged in spirit — Pick Rhino Geometry button, results TextArea, new Apply to Selected Objects button, Copy to Clipboard button.

Verified the per-mode unit dropdowns were (and still are) wired correctly: Linear offers Feet/Inches, Surface Area offers Sq. Feet/Sq. Inches, Volume offers Cubic Inches/Cubic Feet — all populated in `OnModeChanged` and consumed correctly in `Calculate()`.

**New: Apply to Selected Objects.** Reverse direction of Pick Rhino Geometry — instead of reading geometry into the calculator, it writes the *current calculation's* output onto whatever objects are selected in the document, as RhinoCommon object user text (`rs.SetUserText`). Prompts for selection the same way `OnPickGeometry` does (hides the form, `rs.GetObjects(..., preselect=True)`, shows it again). For each selected object it writes:
- `"Material"` — e.g. `"Aluminum"`
- `"Alloy"` — e.g. `"5086-H116"`
- `"Spec"` — the alloy's spec string
- `"Weight (lbs)"` — the **per-piece** weight (not the quantity-multiplied total, since it's written once per individual object), formatted `"{0:.2f}"`
- `"Thickness (in)"` — written for T×W×L, Linear, and Surface Area modes (all three use thickness in the underlying math), formatted `"{0:.3f}"`; **omitted** for Volume mode, which never touches thickness

Writes are wrapped in a single undo record (`doc.BeginUndoRecord` / `doc.EndUndoRecord`) per this repo's convention. Guards the case where there's no valid current calculation (e.g. bad alloy selection) the same way `Calculate()` does. On completion it both writes a one-line count to the Rhino command line (`Rhino.RhinoApp.WriteLine`) and appends a confirmation line below the existing calculation summary in the output TextArea (doesn't overwrite it).

**Alloy swap.** Dropped `5383-H116` (a European alloy designation, unlikely to be part of a standard US stock distributor's sheet/plate lineup, and unverifiable against alaskancopper.com per the caveat above). Added `3003-H14` in its place: spec `ASTM B209`, density `0.0980`, general-purpose non-marine sheet with excellent formability and lower strength than the 5000-series. The other four alloys (5086-H116, 5083-H116, 5052-H32, 6061-T6) are unchanged.

## 2026-08-07, real-Rhino run: bug #6 — StackLayoutItem implicit conversion

First actual run in Rhino (via ScriptEditor) crashed immediately in `_init_layout` with `TypeError: Eto.Forms.Label value cannot be converted to Eto.Forms.StackLayoutItem`. Root cause: `Eto.Forms.StackLayoutItem` has an implicit conversion operator from `Control` in C#, so `layout.Items.Add(a_control)` compiles fine in native Eto/C# code — but PythonNet (the CPython bridge Rhino 8/9 uses) does not apply implicit conversion operators at call sites, so passing a bare control where a `StackLayoutItem` is expected throws. This predates the 2026-08-07 relayout — every `.Items.Add(...)` call in `_init_layout` had this bug from the original owner-supplied version, just never caught because the script had never actually been run before (see "Status: WIP — untested inside Rhino" above). Fixed by wrapping every control passed to a `StackLayout.Items.Add(...)` call in `forms.StackLayoutItem(...)` explicitly.

## 2026-08-07, real-Rhino run: bug #7 — `ShowModal` doesn't exist on `Form`

Next run hit `AttributeError: ... object has no attribute 'ShowModal'` in `main()`. `ShowModal` is an `Eto.Forms.Dialog` method, not a `Form` method — `AluminumWeightCalculatorForm` extends `forms.Form`, which only has `Show()`. This is also the functionally correct fix, not just the compiling one: `OnPickGeometry`/`OnApplyToSelected` both hide the form (`self.Visible = False`) to let the owner click objects in the Rhino viewport, then show it again — a true modal dialog blocks interaction with its owner window for its entire lifetime, hidden or not, so modal would have broken both pick/apply flows even if `ShowModal` had existed on `Form`. Fixed `main()` to call `form.Show()`.

## 2026-08-07, real-Rhino run: bug #8 — form not staying on top of Rhino

Once the form finally opened, the owner reported it doesn't stay above the Rhino window - `ShowModal`'s owner argument was the thing keeping it pinned on top, and switching to `Show()` for bug #7 dropped that with nothing replacing it. Fixed by setting `form.Owner = Rhino.UI.RhinoEtoApp.MainWindow` before calling `Show()` - an owned non-modal window stays above its owner without blocking input to it (unlike `ShowModal`), which is exactly what the pick/apply flows need.

## 2026-08-07, real-Rhino run: bug #9 — zero-arg `super()` fails under IronPython 2

Next run hit `__init__() takes at least 1 argument (0 given)` in `AluminumWeightCalculatorForm.__init__`. Message phrasing (Python-2-style "takes at least N (M given)" rather than Python 3's "missing N required positional argument") plus the traceback's temp-file path (`AppData\Local\Temp\TempScript.py`, no `.rhinocode\stage` segment) both point to this run going through Rhino's legacy `RunPythonScript` command (IronPython 2 engine) rather than ScriptEditor's CPython bridge - same "wrong engine" tell as the earlier Pascal Golay scripts this session. Root cause: `super().__init__()` (zero-arg form) only works in Python 3 - IronPython 2 requires the explicit `super(ClassName, self).__init__()` form. Fixed by switching to the explicit form, which works under both engines, so the script no longer depends on which one actually runs it.
