"""
Mitigation attempt for RH-97159: custom Display Modes silently vanish from
the Display Mode list after rs.AddAlias()/rs.DeleteAlias() (or the raw
RhinoCommon Rhino.ApplicationSettings.CommandAliasList equivalents) are
called, once Rhino is restarted / the mode is checked in a later session.

Forum thread (read first, has the full repro and McNeel's response):
https://discourse.mcneel.com/t/add-remove-alias-silently-resets-display-mode-list-at-next-check/220727

Confirmed bug, logged by McNeel as RH-97159. Dale Fugier (McNeel) suggested
calling DisplayModeDescription.UpdateDisplayMode() to force a disk write of
the mode BEFORE touching the alias list. The OP tested that exact fix and
confirmed it does NOT prevent the loss - the mode still vanished on the
next separate script run. This is being treated here as an engine-level
persistence/ordering bug, not something fully fixable from script.

THIS SCRIPT IS A MITIGATION ATTEMPT, NOT A CONFIRMED FIX.
It has NOT been run against a live Rhino instance - I do not have one in
this environment. Everything below either:
  (a) uses API calls copied verbatim from the actual working code Dale
      Fugier and the OP posted in the thread (FindByName, DeleteDisplayMode,
      CopyDisplayMode, GetDisplayMode, UpdateDisplayMode - all confirmed via
      live thread content, not memory), or
  (b) is clearly marked as an untested hypothesis.

Engine/context: written for Python 3 via Rhino 8's ScriptEditor (F5).
Would also run under RunPythonScript's IronPython 2 engine as-is (no
non-ASCII characters, no f-strings used), but that hasn't been separately
verified either - if you must run it via RunPythonScript, test the print
output encoding first.

WHAT THIS SCRIPT DOES NOT DO
-----------------------------
It does not "fix" RH-97159. The OP already showed that persisting the
display mode BEFORE the alias operation (Dale's suggested order) does not
survive to the next session. The only untested variant left available from
script is the reverse order: touch the alias list FIRST, create/persist the
display mode LAST, so the display-mode disk write is not sitting underneath
whatever settings reload the alias mutation triggers. This is a plausible
mitigation based on the failure pattern described in the thread (an alias
change appears to trigger a settings reload that reverts display modes to a
stale on-disk snapshot) - but nobody in the thread tested this ordering, so
treat it as "worth trying," not "proven."

A second piece here is a repair/verify function you can run in a later,
separate script execution to detect the loss and recreate the mode from a
named source mode (e.g. "Shaded"). Note this can only recreate a *fresh
copy* of the source mode under the same name - it CANNOT restore any
customization (colors, shading settings, etc.) you made to the mode after
copying it, unless you separately captured those settings yourself. Rhino's
DisplayModeDescription class does have ExportToFile/ImportFromFile methods
for round-tripping a mode to an .ini file, which would solve that
customization-loss problem - but I could not get a live, authoritative look
at their exact signatures in this session (API doc pages are JS-rendered
and returned no usable content; GitHub code search required a login), so
they are intentionally NOT used here. See the README for how to wire that
in yourself once you've confirmed the signature against Rhino's own
help(Rhino.Display.DisplayModeDescription.ExportToFile) output.
"""

import Rhino
import rhinoscriptsyntax as rs


def create_display_mode_after_aliases(probe_name, source_mode_name, alias_name, alias_command):
    """
    Mitigation attempt: perform the alias add/delete FIRST, then create and
    persist the display mode LAST, on the theory (from the thread's failure
    pattern) that the alias mutation triggers a settings reload/rewrite that
    clobbers display modes present in memory at the time it fires. Doing the
    display-mode creation afterward means there is no later alias-triggered
    reload left in this script run to clobber it.

    This does NOT guarantee survival across a full Rhino restart, since any
    OTHER later alias change (by this script, another script, or the user
    manually adding an alias) could still trigger the same reload and wipe
    the mode again. It only removes the specific failure mode demonstrated
    in the thread's repro, where the alias change happens in the same script
    run as the mode's creation.

    Returns the new display mode's Guid, or None if the source mode wasn't
    found.
    """
    # Clean up any stale probe mode from a previous test run.
    existing = Rhino.Display.DisplayModeDescription.FindByName(probe_name)
    if existing:
        Rhino.Display.DisplayModeDescription.DeleteDisplayMode(existing.Id)

    # --- Alias operations FIRST ---
    rs.AddAlias(alias_name, alias_command)
    rs.DeleteAlias(alias_name)

    # --- Display mode creation LAST ---
    source = Rhino.Display.DisplayModeDescription.FindByName(source_mode_name)
    if source is None:
        print("Source display mode '{0}' not found - aborting.".format(source_mode_name))
        return None

    probe_id = Rhino.Display.DisplayModeDescription.CopyDisplayMode(source.Id, probe_name)

    # Force the disk write, same call Dale suggested - harmless to include
    # even though the OP's test showed it doesn't help when done BEFORE the
    # alias operation. Doing it here, as the last operation in the script,
    # is the untested part of this mitigation.
    probe = Rhino.Display.DisplayModeDescription.GetDisplayMode(probe_id)
    Rhino.Display.DisplayModeDescription.UpdateDisplayMode(probe)

    present = Rhino.Display.DisplayModeDescription.FindByName(probe_name) is not None
    print("Created '{0}': {1}".format(probe_name, probe_id))
    print("Present at end of this script: {0}".format(present))
    print("Re-check with verify_probe('{0}') in a SEPARATE later script run".format(probe_name))
    print("to see whether it actually survived - that's the only real test.")

    return probe_id


def verify_probe(probe_name):
    """
    Run this in a separate script execution (or after restarting Rhino) to
    check whether a previously created display mode survived. This is the
    only way to actually confirm whether a mitigation attempt worked - the
    bug does not manifest within the same script run.
    """
    present = Rhino.Display.DisplayModeDescription.FindByName(probe_name) is not None
    print("'{0}' present: {1}".format(probe_name, present))
    return present


def repair_if_missing(probe_name, source_mode_name):
    """
    Best-effort repair: if probe_name is missing, recreate it fresh from
    source_mode_name.

    LIMITATION (be clear with the user about this): this only recreates an
    unmodified COPY of source_mode_name under probe_name. If the original
    probe had been customized after creation (colors, shading options,
    etc.), those customizations are gone and are NOT restored by this
    function - there is no capture of prior state here, only a same-named
    stand-in. If you need real customization survival, export the mode to
    an .ini file immediately after every edit (see README) and have this
    function import from that .ini instead of copying from source_mode_name
    - once you've verified the Export/ImportFromFile signatures yourself.
    """
    if Rhino.Display.DisplayModeDescription.FindByName(probe_name) is not None:
        print("'{0}' still present - no repair needed.".format(probe_name))
        return

    source = Rhino.Display.DisplayModeDescription.FindByName(source_mode_name)
    if source is None:
        print("Cannot repair: source mode '{0}' not found either.".format(source_mode_name))
        return

    new_id = Rhino.Display.DisplayModeDescription.CopyDisplayMode(source.Id, probe_name)
    new_mode = Rhino.Display.DisplayModeDescription.GetDisplayMode(new_id)
    Rhino.Display.DisplayModeDescription.UpdateDisplayMode(new_mode)
    print("Repaired '{0}' as a fresh copy of '{1}' ({2}).".format(probe_name, source_mode_name, new_id))
    print("Any customization made to the original mode before it vanished is NOT restored.")


if __name__ == "__main__":
    # Example run - adjust names as needed. This exercises the reordered
    # mitigation once; you must run verify_probe() in a SEPARATE later
    # script execution (or after a Rhino restart) to know if it worked.
    create_display_mode_after_aliases(
        probe_name="ZZZ_REPRO_PROBE",
        source_mode_name="Shaded",
        alias_name="ZZZ_REPRO_ALIAS",
        alias_command="_Line",
    )
