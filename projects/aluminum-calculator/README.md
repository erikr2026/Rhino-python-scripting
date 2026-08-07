# aluminum-calculator

**Status: WIP** — untested inside Rhino. Owner reviewed the source for bugs before running it; not yet verified live.

Eto.Forms UI for estimating aluminum sheet/plate weight from marine/structural alloy data (5086, 5083, 5052, 5383, 6061), by thickness x width x length, linear length, surface area, or volume. Can also pick Rhino curves/surfaces/solids directly to auto-fill a mode.

## How to run

Paste `Aluminum_Weight_Calculator.py` into Rhino's `RunPythonScript` command, or load it via the ScriptEditor and run.

## Fix history

Initial version (owner-supplied) had five bugs found in review, all fixed in the current copy:
1. Window title/output header/class name said "Alaskan Copper & Brass Estimator" despite the data and math being aluminum-only.
2. `OnPickGeometry`'s geometry-type check omitted `Rhino.Geometry.Surface`, so picking a plain (non-Brep) surface object was silently skipped.
3. Mixed picks (e.g. a solid + a curve together) silently dropped everything but the highest-priority category with no warning — now prints a command-line note when more than one category is found.
4. `OnCopyClipboard` had a stray `rs.StatusBarDistance(0.0)` call unrelated to copying to clipboard — removed.
5. Open `Extrusion` geometry was passed straight to `AreaMassProperties.Compute` instead of being converted to `Brep` first (inconsistent with how solid Extrusions were already handled) — now converts consistently before any mass-properties call.
