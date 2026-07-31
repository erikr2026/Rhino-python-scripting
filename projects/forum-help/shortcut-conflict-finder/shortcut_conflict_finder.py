"""
Shortcut Conflict Finder
========================

Engine: Rhino 8 Python 3 via the ScriptEditor command (type ScriptEditor,
open this .py file, press F5). Uses a plain print(...) console, which is
fine under both engines, but the f-strings below require Python 3 -
if you need to run this via the legacy RunPythonScript (IronPython 2)
command instead, add an encoding declaration and swap the f-strings for
.format() calls.

Base script credit: original TSV-export script posted by the OP in
McNeel Discourse thread "List currently defined keyboard shortcuts"
(https://discourse.mcneel.com/t/list-currently-defined-keyboard-shortcuts/220451,
2026-06-30). That script lists every defined shortcut as tab-separated
text for pasting into Excel, but does not flag shortcuts assigned to
more than one command - which was the OP's actual stated problem
(losing track of shortcuts and re-assigning ones already in use).

This version keeps the original's TSV export intact and adds a second
pass that groups shortcuts by their exact key+modifier combination and
reports any combination bound to more than one distinct macro/command.

Unverified without live Rhino testing: the exact runtime shape of
Rhino.ApplicationSettings.ShortcutKeySettings.GetShortcuts() (iterable
of objects exposing .Key, .Modifier, .Macro) and the string form each
.Modifier enum value takes when a shortcut has multiple modifiers set
(e.g. whether "MacCommand" ever actually appears together with "Ctrl"
in the same value, or is only ever an either/or on Mac). Both are taken
directly from the OP's own script, which the OP reported works on their
machine - this script does not independently re-derive that behavior,
it only adds grouping/reporting logic on top of the same field reads.
"""

import Rhino


def get_shortcut_rows():
    """Return sorted (shortcut_text, macro) rows, exactly as the OP's
    original script produced them - same field reads, same modifier
    normalization, same sort."""
    shortcuts = Rhino.ApplicationSettings.ShortcutKeySettings.GetShortcuts()
    rows = []
    for shortcut in shortcuts:
        key = shortcut.Key
        if shortcut.Modifier:
            modifiers = str(shortcut.Modifier).replace("MacCommand", "Ctrl").split(", ")
        else:
            modifiers = []
        rows.append(["+".join([*modifiers, str(key)]), shortcut.Macro])

    rows.sort(key=lambda r: r[0].lower())
    return rows


def print_tsv(rows):
    """Original export behavior: tab-separated, Excel-pasteable."""
    print("Shortcut\tMacro")
    for shortcut_text, macro in rows:
        print(f"{shortcut_text}\t{macro}")


def find_conflicts(rows):
    """Group rows by shortcut_text (the exact key+modifier combo) and
    return only the groups with more than one distinct macro assigned.

    Returns a list of (shortcut_text, [macro, macro, ...]) tuples,
    sorted the same way as the main list.
    """
    groups = {}
    for shortcut_text, macro in rows:
        groups.setdefault(shortcut_text, []).append(macro)

    conflicts = []
    for shortcut_text, macros in groups.items():
        # Same shortcut can legitimately appear twice with the identical
        # macro (e.g. duplicate registration) - only flag it if there's
        # more than one *distinct* command bound to it.
        distinct_macros = []
        for m in macros:
            if m not in distinct_macros:
                distinct_macros.append(m)
        if len(distinct_macros) > 1:
            conflicts.append((shortcut_text, distinct_macros))

    conflicts.sort(key=lambda c: c[0].lower())
    return conflicts


def print_conflicts(conflicts):
    if not conflicts:
        print("No conflicting shortcuts found - every key combination maps to a single command.")
        return

    print(f"Found {len(conflicts)} shortcut(s) assigned to more than one command:")
    for shortcut_text, macros in conflicts:
        print(f"\n{shortcut_text}  ({len(macros)} commands)")
        for macro in macros:
            print(f"    {macro}")


def main():
    rows = get_shortcut_rows()

    print("=== Full shortcut list (TSV - paste into Excel) ===")
    print_tsv(rows)

    print("\n=== Conflict report ===")
    conflicts = find_conflicts(rows)
    print_conflicts(conflicts)


if __name__ == "__main__":
    main()
