# Alias/Display Mode persistence bug — mitigation attempt, not a fix

Forum thread: https://discourse.mcneel.com/t/add-remove-alias-silently-resets-display-mode-list-at-next-check/220727
(posted 2026-07-10). Confirmed bug, escalated by McNeel to internal ticket
**RH-97159**.

## The bug

Calling `rs.AddAlias()`/`rs.DeleteAlias()` (or the underlying
`Rhino.ApplicationSettings.CommandAliasList` calls) causes a newly-created
custom Display Mode to silently vanish from the Display Mode list — it's
only visible within the same Rhino session/script run, not the next one.
Dale Fugier (McNeel staff) suggested calling
`DisplayModeDescription.UpdateDisplayMode()` to force a disk write of the
mode *before* touching the alias list. The OP tested that exact fix and
confirmed **it does not work** — the mode still vanishes.

## Honest confidence level: low-to-moderate, unverified

This is a real engine-level persistence/ordering bug, not a scripting
mistake — a pure Python workaround may not be able to fully fix it. This
script is a **mitigation attempt**, not a confirmed fix:

- **What it tries:** reversing the operation order Dale suggested. Instead
  of persisting the display mode *then* touching aliases (which the OP
  showed fails), this does the alias add/delete *first*, then creates and
  persists the display mode *last* — on the theory that the alias mutation
  triggers a settings reload that clobbers whatever's in memory at the time
  it fires. Nobody in the thread tested this specific ordering, so it's
  "worth trying," not "proven."
- **What it explicitly does NOT do:** guarantee survival across a full
  Rhino restart if any *other* later alias change (by this script, another
  script, or the user manually) fires again — it only removes the specific
  same-script-run failure mode from the thread's repro.
- **The only real test:** run `create_display_mode_after_aliases(...)` in
  one script execution, then run `verify_probe(...)` in a **separate**,
  later script execution (or after restarting Rhino) — the bug doesn't
  manifest within a single run, so testing both halves in the same script
  would prove nothing.

## What's in the script

- `create_display_mode_after_aliases()` — the reordered mitigation attempt.
- `verify_probe()` — checks whether a previously created mode survived.
  Must be run in a separate script execution from the creation call.
- `repair_if_missing()` — best-effort repair: recreates a **fresh, unmodified
  copy** of a source mode if the probe went missing. This does **not**
  restore any customization (colors, shading settings) made to the mode
  after it was created — there's no capture of prior state here.

## Confirmed vs. unverified API calls

- `FindByName`, `DeleteDisplayMode`, `CopyDisplayMode`, `GetDisplayMode`,
  `UpdateDisplayMode` — all copied verbatim from real, working code Dale
  Fugier and the OP posted in the thread itself, not from training memory.
- `DisplayModeDescription.ExportToFile`/`ImportFromFile` — these exist and
  would solve the "customization is lost on repair" limitation above (by
  round-tripping the mode to an `.ini` file instead of copying from a
  source mode), but their exact signatures could not be confirmed live this
  session (developer.rhino3d.com's API docs are a JS-rendered SPA that
  returned no usable content; GitHub code search required login). They are
  **intentionally not used** in this script. If you want that capability,
  run `help(Rhino.Display.DisplayModeDescription.ExportToFile)` inside
  Rhino's own Python console first to confirm the real signature, then wire
  it into `repair_if_missing()`.

## Bottom line

If this mitigation doesn't hold up in real testing, the honest next step is
reporting back to the thread/RH-97159 that the reordering doesn't help
either — that's still useful information for McNeel and the OP, even though
it's not the "problem solved" outcome. This is McNeel's bug to fix at the
engine level; script-side mitigation has real limits here.
