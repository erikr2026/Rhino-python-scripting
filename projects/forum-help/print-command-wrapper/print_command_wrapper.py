"""
print_command_wrapper.py

Engine / how to run: Python 3 (CPython, PythonNet bridge) via Rhino 8's
ScriptEditor command. Open this file in ScriptEditor and press F5. Do NOT
run it via the RunPythonScript command (that invokes IronPython 2 instead,
regardless of this file's contents).

Origin: written to answer this McNeel forum thread, where the owner (Cd1)
couldn't find a documented syntax for scripting Rhino's Print command:
https://discourse.mcneel.com/t/fulfill-arguments-for-rhino-command-print/219958

What is and isn't confirmed (see README.md in this folder for the full
breakdown) -- short version:

  CONFIRMED (from a working example posted in the thread by user Tom_P):
    -_Print _Setup _Destination _Printer "Rhino PDF"
  This proves Setup / Destination / Printer <name> are real, working
  sub-arguments of -_Print.

  NOT CONFIRMED (only appeared in a second-hand macro fragment the OP was
  experimenting with, not shown to actually work, and I could not find any
  official McNeel command-line reference to check it against -- Rhino 8's
  own docs and developer.rhino3d.com do not document -Print's command-line
  grammar at all, and docs.mcneel.com returned 403/placeholder pages when
  fetched live on 2026-07-31):
    PageSize, OutputType, Layout (as a -Print sub-arg), Filename (as a
    -Print sub-arg), Scale, any color/calibration options.

Because of that, this wrapper only bakes in Setup/Destination/Printer as
guaranteed macro tokens. layout_name, scale, and filename are accepted as
parameters (that's what the forum thread asked for), but they're wired in
as *best-guess* tokens clearly marked experimental -- test each one with
the macro editor per Tom_P's advice ("build it manually first") before
trusting it in production. If a token turns out wrong, Rhino will usually
just prompt interactively for that missing/misunderstood value rather than
silently doing something wrong -- but confirm on your own file before
batching this over real print jobs.
"""

import rhinoscriptsyntax as rs


def print_layout(destination="Printer", printer="Rhino PDF",
                  layout_name=None, scale=None, filename=None,
                  run_setup=True):
    """Build and run a -_Print macro from named parameters.

    Parameters
    ----------
    destination : str
        Confirmed working value: "Printer". This maps to the -_Print
        _Destination _Printer branch shown in the forum thread. Other
        destination values (e.g. a "File"-style destination that skips
        the printer driver entirely) were NOT found in any live doc or
        thread reply -- unconfirmed, do not assume they exist.
    printer : str
        Printer/plotter name exactly as it appears in Rhino's Print
        dialog, e.g. "Rhino PDF". Confirmed via the thread's working
        example. Must be quoted in the macro if it contains spaces --
        handled automatically below.
    layout_name : str or None
        UNCONFIRMED as a -_Print sub-argument. Passed through as a
        best-guess `_Layout "<name>"` token if given. Test manually first.
    scale : str or None
        UNCONFIRMED as a -_Print sub-argument. Passed through as a
        best-guess `_Scale <value>` token if given (Rhino's Print dialog
        commonly expresses scale as "1:1", "1:50", etc. -- exact token
        grammar not verified). Test manually first.
    filename : str or None
        UNCONFIRMED as a -_Print sub-argument for setting the output PDF
        path directly from the macro. Passed through as a best-guess
        `_Filename "<path>"` token if given. In practice, Rhino's Print-
        to-PDF flow may still prompt an interactive Save dialog regardless
        of this token -- if so, the macro will stall waiting for input
        rather than silently failing, since rs.Command() runs modally.
        Test manually first; do not batch unattended until confirmed.
    run_setup : bool
        Whether to include the confirmed _Setup token before _Destination.
        True by default, matching the thread's working example.

    Returns
    -------
    bool
        Whatever rs.Command() reports for success (True if Rhino did not
        report a script error -- this does NOT guarantee the PDF was
        actually written, only that the macro string didn't error out).
    """
    tokens = ["-_Print"]

    if run_setup:
        tokens.append("_Setup")

    tokens.append("_Destination")
    if destination:
        tokens.append("_" + destination if not destination.startswith("_") else destination)

    if printer:
        tokens.append("_Printer")
        tokens.append('"%s"' % printer if " " in printer else printer)

    # --- Everything below this line is UNCONFIRMED. See README.md. ---
    if layout_name:
        tokens.append("_Layout")
        tokens.append('"%s"' % layout_name if " " in layout_name else layout_name)

    if scale:
        tokens.append("_Scale")
        tokens.append(str(scale))

    if filename:
        tokens.append("_Filename")
        tokens.append('"%s"' % filename if " " in filename else filename)

    # Close out the command so it doesn't sit waiting for Enter.
    tokens.append("_Enter")

    macro = " ".join(tokens)
    print("Running macro: {}".format(macro))

    ok = rs.Command(macro, echo=True)
    if not ok:
        print("-_Print macro reported failure -- check the command line "
              "history in Rhino for exactly which token it choked on.")
    return ok


if __name__ == "__main__":
    # Minimal confirmed-only example: reproduces Tom_P's working macro.
    print_layout(destination="Printer", printer="Rhino PDF")
