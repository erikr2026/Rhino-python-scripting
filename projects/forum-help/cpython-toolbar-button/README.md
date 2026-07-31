# Running a CPython 3 script from a Rhino toolbar button/alias

Source: McNeel Discourse threads (read 2026-07-31):
- https://discourse.mcneel.com/t/better-object-properties-export/220056 (2026-06-17)
- https://discourse.mcneel.com/t/running-a-cpython-script-from-a-rhino-button-icon-instead-of-ironpython/220021 (2026-06-17, resolved)

## Root cause

Rhino 8 ships two separate Python engines (see also the standing rule in
`memory/projects/rhino-python-scripting.md`):

- **`RunPythonScript`** (and the equivalent `!_-RunPythonScript "path"` macro
  commonly bound to toolbar buttons) is the **legacy command and always
  launches IronPython (Python 2)**, regardless of what the target `.py` file
  actually contains. Confirmed by McNeel staff (Michael, "mikeJM") in both
  threads above.
- **`ScriptEditor`** (Rhino 8's new editor, `F5` to run inside the UI) runs
  **CPython 3** via the PythonNet bridge, which is what gives access to
  pip-installed third-party packages such as `openpyxl`.

Luca's object-properties export script used `openpyxl` (a CPython-only
package — IronPython has no C-extension support, so wheels like this simply
can't load there). It worked fine when run manually inside ScriptEditor, but
failed the instant he wired it to a toolbar button using the traditional
`RunPythonScript` macro, because that macro silently routes to IronPython 2
and `import openpyxl` fails there.

This is the same "two execution engines, selected by which command launches
the file, not by anything in the file itself" gotcha already logged in this
repo's Python-3-via-ScriptEditor lesson — this forum thread is a second,
independent real-world confirmation of it.

## Confirmed fix

Use the `ScriptEditor` command's `_Run` sub-command instead of
`RunPythonScript`. Michael's exact confirmed macro syntax (from the
"running a cpython script from a rhino button icon" thread, and reused as
the fix in the "better object properties export" thread):

```
-_ScriptEditor _Run "C:\Path\script.py"
```

To wire this to a toolbar button or alias:

1. Rhino > Toolbar Layout Editor (or the alias manager) > new button/alias.
2. Set the macro/command text to the line above, with the **absolute path**
   to your script, **in double quotes** (required if the path contains
   spaces, which Windows paths under `Program Files`/`OneDrive`/etc.
   frequently do).
3. Leading `-` suppresses the command-line dialog/prompt echo that
   `ScriptEditor` would otherwise show; `_Run` is the sub-command that tells
   ScriptEditor to execute the given file immediately rather than just open
   it for editing.

### Gotchas confirmed in the threads

- **Only absolute paths were confirmed working.** Neither thread discusses
  relative paths, so don't assume a path relative to the current Rhino
  working directory will resolve — hardcode the absolute path in the macro,
  or generate it dynamically if the button needs to work across machines
  (e.g. via a wrapper macro or a small "locate my script" step — not covered
  in either thread).
- **This still briefly surfaces UI, unlike a pure background run.** Luca
  reported `-_ScriptEditor _Run` opens the ScriptEditor interface (and
  potentially an external editor window) rather than running fully silently
  in the background the way old macro-only IronPython buttons did. If a
  fully silent one-click run is the actual requirement, this fix does not
  fully satisfy it — see the "known limitation" note below.
- **No argument-passing syntax was confirmed.** Neither thread shows how
  (or whether) you can pass command-line arguments to the script through
  this macro. If your script needs runtime parameters, use
  `rhinoscriptsyntax.GetString`/`GetObject`/etc. inside the script itself
  to prompt interactively, per this repo's existing standing guidance for
  standalone `.py` files with no GH canvas to supply inputs.
- **Working-directory behavior is unconfirmed.** Neither thread states
  what the CPython process's working directory is when launched this way
  (script's own folder? Rhino's install dir? user profile?). If your script
  writes an output file with a relative path (e.g. the exported `.xlsx`),
  build an absolute output path from `os.path.dirname(__file__)` or a
  hardcoded folder rather than relying on an assumed CWD — this is
  defensive practice given the unconfirmed behavior, not a confirmed
  requirement from the thread.

### Known limitation — not a clean single-click fix

Luca ultimately did **not** end up using `-_ScriptEditor _Run` for his daily
workflow. He judged the extra UI noise (ScriptEditor window opening,
possibly an external editor too) not worth it for a button meant to be
"click and done," and instead installed **ScriptManager** (Dale Fugier's
third-party plugin, "Dale's Garage," available via Rhino's Package Manager).
ScriptManager shows a panel of scripts from a designated folder and runs
the selected one on double-click without opening ScriptEditor at all.

If a fully silent, no-extra-window button is the actual goal (not just "a
button that works"), `-_ScriptEditor _Run` is the McNeel-native fix but
still shows UI; ScriptManager is the workaround that actually achieves the
silent, single-click behavior Luca wanted. Neither thread reports a way to
make `ScriptEditor _Run` itself fully headless.

## Engine for the example script below

`object_properties_export.py` in this folder is written for **Python 3 via
the ScriptEditor / `-_ScriptEditor _Run` pattern**, per the fix above — it
is not meant to be run via `RunPythonScript` (it would fail there, since
`openpyxl` isn't available to IronPython, which is exactly the bug this
whole thread is about).
