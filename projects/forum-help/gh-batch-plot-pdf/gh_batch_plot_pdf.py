# -*- coding: utf-8 -*-
"""
Batch-plot multiple Rhino layouts to ONE combined PDF, driven from Grasshopper.

Forum context:
  https://discourse.mcneel.com/t/batch-plot-from-grasshopper-to-pdf/221262
  Soren Lauesen (2026-07-28, unanswered as of this writing): printing manually
  through Rhino's normal Print dialog merges all selected layouts into a
  single PDF. Doing the equivalent from Grasshopper produces one separate
  PDF file per layout instead of one combined document. The original post
  does not name the specific GH component/plugin he's using (no Human/
  Human UI/Heteroptera-style plot component identified, and no code posted),
  so this script does not attempt to reproduce or patch whatever mechanism
  he was calling. Instead it replaces that step outright: script the plot
  yourself in two verifiable stages (per-layout single-page PDF, then a
  pure-Python merge) rather than depend on a GH plot component's opaque
  multi-file behavior.

WHY layouts come out as separate files in the first place:
  Rhino's own Print dialog batches multiple selected layouts into one PDF
  job because it drives a single print/plot session that appends pages as
  it goes. Any automation path that instead calls a plot/export operation
  once per layout (which is what most "export layout to PDF" GH components
  and generic -Print scripting loops do) naturally produces N separate
  single-page files, because each invocation opens and closes its own PDF
  writer. There is no rhinoscriptsyntax function that plots page layouts to
  PDF, combined or otherwise (confirmed by reading the current
  rhinoscriptsyntax source, Scripts/rhinoscript/view.py and document.py, on
  github.com/mcneel/rhinoscriptsyntax on 2026-07-31 -- neither module has a
  print/plot/PDF-export wrapper). The only scriptable path to Rhino's
  plot engine is the command line "-Print" command via rs.Command(), which
  is what this script uses, once per layout, into a temp folder -- then
  merges those temp PDFs into one file with pypdf. This sidesteps the
  "single combined print job" behavior entirely and replaces it with an
  explicit merge step you fully control.

VERIFIED this session (2026-07-31), all read directly from mcneel source,
not from memory:
  - rs.ViewNames(True, 1) returns page-layout view names only.
    (Scripts/rhinoscript/view.py, ViewNames, view_type=1 branch.)
  - rs.CurrentView(name) sets the active view/layout and returns the
    previous active view's name; it accepts a layout name because
    scriptcontext.doc.Views.Find(view, False) matches any RhinoView,
    including page views, not just model viewports.
    (Scripts/rhinoscript/view.py, CurrentView.)
  - rs.Command(commandString, echo=True) -> bool runs one command per call;
    the docstring explicitly warns against chaining multiple commands in
    one call string. (Scripts/rhinoscript/application.py, Command.)

NOT VERIFIED -- flag before relying on this in production:
  - The exact scripted (command-line) option keywords/order for "-Print"
    in the Rhino version you're running. docs.mcneel.com and the McNeel
    forum were both unreachable from this environment this session (403s
    through the network proxy), so the PRINT_COMMAND_TEMPLATE below is
    built from long-standing, well-known Rhino scripting convention
    (Destination=File / Filename="...") but its literal token spelling,
    ordering, and required trailing Enters have NOT been confirmed against
    live docs or a live Rhino session for your specific Rhino version.
    -Print's prompt sequence has changed across Rhino 5/6/7/8 and can also
    depend on whether a page setup / plot device is already saved on the
    layout. Do this once before trusting the script:
      1. Open the Rhino command line, run "Print" (no dash) once manually,
         set it up exactly how you want (PDF destination, paper size,
         scale, etc.), and save that as a Page Setup on the layout
         (the Print dialog has a "Save" option for page setups).
      2. Then run "-Print" (with the dash) once manually and read the
         command-line prompts Rhino actually shows -- they will reference
         your saved Page Setup by name. Use Window > Panels > History, or
         just watch the command line, to capture the exact prompt text and
         the option keywords it accepts.
      3. Update PRINT_COMMAND_TEMPLATE below to match what you observed.
    This repo's prior print-command-wrapper project (referenced in the
    task brief for this script) was not present in this checkout to cross-
    check against -- if you have it elsewhere, diff the two before trusting
    either.
  - Whether "-Print" can target a raw PDF writer without a Windows/macOS
    PDF virtual printer or an Adobe PDF driver installed. On most Windows
    Rhino installs, "Print" with Destination=File and a .pdf filename
    routes through Rhino's own built-in PDF writer (no virtual printer
    needed) -- but this has not been confirmed live for your Rhino build.

DEPENDENCY (external, not part of Rhino's own scripting environment):
  pypdf (the actively maintained successor to PyPDF2; PyPDF2 itself is
  deprecated upstream in favor of pypdf, same API shape for what's used
  here). This script uses pypdf.PdfWriter.append() and .write(), both
  confirmed against the current pypdf source
  (github.com/py-pdf/pypdf, pypdf/_writer.py) on 2026-07-31.

  Rhino 8's Python 3 (CPython via the ScriptEditor / PythonNet bridge) can
  install packages into its own environment with:
      python -m pip install pypdf
  Run that from the same Python Rhino 8 uses (Tools > Options > Python
  in Rhino 8, or `python -m ensurepip` first if pip itself isn't present).
  If you're on Rhino 7 or older with legacy IronPython 2, pip-installed
  CPython packages like pypdf are NOT importable at all inside
  RunPythonScript's IronPython 2 engine -- see the ENGINE note below.

ENGINE: this script targets Rhino 8's Python 3 (CPython/PythonNet), run
inside a GH Python 3 script component, or standalone via ScriptEditor (F5).
It will NOT run under IronPython 2 / the legacy RunPythonScript command --
pypdf has no IronPython-compatible build. If you must batch-plot from
Rhino 7 or IronPython 2, drop the merge step in-process and instead shell
out to an external merge tool (e.g. a separate CPython process, or
Ghostscript) after the per-layout PDFs are written; that variant is not
implemented here.

USAGE as a GH Python 3 script component:
  Inputs (declare these on the component):
    layout_names : list[str]   -- layout titles to plot, in the order you
                                   want them to appear in the combined PDF
    output_path  : str          -- full path to the combined output PDF
    run          : bool         -- wire a boolean toggle here; gates
                                   execution so it only fires on demand
  Output:
    a            : str          -- status message

Standalone (no GH): call main() directly from the bottom of this file,
or paste the body into ScriptEditor and hardcode the three inputs.
"""

import os
import tempfile

import rhinoscriptsyntax as rs

try:
    from pypdf import PdfWriter
except ImportError:
    PdfWriter = None


# --- UNVERIFIED: adjust after the manual test described above. ---
# {filename} is substituted with a per-layout temp .pdf path.
# This assumes a Page Setup has already been saved on each layout (see the
# NOT VERIFIED section above) and that -Print will reuse it, prompting only
# for destination/filename. If your Rhino version prompts differently,
# this string is the only thing you should need to change.
PRINT_COMMAND_TEMPLATE = (
    '-Print '
    'Destination=File '
    'Filename="{filename}" '
    'Enter'
)


def plot_layout_to_pdf(layout_name, temp_pdf_path):
    """Make one layout active and plot it to a single-page PDF.

    Returns True on apparent success (rs.Command reported success), False
    otherwise. Does not itself confirm the file was written -- callers
    should check os.path.exists afterward, since a malformed command
    string can return True from rs.Command while still failing inside the
    Print command's own sub-prompts.
    """
    previous = rs.CurrentView(layout_name)
    if previous is None:
        raise ValueError('Layout "{}" not found (rs.CurrentView failed to '
                          'switch to it). Check spelling against '
                          'rs.ViewNames(True, 1).'.format(layout_name))

    command_string = PRINT_COMMAND_TEMPLATE.format(filename=temp_pdf_path)
    ok = rs.Command(command_string, echo=False)
    return ok


def merge_pdfs(pdf_paths, output_path):
    """Merge single-page PDFs (in order) into one combined PDF file.

    Requires pypdf. Raises RuntimeError with an install hint if pypdf is
    not importable rather than failing with a bare ImportError deep in
    the call stack.
    """
    if PdfWriter is None:
        raise RuntimeError(
            'pypdf is not installed in this Python environment. Install it '
            'with: python -m pip install pypdf  (run against the same '
            'Python Rhino 8 uses -- see the DEPENDENCY note in this '
            'script\'s docstring).'
        )

    writer = PdfWriter()
    for path in pdf_paths:
        if not os.path.exists(path):
            raise RuntimeError(
                'Expected per-layout PDF was not created: {}. The -Print '
                'command likely did not complete as scripted -- see the '
                'NOT VERIFIED section in this script\'s docstring and '
                're-check PRINT_COMMAND_TEMPLATE against a manual test.'
                .format(path)
            )
        writer.append(path)

    writer.write(output_path)
    writer.close()


def batch_plot_to_combined_pdf(layout_names, output_path, cleanup_temp=True):
    """Plot each named layout to its own temp PDF, then merge in order.

    Parameters:
      layout_names (list[str]): layout titles, in desired output order.
      output_path (str): full path for the combined output PDF.
      cleanup_temp (bool): delete the per-layout temp PDFs after merging.

    Returns a status string (success or a clear failure reason) rather
    than raising, so a GH component can surface it directly on an output
    without the component turning red on every recoverable issue -- it
    still raises for genuine setup errors (missing pypdf, bad layout name)
    since those need the owner's attention, not a silent partial result.
    """
    if not layout_names:
        return 'No layout names supplied -- nothing to plot.'

    all_layouts = rs.ViewNames(True, 1) or []
    missing = [name for name in layout_names if name not in all_layouts]
    if missing:
        raise ValueError(
            'These layout names were not found in the document: {}. '
            'Available layouts: {}'.format(missing, all_layouts)
        )

    temp_dir = tempfile.mkdtemp(prefix='gh_batch_plot_pdf_')
    temp_pdf_paths = []
    try:
        for i, layout_name in enumerate(layout_names):
            temp_pdf_path = os.path.join(
                temp_dir, '{:03d}_{}.pdf'.format(i, _safe_filename(layout_name))
            )
            plot_layout_to_pdf(layout_name, temp_pdf_path)
            temp_pdf_paths.append(temp_pdf_path)

        merge_pdfs(temp_pdf_paths, output_path)
        return 'OK: combined PDF written to {} ({} layout(s)).'.format(
            output_path, len(layout_names)
        )
    finally:
        if cleanup_temp:
            for path in temp_pdf_paths:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass


def _safe_filename(name):
    """Strip characters that are awkward in filenames on Windows/macOS."""
    keep = (c if (c.isalnum() or c in ('-', '_')) else '_' for c in name)
    return ''.join(keep) or 'layout'


# --- GH Python 3 script component entry point ---------------------------
# Declare component inputs named layout_names, output_path, run; declare
# output named a. Grasshopper injects these as globals at solve time --
# referencing them here is only valid inside a GH component, not when this
# file is run standalone (see the ENGINE/USAGE notes above). Standalone
# runs (ScriptEditor F5, or `python this_file.py`) skip this block
# entirely and do nothing by default -- call batch_plot_to_combined_pdf()
# yourself with hardcoded arguments for that case.
if 'run' in globals():
    try:
        if run:  # noqa: F821 (GH-injected global)
            a = batch_plot_to_combined_pdf(layout_names, output_path)  # noqa: F821
        else:
            a = 'Idle -- set run=True to plot.'
    except Exception as exc:
        a = 'FAILED: {}'.format(exc)
