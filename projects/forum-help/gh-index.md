# Grasshopper category forum-help (2026-07-31 pass)

Second batch of `forum-help` scripts, this time from McNeel Discourse's
Grasshopper category (the Scripting-category batch is documented in
`forum-help/README.md`). Same rules: **not posted anywhere** — no
forum-posting capability exists yet, these are for the owner to review,
test, and post themselves.

| Folder | Forum thread | What it does | Confidence |
|---|---|---|---|
| `gh-batch-plot-pdf/` | [221262](https://discourse.mcneel.com/t/batch-plot-from-grasshopper-to-pdf/221262) | Plots each layout to a temp PDF via `-Print`, merges into one combined PDF with `pypdf`. | High on the merge/view logic (confirmed against real rhinoscriptsyntax/pypdf source); the exact `-Print` command-line tokens are unconfirmed and isolated to one template string — verify manually first. Needs `pip install pypdf`. |
| `gh-datatable-float-fix/` | [221305](https://discourse.mcneel.com/t/help-with-unknown-datatable-error/221305) | Standalone GHPython replacement for Lunchbox's DataTable→JSON chain, using plain Python `int()`/`float()` parsing instead of .NET `Parse`/`Convert` calls. | High confidence on root cause (matches a duplicate 2023 report of the identical symptom); not tested against the OP's actual `.gh` file. |
| `gh-louvre-facade/` | [221044](https://discourse.mcneel.com/t/custom-louvre-facades-script/221044) | Jittered/Poisson-disc void-sphere placement + Boolean difference, plus a bounding-box fabrication tiler. | General-purpose starting point, not a tuned match — **could not see the OP's reference image**, flagged explicitly. |
| `gh-tekla-rebar-curves/` | [221046](https://discourse.mcneel.com/t/rebar-in-tekla-doesnt-follow-control-polylines-from-gh/221046) | Pre-processing: normalizes curve direction + converts to NURBS before handing off to the Tekla connector. | Low-moderate — diagnostic mitigation, not a confirmed fix. The bug may be inside the third-party connector, which no upstream script can reach. |
| `gh-datatree-multi-object/` | [221292](https://discourse.mcneel.com/t/applying-the-same-gh-routine-across-several-objects/221292) | Explicit per-branch `DataTree` iteration for the mesh-projection/thickness workflow, replacing native graft/flatten. | Reconstructed template, not tested against the OP's real script/geometry — credits two existing partial forum replies. |

All 5 are cleanup-conservative: each README states plainly what's confirmed
(from the thread or live-fetched source) vs. carried over from training
knowledge and flagged unverified, since this session has no live Rhino or
Grasshopper to test against.
