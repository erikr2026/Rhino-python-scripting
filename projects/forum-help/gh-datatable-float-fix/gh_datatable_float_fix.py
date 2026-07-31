"""
GHPython workaround for: Lunchbox 'DataTable' component throwing
    Solution exception: The input string '14.8' was not in a correct format.
on float-valued cells while integer-valued cells parse fine.

Forum thread (unresolved as of 2026-07-31):
https://discourse.mcneel.com/t/help-with-unknown-datatable-error/221305

Engine / how to use:
    Python 3 (CPython) GHPython component in Rhino 8 Grasshopper.
    Add a "GhPython Script" component (not the legacy IronPython "Python
    Script" component) from the Maths > Script panel, or use File >
    "Create Python 3 Script" depending on your GH build. Paste this code
    into it. Set up inputs/outputs as described below, then wire it in
    place of the Lunchbox DataTable + DataSet + Create JSON chain.

Inputs (rename the component's default x/y/... inputs to these):
    headers : list[str]   - column names, one per column, list access
    rows    : tree         - a data tree where each branch is one row and
                              each branch's items are that row's cell
                              values (numbers or number-like strings),
                              matching the order of `headers`
    decimals: int          - optional, decimal places to round floats to
                              for display (default 1, matching the OP's
                              "rounded to one decimal place" data)

Output:
    json    : str  - a JSON string: a list of row-objects, e.g.
                      [{"length": 14.8, "count": 3}, {"length": 9.0}, ...]
    table   : str  - human-readable preview of the same data (for a
                      Panel, so you can sanity-check before it hits any
                      downstream JSON/DataTable component)

Root-cause hypothesis (unverified against Lunchbox's actual source -
I don't have it in front of me and didn't find it published in a form
I could fetch this session): Lunchbox's DataTable component is a
compiled .NET component, not something inspectable/patchable here. The
forum thread itself surfaces a second report of the identical failure
mode from 2023 ("Lunchbox DataTable breaking with float input"), which
is corroborating evidence for a persistent bug rather than a one-off
data issue on the OP's file. The error text ("input string '14.8' was
not in a correct format") is exactly what .NET raises from
`int.Parse("14.8")` or `Convert.ToInt32("14.8")` - a FormatException,
because .NET's Int32.Parse rejects any string containing a decimal
point or non-invariant separator. The likely internal bug: the
component appears to sniff a column's type from its first cell (or
assumes all-integer columns) and then calls an integer parser on every
cell in that column regardless of later values, or a culture setting
somewhere in the parse call isn't pinned to InvariantCulture and is
rejecting '.' as a valid decimal point on certain system locales. Since
Lunchbox is closed-source-in-practice from this session's vantage point,
this script sidesteps the bug entirely by replacing the parsing +
serialization step with plain Python, rather than attempting to patch
Lunchbox's compiled component internals.

Confidence: high that this is a float-vs-int parser bug inside Lunchbox
(matches the exact FormatException wording, matches the 2023 duplicate
report, matches "works with ints, fails on floats" symptom precisely).
Not independently verified against Lunchbox's actual decompiled source
this session - I did not have network access to Lunchbox's GitHub repo
scoped in this session's search, so treat the internal-mechanism
paragraph above as an informed hypothesis, not a confirmed root cause.
"""

import json
import Grasshopper


def _to_number(value, decimals):
    """
    Convert a numeric or numeric-string cell to an int or float.
    Uses plain Python float()/int() - no .NET Parse/Convert calls at all,
    which is what sidesteps culture-sensitive parsing entirely. Python's
    float() and int() always treat '.' as the decimal point regardless
    of OS locale; there is no invariant-culture concept to worry about
    because CPython's numeric parsing is locale-independent by design.
    """
    if value is None:
        return None

    # Already numeric (GH often hands you real Python floats/ints here).
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            return round(value, decimals)
        return value

    s = str(value).strip()
    if s == "":
        return None

    # Try int first (covers "3", "-12"), then float (covers "14.8",
    # "-0.5", "1e3"). This order matters: int("14.8") raises ValueError
    # in Python too, so int-looking strings stay ints and float-looking
    # strings become floats - no forced upcast of every column to float.
    try:
        return int(s)
    except ValueError:
        pass

    try:
        f = float(s)
        return round(f, decimals)
    except ValueError:
        # Not numeric at all - pass through as a plain string so the
        # component doesn't silently drop malformed cells.
        return s


def build_rows(headers, rows_tree, decimals):
    """
    headers: list of column name strings
    rows_tree: Grasshopper DataTree, one branch per row
    Returns: list of dicts, one per row, JSON-serializable.
    """
    if not headers:
        raise ValueError("`headers` input is empty - connect a list of column names.")

    result = []
    for branch in rows_tree.Branches:
        row = {}
        for i, cell in enumerate(branch):
            if i >= len(headers):
                break  # extra cells beyond header count are ignored, not errored
            row[headers[i]] = _to_number(cell, decimals)
        result.append(row)
    return result


# ---- GHPython component body -------------------------------------------
# Expects component inputs named: headers (list access), rows (tree access),
# decimals (item access, optional int, default handled below).

if decimals is None:
    decimals = 1

row_dicts = build_rows(headers, rows, decimals)

json_ = json.dumps(row_dicts)

# Simple readable preview for a Panel.
lines = []
for i, row in enumerate(row_dicts):
    lines.append("row %d: %s" % (i, row))
table = "\n".join(lines)
