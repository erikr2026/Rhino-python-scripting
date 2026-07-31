# -Print command wrapper

Answers this forum thread: [Fulfill arguments for Rhino command Print](https://discourse.mcneel.com/t/fulfill-arguments-for-rhino-command-print/219958) (Cd1, posted 2026-06-15).

The owner wanted to script Rhino's `Print` command (destination, layout,
file type, filename, scale) but couldn't find documented `-Print`
command-line syntax. Rhino 8's own help favors the GUI dialog and doesn't
publish a command-line grammar for it.

## What's confirmed

Only one thing is confirmed as actually working, from a reply by forum
user Tom_P in that thread:

```
-_Print _Setup _Destination _Printer "Rhino PDF"
```

This proves `_Setup`, `_Destination`, and `_Printer <name>` are real,
working `-_Print` sub-arguments. Tom_P's advice: build the macro
incrementally in Rhino's macro editor (`_MacroEditor`) step by step,
confirming each step manually, before scripting it.

## What's NOT confirmed

A second macro fragment appeared in a thread linked from that discussion,
attempted by another user, not shown to actually succeed:

```
-Print Setup Destination Printer "Rhino PDF" PageSize 420 297 OutputType=Raster...
```

This is the *only* source for `PageSize`, `OutputType`, and any
color/calibration tokens -- I could not verify any of it. Nor could I find
`Layout`, `Filename`, or `Scale` as `-Print` sub-arguments anywhere.

Live-doc check performed 2026-07-31 (not just relying on trained
knowledge): `developer.rhino3d.com`'s RhinoScriptSyntax reference has no
`-Print` command-line grammar (it documents `rs.Command()` itself, not
individual command syntax). `docs.mcneel.com`'s command help pages
returned HTTP 403 / placeholder content when fetched directly. Discourse's
own search endpoint didn't return usable results via fetch. So: **no
official command-line reference for `-Print` exists that I could locate.**
If the owner has direct Rhino access, the fastest way to actually nail
down the full sub-argument list is running `-_Print` interactively at the
command line and reading each prompt Rhino shows (it will list valid
options at each step) -- then feeding those back here to harden the
wrapper.

## What the wrapper covers

`print_command_wrapper.py` exposes `print_layout()` with named parameters:

- `destination`, `printer`, `run_setup` -- built from the **confirmed**
  Tom_P example. Safe to rely on.
- `layout_name`, `scale`, `filename` -- accepted as parameters (because
  that's what the original ask wanted), passed through as best-guess
  `_Layout`/`_Scale`/`_Filename` tokens, but these are **unconfirmed**.
  They may be wrong token names, wrong argument order, or simply not
  exist as `-Print` sub-arguments at all. Test each one manually via
  `_MacroEditor` before trusting it, especially `filename` -- if Rhino
  ignores it and falls back to an interactive Save dialog, a script
  calling this unattended will hang waiting for input rather than fail
  cleanly (since `rs.Command()` runs modally).

## Usage

```python
import sys
sys.path.append(r"C:\path\to\print-command-wrapper")  # adjust
from print_command_wrapper import print_layout

# Confirmed-safe: reproduces Tom_P's working example.
print_layout(destination="Printer", printer="Rhino PDF")

# Experimental -- test manually first, do not batch unattended:
print_layout(destination="Printer", printer="Rhino PDF",
             layout_name="Layout1", scale="1:50",
             filename=r"C:\prints\hull_layout1.pdf")
```

Run via Rhino 8's `ScriptEditor` command (Python 3 / PythonNet), not
`RunPythonScript` (that's IronPython 2 and is a different engine
entirely).

## Extending

Once you've manually confirmed a real sub-argument (e.g. by running
`-_Print` interactively and reading what Rhino's command line actually
prompts for at each step), add it to `print_layout()` the same way the
confirmed ones are handled: build the token list conditionally, quote any
value containing spaces, and move it out of this "unconfirmed" section of
the README into the confirmed one.
