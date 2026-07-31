# Shortcut Conflict Finder

Extends a script originally posted by the OP on McNeel Discourse:
[List currently defined keyboard shortcuts](https://discourse.mcneel.com/t/list-currently-defined-keyboard-shortcuts/220451)
(2026-06-30).

## What the original script did

The OP's script pulled every defined shortcut from
`Rhino.ApplicationSettings.ShortcutKeySettings.GetShortcuts()`, formatted
each one's modifier+key combo (e.g. `Ctrl+Shift+A`), and printed the whole
list as tab-separated `Shortcut / Macro` text for pasting straight into
Excel. It solved "let me see everything I've bound" but not the actual
problem that made the OP write it: nothing in the script flags when the
same key combination is bound to more than one command.

## What this version adds

`shortcut_conflict_finder.py` keeps the original TSV export word-for-word
(same field reads, same modifier normalization, same sort), then adds a
second pass:

1. Groups all rows by their exact shortcut text (key + modifiers).
2. For any group with more than one *distinct* macro/command bound to it,
   reports it as a conflict, listing every command involved.
3. Prints both sections in one run - full TSV list first, conflict report
   second - so the export-to-Excel workflow still works unchanged, and the
   conflict list is immediately visible in the same console output.

No conflicts found prints an explicit "none found" line rather than
staying silent, so a clean run is unambiguous.

## How to run it

Rhino 8, Python 3, via the **ScriptEditor** command:

1. Type `ScriptEditor`, open `shortcut_conflict_finder.py`.
2. Press F5.
3. Copy the TSV block (from `Shortcut\tMacro` down to the blank line
   before `=== Conflict report ===`) into Excel if you want the sortable
   export; read the conflict report directly in the console.

Not verified against a live Rhino session with actual conflicting
shortcuts configured - the field reads (`.Key`, `.Modifier`, `.Macro`) and
modifier-string handling are carried over unchanged from the OP's own
script, which the OP confirmed works on their machine. The grouping/report
logic is new and was checked by reasoning through the code, not by running
it inside Rhino.
