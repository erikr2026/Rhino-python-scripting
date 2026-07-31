"""
numberer_py3.py
CPython3 port of numberer.py (companion script to the compiled Numberer.rhp
plugin). numberer.py itself was already Python, but written in a Python-2
dialect - `python3 -m py_compile` on the original fails immediately with
"Missing parentheses in call to 'print'" at line 41.

Target engine: Rhino 8 Script Editor, CPython3 mode (F5). The original
appears to have been written for Rhino's legacy IronPython2 engine
(RunPythonScript) - IronPython2 is Python-2-syntax, which explains the
`print` statement and `dict.has_key()` calls below; both are Python-2-only
and raise SyntaxError/AttributeError respectively under CPython3.

Changes made, and why:

1. `print sFont + " is not a valid font name."` (line 41 of the original)
   -> `print(sFont + " is not a valid font name.")`. Python 3's `print` is
   a function, not a statement; this is the error that made the original
   fail `py3 -m py_compile` outright.

2. `sc.sticky.has_key("...")` (14 occurrences) -> `"..." in sc.sticky`.
   `dict.has_key()` was removed in Python 3 (PEP 3106) - `scriptcontext
   .sticky` is a plain dict under both engines, so this is a drop-in
   replacement with identical semantics.

3. `import System.Drawing.Text` - kept, but preceded by
   `import clr` + `clr.AddReference("System.Drawing")`. Rhino 8's CPython3
   host pre-loads RhinoCommon/Eto/core .NET assemblies automatically for
   convenience, but I could not find a live, current doc page confirming
   whether `System.Drawing` specifically is auto-referenced in CPython3
   mode the same way it was under IronPython2 (the only reachable
   developer.rhino3d.com guide pages describing Python/.NET interop still
   describe the IronPython engine, and the CPython3-specific guide pages
   returned 404 when fetched live during this port, 2026-07-31). Adding
   the explicit `clr.AddReference` first is a no-op if the assembly is
   already loaded and a real fix if it isn't, so it's a safe default -
   but this line is flagged as UNVERIFIED LIVE. If `import
   System.Drawing.Text` still fails in Script Editor after this change,
   check Rhino 8's current CPython3-vs-IronPython2 interop docs directly.

4. BUG FOUND AND FIXED in the Suffix option handler. Compare the original
   Prefix handler:

       prefix = rs.StringBox(..., default_value=prefix, ...)
       if prefix is None:
           prefix = sc.sticky["NumPrefix"]      # restore previous value
       else:
           if isinstance(prefix, str):
               sc.sticky["NumPrefix"] = prefix  # save new value

   against the original Suffix handler:

       suffix = rs.StringBox(..., default_value=suffix, ...)
       if suffix is None:
           sc.sticky["NumSuffix"] = suffix      # BUG: writes None into
                                                 # sticky, wiping out the
                                                 # remembered suffix, and
                                                 # never restores `suffix`
                                                 # itself from sticky
       else:
           if isinstance(suffix, str):
               sc.sticky["NumSuffix"] = suffix

   Cancelling the Suffix dialog (`StringBox` returns None on Cancel) wipes
   the previously-remembered suffix from sticky and leaves the local
   `suffix` variable as `None` for the rest of the run - unlike Prefix,
   which correctly restores the previous value on cancel. Fixed here to
   mirror the (correct) Prefix logic. This is a genuine behavior change
   from the original file, flagged per instructions rather than silently
   carried over.

5. `sc.sticky.has_key("NumPrefix")` / `"NumSuffix"` guards were added
   before the now-safe `sc.sticky["NumPrefix"]` / `["NumSuffix"]` restore
   reads (in both Prefix and Suffix handlers) to avoid a `KeyError` if the
   user cancels the dialog on the very first invocation, before anything
   has ever been written to sticky. The original had this same latent gap
   (a `KeyError` on first-run-cancel) in the Prefix handler; both are
   closed here since fixing one and not the other would be inconsistent.

6. The unconditional `Numberer()` call at the bottom of the original was
   wrapped in `if __name__ == "__main__":`. No behavior difference when
   run directly via F5 (the normal use case here) - only matters if this
   file were ever imported as a module elsewhere, which doesn't happen in
   the current workflow.

No other behavior changes. All rhinoscriptsyntax/RhinoCommon calls used
here (`rs.ListBox`, `rs.StringBox`, `rs.AddTextDot`, `rs.AddText`,
`rs.DeleteObject`, `Rhino.Input.Custom.GetPoint/GetOption/GetString/
GetInteger`, `Rhino.Input.Custom.OptionToggle/OptionDouble`) were checked
against the live rhinoscriptsyntax reference (developer.rhino3d.com,
2026-07-31) or are core RhinoCommon `Rhino.Input.Custom` classes unrelated
to the rhinoscriptsyntax version-skew question - none were renamed or
deprecated. `Rhino.Input.Custom` itself is available identically from
CPython3 via the pythonnet bridge (it's just RhinoCommon), so none of that
code needed to change.

Validated with `ast.parse` only (no syntax errors) - there is no live
Rhino in this environment to actually run it. Not run against a live
Rhino in this session.
"""

import clr
clr.AddReference("System.Drawing")

import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs
import System.Drawing.Text


def get_font():

    fams = System.Drawing.Text.InstalledFontCollection().Families
    lcSysFonts = [f.Name.lower() for f in fams]
    sysFonts = [f.Name for f in fams]

    while True:
        crntFont = sc.doc.Fonts[sc.doc.Fonts.CurrentIndex].FaceName
        sFont = crntFont
        if "NumbererCrntFont" in sc.sticky:
            crntFont = sc.sticky["NumbererCrntFont"]

        gs = Rhino.Input.Custom.GetString()
        gs.SetCommandPrompt("Set current font.")
        gs.SetDefaultString(crntFont)
        opList = gs.AddOption("List")

        result = gs.Get()

        if gs.CommandResult() != Rhino.Commands.Result.Success:
            return

        x = gs.OptionIndex()

        if gs.OptionIndex() == opList:
            sFont = rs.ListBox(sysFonts, "Set Nunberer font face.", "Numberer Font", crntFont)
            if not sFont:
                break

        else:
            sFont = gs.StringResult().Trim()

        if sFont.lower() in lcSysFonts:
            idx = sc.doc.Fonts.FindOrCreate(sysFonts[lcSysFonts.index(sFont.lower())], False, False)
            sc.sticky["NumbererCrntFont"] = sc.doc.Fonts[idx].FaceName
            break
        else:
            print(sFont + " is not a valid font name.")
            continue


def Numberer():

    crntNum = 0
    if "MyNum" in sc.sticky:
        crntNum = sc.sticky["MyNum"]

    prefix = None
    if "NumPrefix" in sc.sticky:
        prefix = sc.sticky["NumPrefix"]

    suffix = None
    if "NumSuffix" in sc.sticky:
        suffix = sc.sticky["NumSuffix"]

    outputStyle = 0
    if "NumOutputStyle" in sc.sticky:
        outputStyle = sc.sticky["NumOutputStyle"]

    justCodes = 1, 2, 4, 65536, 131072, 262144

    count = 0
    numList = []
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        opReset = gp.AddOption("Reset")
        StyleList = "Text", "Dots"
        textList = "Size", "Font", "Style", "Justification"
        # OpList = gp.AddOptionList("Output", StyleList, outputStyle)
        opToggleStyle = Rhino.Input.Custom.OptionToggle(outputStyle, "Text", "Dots")
        gp.AddOptionToggle("Output", opToggleStyle)

        opPref = gp.AddOption("Prefix")
        opSuf = gp.AddOption("Suffix")
        textIdx = 0
        opText = gp.AddOption("TextSettings")

        if count > 0:
            opUndo = gp.AddOption("Undo")

        gp.SetCommandPrompt("Set number location or type a number. Current number = " + str(crntNum))
        gp.AcceptNumber(True, True)
        result = gp.Get()
        if gp.CommandResult() != Rhino.Commands.Result.Success:
            return
        if result == Rhino.Input.GetResult.Number:
            crntNum = int(gp.Number())
            continue
        if result == Rhino.Input.GetResult.Option:
            if gp.OptionIndex() == opText:
                while True:

                    # //////////////////////////////////////////
                    # Text Option defaults:
                    crntTextSize = 1
                    if "CurrentNumbererTextSize" in sc.sticky:
                        crntTextSize = sc.sticky["CurrentNumbererTextSize"]

                    textStyleIdx = 0
                    if "NumbererTextStyleIdx" in sc.sticky:
                        textStyleIdx = sc.sticky["NumbererTextStyleIdx"]

                    # textFont= "Arial"
                    # if "NumbererTextFont" in sc.sticky:
                    #     textFont = sc.sticky["NumbererTextFont"]
                    crntFont = sc.doc.Fonts[sc.doc.Fonts.CurrentIndex].FaceName
                    if "NumbererCrntFont" in sc.sticky:
                        crntFont = sc.sticky["NumbererCrntFont"]

                    textJust = 0
                    if "NumbererTextJust" in sc.sticky:
                        textJust = sc.sticky["NumbererTextJust"]

                    # //////////////////////////////////////////

                    # Set up an option getter:
                    # //////////////////////////////////////////
                    go = Rhino.Input.Custom.GetOption()

                    go.SetCommandPrompt("Set text options")
                    opFont = go.AddOption("Font")
                    opDblHeight = Rhino.Input.Custom.OptionDouble(crntTextSize)
                    go.AddOptionDouble("Height", opDblHeight)

                    textStyleList = "Normal", "Bold", "Italic", "BoldItalic"
                    opStyleList = go.AddOptionList("Style", textStyleList, textStyleIdx)

                    justList = "Left", "CenterH", "Right", "Bottom", "CenterV", "Top"
                    opJustList = go.AddOptionList("Justification", justList, textJust)

                    # //////////////////////////////////////////

                    # //////////////////////////////////////////
                    go.Get()

                    sc.sticky["CurrentNumbererTextSize"] = opDblHeight.CurrentValue

                    if go.CommandResult() != Rhino.Commands.Result.Success:
                        break

                    if go.OptionIndex() == opFont:
                        get_font()

                    if go.OptionIndex() == opJustList:
                        sc.sticky["NumbererTextJust"] = go.Option().CurrentListOptionIndex

                    if go.OptionIndex() == opStyleList:
                        sc.sticky["NumbererTextStyleIdx"] = go.Option().CurrentListOptionIndex

                    # //////////////////////////////////////////

            if count > 0:
                if gp.OptionIndex() == opUndo:
                    rs.DeleteObject(numList.pop())
                    count = count - 1
                    crntNum = crntNum - 1
                    continue

            outputStyle = opToggleStyle.CurrentValue
            sc.sticky["NumOutputStyle"] = outputStyle

            if gp.OptionIndex() == opReset:
                gi = Rhino.Input.Custom.GetInteger()
                gi.AcceptNumber(True, True)
                gi.SetDefaultInteger(0)
                gi.SetCommandPrompt("Start numbering at ")
                numResult = gi.Get()
                if gi.CommandResult() != Rhino.Commands.Result.Success:
                    return gi.CommandResult()
                num = int(gi.Number())
                if num:
                    crntNum = num
                    sc.sticky["MyNum"] = num
                    continue
                crntNum = 0
                sc.sticky["MyNum"] = 0
                continue

            elif gp.OptionIndex() == opPref:
                prefix = rs.StringBox("Enter \"none\" for no prefix.", default_value=prefix, title="Numberer Prefix")
                if prefix is None:
                    # Restore the previous value on Cancel rather than
                    # wiping it out. Guarded with `in sc.sticky` so a
                    # cancel on the very first run (nothing stored yet)
                    # doesn't raise KeyError.
                    if "NumPrefix" in sc.sticky:
                        prefix = sc.sticky["NumPrefix"]
                else:
                    if isinstance(prefix, str):
                        sc.sticky["NumPrefix"] = prefix
                continue

            elif gp.OptionIndex() == opSuf:
                suffix = rs.StringBox("Enter \"none\" for no suffix.", default_value=suffix, title="Numberer Suffix")
                if suffix is None:
                    # BUG FIX (see module docstring item 4): the original
                    # wrote `sc.sticky["NumSuffix"] = suffix` here, which
                    # stored None into sticky and permanently wiped the
                    # remembered suffix on a single Cancel. Mirror the
                    # Prefix handler instead: restore the previous value.
                    if "NumSuffix" in sc.sticky:
                        suffix = sc.sticky["NumSuffix"]
                else:
                    if isinstance(suffix, str):
                        sc.sticky["NumSuffix"] = suffix
                continue
        else:
            pt = gp.Point()
            if pt:
                if "NumPrefix" in sc.sticky:
                    prefix = sc.sticky["NumPrefix"]
                if not prefix:
                    prefix = ""

                if "NumSuffix" in sc.sticky:
                    suffix = sc.sticky["NumSuffix"]
                if not suffix:
                    suffix = ""

                if outputStyle:
                    numList.append(rs.AddTextDot(prefix + str(crntNum) + suffix, pt))
                else:
                    crntTextSize = 1
                    if "CurrentNumbererTextSize" in sc.sticky:
                        crntTextSize = sc.sticky["CurrentNumbererTextSize"]

                    textStyleIdx = 0
                    if "NumbererTextStyleIdx" in sc.sticky:
                        textStyleIdx = sc.sticky["NumbererTextStyleIdx"]

                    textJust = 1
                    if "NumbererTextJust" in sc.sticky:
                        textJust = justCodes[sc.sticky["NumbererTextJust"]]

                    crntFont = sc.doc.Fonts[sc.doc.Fonts.CurrentIndex].FaceName
                    if "NumbererCrntFont" in sc.sticky:
                        crntFont = sc.sticky["NumbererCrntFont"]

                    numList.append(rs.AddText(prefix + str(crntNum) + suffix, pt, crntTextSize, crntFont, textStyleIdx, textJust))
                crntNum = crntNum + 1
                count = count + 1
                sc.sticky["MyNum"] = crntNum

            else:
                return


if __name__ == "__main__":
    Numberer()
