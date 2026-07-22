# rhino-python-scripting

General-purpose home for Rhino/Grasshopper Python scripts and utilities that
don't warrant their own repo. Larger standalone projects (e.g. HULL-TEST-1,
Blackbird) still live in their own repos — this one is for smaller scripts,
one-offs, and shared utilities.

## Convention

Each project or script gets its own folder under `projects/`:

```
projects/
  <project-name>/
    README.md      # what it does, how to run it
    ...             # scripts, .ghx files, etc.
```

Copy `projects/_template/` as a starting point for a new project.

## Environment

Rhino 8 + VS Code + McNeel's `rhino-stubs` for autocomplete. See the owner's
Vincent memory (`memory/projects/rhino-python-scripting.md`) for the full
environment setup writeup.
