# GH batch-plot multiple layouts to one combined PDF

Forum thread (unanswered as of 2026-07-31, zero replies):
https://discourse.mcneel.com/t/batch-plot-from-grasshopper-to-pdf/221262

## The problem as reported

Soren Lauesen: printing manually through Rhino's normal **Print** dialog,
with several layouts selected, merges them into one combined PDF. Doing the
equivalent from Grasshopper produces separate individual PDF files, one per
layout, instead of one combined document. The original post doesn't name
the specific GH component or plugin he's using, and posts no code or
screenshots of a script -- so there's nothing there to reverse-engineer or
patch directly.

## Why this happens

Rhino's Print dialog batches multiple selected layouts into a single PDF
because it runs one print job that appends pages as it goes. Any
automation path that instead calls a plot/export step once per layout
(true of most "export layout to PDF" GH components, and of a naive
`-Print`-in-a-loop script) naturally produces N separate single-page files
-- each call opens and closes its own PDF writer independently. There's no
way to fix this by tweaking a component's PDF-export setting; it needs an
explicit merge step afterward.

## Approach taken here

1. For each requested layout: make it the active view (`rs.CurrentView`),
   then script Rhino's `-Print` command (`rs.Command`) to write that one
   layout to its own temp single-page PDF.
2. Once all temp PDFs exist, merge them in order into one combined PDF
   using `pypdf` (pure Python, no Ghostscript/external binary needed).
3. Clean up the temp files.

This replaces whatever GH plot mechanism Lauesen was using rather than
patching it, since the original post gives no detail on what that
mechanism was.

## Files

- `gh_batch_plot_pdf.py` -- the script. Drop into a GH Python 3 script
  component (see its docstring for the exact input/output names:
  `layout_names`, `output_path`, `run` in; `a` out), or run standalone via
  Rhino 8's `ScriptEditor` (F5) after hardcoding inputs at the bottom.

## Engine / where this runs

Targets **Rhino 8's Python 3** (CPython via the PythonNet bridge) --
either inside a GH Python 3 script component, or standalone via the
`ScriptEditor` command. It will **not** run under legacy IronPython 2 /
the `RunPythonScript` command: `pypdf` has no IronPython-compatible build,
so the merge step is unavailable there. If you're stuck on Rhino 7 or
IronPython 2, write the per-layout PDFs as this script does, then merge
them in a *separate* CPython process (or with Ghostscript) instead of
in-process -- not implemented in this script.

## External dependency: pypdf

Not part of Rhino's own scripting environment -- install it into whichever
Python Rhino 8 actually uses:

```
python -m pip install pypdf
```

Run that against the same Python interpreter Rhino 8's Tools > Options >
Python page points to (or `python -m ensurepip` first if pip itself isn't
present in that environment). `pypdf` is the actively maintained successor
to `PyPDF2`, same relevant API surface (`PdfWriter.append()` /
`PdfWriter.write()`) -- both confirmed against the current pypdf source
(`github.com/py-pdf/pypdf`, `pypdf/_writer.py`) on 2026-07-31, so the
script uses `pypdf` directly rather than the deprecated `PyPDF2` name.

## What's verified vs. not

**Verified this session**, by reading the actual `rhinoscriptsyntax`
source on GitHub (`mcneel/rhinoscriptsyntax`, `Scripts/rhinoscript/`), not
from memory:

- `rs.ViewNames(True, 1)` returns page-layout names only (view.py).
- `rs.CurrentView(name)` switches the active view/layout and works for
  layouts, not just model viewports, because the underlying
  `scriptcontext.doc.Views.Find(view, False)` matches any `RhinoView`
  (view.py).
- `rs.Command(commandString, echo=True) -> bool` runs exactly one command
  per call; its own docstring warns against chaining multiple commands in
  one string (application.py).
- There is **no** rhinoscriptsyntax function for plotting/printing layouts
  to PDF at all -- confirmed by reading through `view.py` and
  `document.py` in full; scripting `-Print` via `rs.Command` is the only
  available path.
- `pypdf.PdfWriter.append(path)` and `.write(output_path)` are current API
  (checked against `pypdf/_writer.py` on GitHub).

**NOT verified -- check before trusting this in production:**

- The exact scripted (`-Print`) option keywords/order/prompt sequence.
  `docs.mcneel.com` and the McNeel forum both returned HTTP 403 through
  this environment's network proxy this session, so
  `PRINT_COMMAND_TEMPLATE` in the script is built from well-known Rhino
  scripting convention (`Destination=File Filename="..."`) but its literal
  spelling has not been confirmed against live docs or a live Rhino
  session. `-Print`'s prompts have changed across Rhino 5/6/7/8 and also
  depend on whether a Page Setup is already saved on the layout. **Do
  this once before relying on the script**: run `Print` (no dash)
  manually, configure and save a Page Setup on each layout, then run
  `-Print` (with the dash) manually once and read what Rhino's command
  line actually prompts for -- adjust `PRINT_COMMAND_TEMPLATE` to match.
- Whether `-Print` with `Destination=File` and a `.pdf` filename routes
  through Rhino's own built-in PDF writer on your platform/build without
  needing a separate PDF virtual printer/driver installed. Commonly true,
  but not confirmed live for a specific Rhino 8 build here.
- The task brief for this write-up referenced a prior-art folder at
  `projects/forum-help/print-command-wrapper/` in this repo for `-Print`
  scripting notes. That folder does not exist in this checkout (checked
  with a recursive glob before writing this) -- if it exists elsewhere,
  diff it against the assumptions above before trusting either one.

## If you get stuck

Most likely failure mode is `PRINT_COMMAND_TEMPLATE` not matching your
Rhino version's actual `-Print` prompts, which will surface as a missing
temp PDF file and a clear `RuntimeError` from `merge_pdfs()` naming the
missing file -- not a silent bad merge.
