# Lunchbox DataTable float-parsing workaround

Forum thread: https://discourse.mcneel.com/t/help-with-unknown-datatable-error/221305
(posted 2026-07-29, unresolved as of this writing - two replies just ask
the OP for the full error text / a file attachment, no fix given).

## What Jenn (the OP) reported

- Building a data table for DataSet -> JSON conversion in Grasshopper.
- Chain involves: **Lunchbox `DataTable`** component -> **DataSet** ->
  **Create JSON**. A **DataGrid** component with the same data works fine.
- Error (partial, OP couldn't get the full text):
  `Solution exception: The input string '14.8' was not in a correct format.`
- Integers work. Floats fail across the board, even after rounding to
  one decimal place.
- A prior forum thread from 2023, "Lunchbox DataTable breaking with
  float input," reports the identical symptom - this is corroborating
  evidence of a persistent Lunchbox bug, not a one-off data glitch in
  the OP's file.

## Root-cause hypothesis (confidence: high, not independently verified against Lunchbox source)

The exact error wording - `"The input string '14.8' was not in a
correct format"` - is the standard .NET `FormatException` text thrown by
`Int32.Parse("14.8")` or `Convert.ToInt32("14.8")`. .NET's integer
parser rejects any string containing a decimal point outright; it isn't
a culture/locale issue in the usual sense (wrong decimal separator for
the OS locale), it's that an integer parser is being called on a string
that is a valid float but not a valid int.

Likely mechanism inside Lunchbox's `DataTable` component: it appears to
infer each column's type (probably from the first row's value, or from
some other heuristic) and then applies an integer parse to every cell in
a column it decided was "integer," or its type-sniffing logic doesn't
correctly detect float-valued columns at all and falls back to int
parsing unconditionally. Either way, it's a bug in a closed/compiled
Lunchbox component - not something inspectable or patchable from this
session, since I don't have Lunchbox's source in front of me and didn't
verify this mechanism against it directly. Treat this paragraph as an
informed hypothesis based on the error text and symptom pattern, not a
confirmed read of Lunchbox's actual code.

## Why this script avoids the bug

`gh_datatable_float_fix.py` replaces the Lunchbox `DataTable` -> `DataSet`
-> `Create JSON` chain with a single GHPython component that does its own
parsing and its own JSON serialization in plain Python:

- Uses Python's built-in `int()`/`float()`, never any .NET
  `Parse`/`Convert` call. CPython's numeric parsing is locale-independent
  by design - there is no equivalent of .NET's culture-sensitive decimal
  separator to worry about, so this sidesteps the entire class of bug
  regardless of whether the real Lunchbox issue is a type-sniffing bug
  or a genuine culture mismatch.
- Tries `int(s)` first, falls back to `float(s)` - so integer-looking
  cells stay `int` and float-looking cells become `float` per-cell, not
  per-column. This avoids the "one bad cell wrecks the whole column"
  failure mode that the symptom (works with ints, fails entirely with
  floats) suggests is happening in Lunchbox.
- Serializes with Python's `json` module directly, skipping the
  `DataSet`/`Create JSON` components entirely.

## How to use it as a GHPython component

1. Rhino 8, Grasshopper. Drop a **GhPython Script** component (Python 3 /
   CPython engine - not the legacy IronPython "Python Script" component)
   from the Maths > Script panel.
2. Rename/add inputs to match the script:
   - `headers` - list access, a list of column-name strings (e.g. from a
     Panel or a List Item chain).
   - `rows` - **tree access** (right-click the input > set to "Tree"),
     one branch per row, each branch's items being that row's cell
     values in the same order as `headers`.
   - `decimals` - item access, optional int (defaults to `1` if left
     unconnected, matching the OP's "rounded to one decimal place" data).
3. Add outputs `json_` and `table` (rename the defaults, or add these two
   explicitly) to match what the script assigns.
4. Paste the contents of `gh_datatable_float_fix.py` into the component,
   replacing the boilerplate.
5. Wire `json_` wherever the old `Create JSON` output was going. Wire
   `table` into a Panel first to visually confirm the row data looks
   right before trusting the JSON downstream.

## What's unverified

- I have not seen the OP's actual `.gh`/`.ghx` file, so the exact
  component wiring, whether `DataTable` is fed a tree or a flat list, and
  the true column count/types are inferred from the thread text only.
- I have not decompiled or read Lunchbox's `DataTable` source, so the
  "type-sniffs from first row" mechanism is a plausible hypothesis
  matching the symptom, not a confirmed reading of the bug.
- The full original error text was never posted (OP could only read the
  truncated first line) - if the underlying exception is actually
  something else that merely contains similar wording, this diagnosis
  would need revisiting once the OP posts the full message or the file.
