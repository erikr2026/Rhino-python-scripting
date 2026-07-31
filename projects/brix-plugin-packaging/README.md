# BRIX plugin packaging — plan (not yet started)

Plan for turning the scripts in the 4 BRIX folders (`BRIX CNC PARTS`,
`BRIX DRAFTING`, `BRIX JOINERY`, `BRIX MODELING`) into 4 separate,
headlessly-buildable Rhino plugins. Decided 2026-07-31, parked — owner said
"hold on to it for now."

## The mechanism (live-verified against developer.rhino3d.com, 2026-07-15)

- Rhino 8 has **Script Editor Projects**: a `.rhproj` file maps scripts to
  plugin commands/Grasshopper components. Building it produces a real Rhino
  command plugin (`.rhp`), a Grasshopper plugin (`.gha`), an `.rui` toolbar,
  and a `.yak` package — in one shot.
- **Headless build, once the `.rhproj` exists:**
  `rhinocode project build MyTools.rhproj` — no running Rhino instance
  required. McNeel's docs describe this as meant for CI/CD build scripts.
- **Creating the initial `.rhproj` is GUI-only** (`File > Create Project` in
  Script Editor, drag scripts in via `+`). The exact file schema was never
  confirmed in docs, so this step can't be scripted blind — needs one pass
  in the Script Editor per plugin.
- **Hard constraint:** `rhinocode` ships inside a real Rhino 8.11+ install
  (Windows: `%PROGRAMFILES%\Rhino 8\System` on PATH; Mac: inside the app
  bundle). Any cloud/headless dev environment without Rhino installed can't
  run this step — it has to happen on a machine with Rhino (e.g. via Remote
  Control into a Windows PC).

## Plan

1. **One-time setup per plugin, in Script Editor on a Rhino-installed
   machine:**
   - `File > Create Project` → name it (e.g. `BrixCncParts.rhproj`), set
     name/version/authors/description (required manifest fields) and
     url/keywords/icon (recommended).
   - Drag in that folder's scripts, assigning each to a command (`.rhp`
     side) and/or Grasshopper component (`.gha` side) as appropriate.
   - Save the `.rhproj` into that BRIX folder in this repo (e.g.
     `projects/BRIX CNC PARTS/BrixCncParts.rhproj`) so it's version
     controlled with the scripts it references.
   - Repeat for the other 3 folders.

2. **Headless rebuild going forward, from a terminal on the Rhino machine:**
   ```
   rhinocode project build "projects/BRIX CNC PARTS/BrixCncParts.rhproj"
   rhinocode project build "projects/BRIX DRAFTING/BrixDrafting.rhproj"
   rhinocode project build "projects/BRIX JOINERY/BrixJoinery.rhproj"
   rhinocode project build "projects/BRIX MODELING/BrixModeling.rhproj"
   ```
   Each produces `.rhp`/`.gha`/`.rui`/`.yak` next to the `.rhproj`. No Rhino
   GUI needs to be open for this. Once all 4 `.rhproj` files exist, these
   four calls can be wrapped into a single `.bat`/PowerShell script for
   one-click rebuilds.

3. **Open item, unresolved:** the `.rhproj` file's exact format
   (XML/JSON/other) was never confirmed live — plan on the GUI pass above
   rather than trying to hand-author or generate `.rhproj` files
   programmatically.

## Verification (once picked back up)

- After step 1: confirm the `.rhproj` exists and Script Editor shows all
  scripts in that folder assigned to commands/components.
- After step 2: confirm `rhinocode project build` exits 0 and produces the
  `.yak`/`.rhp`/`.gha` files; install the `.yak` via Rhino's Package Manager
  on a test machine and confirm the commands actually run.
