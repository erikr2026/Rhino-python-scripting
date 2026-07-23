import System
import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs
import Eto.Forms as forms
import Eto.Drawing as drawing
import os
import re

def parse_ws_file(filepath):
    """
    Parses a Rhino worksession file (.ws or .rws) which is a binary file.
    Extracts all .3dm and .dwg reference file paths from the binary stream.
    """
    if not filepath or not os.path.exists(filepath):
        return []
        
    try:
        with open(filepath, 'rb') as f:
            binary_data = f.read()
    except Exception as e:
        print("Error reading worksession file: {0}".format(e))
        return []
        
    extracted_paths = []
    
    # Check UTF-16, UTF-16LE, UTF-8, and Latin-1 common encoding patterns inside binary data
    encodings = ['utf-16', 'utf-16le', 'utf-8', 'latin-1']
    for enc in encodings:
        try:
            text = binary_data.decode(enc, errors='ignore')
            # Scans for windows path indicators and relative/UNC paths ending in .3dm or .dwg
            matches = re.findall(r'([a-zA-Z]:\\[^\x00-\x1f"<>\|:\*\?]+\.(?:3dm|dwg)|[^\x00-\x1f"<>\|:\*\?\s]+\.(?:3dm|dwg))', text, re.IGNORECASE)
            for path in matches:
                clean_path = path.strip()
                # Clear residual binary headers and invalid path characters
                clean_path = "".join(ch for ch in clean_path if ord(ch) >= 32 and ch not in '"<>|*?')
                if clean_path and clean_path.lower().endswith(('.3dm', '.dwg')):
                    clean_path = os.path.normpath(clean_path)
                    if clean_path not in extracted_paths:
                        extracted_paths.append(clean_path)
        except Exception as e:
            pass
            
    return extracted_paths

def check_and_restore_worksessions():
    """
    Checks if there are stored worksession models in the document's user text,
    and programmatically re-attaches any that are missing.
    Matches paths relatively to the document's directory if the absolute path doesn't exist.
    """
    stored_paths_str = rs.GetDocumentUserText("WorksessionModelsManifest")
    if not stored_paths_str:
        return
        
    stored_paths = [p.strip() for p in stored_paths_str.split(",") if p.strip()]
    if not stored_paths:
        return
        
    current_paths = []
    try:
        ws = sc.doc.Worksession
        if ws:
            current_paths = [p.lower() for p in ws.ModelPaths if p]
    except Exception as e:
        pass
        
    missing_paths = []
    doc_path = sc.doc.Path
    doc_dir = os.path.dirname(doc_path) if doc_path else ""
    
    for sp in stored_paths:
        # Check absolute path
        if os.path.exists(sp):
            if sp.lower() not in current_paths:
                missing_paths.append(sp)
        else:
            # Check relative to active doc path
            if doc_dir:
                local_path = os.path.join(doc_dir, os.path.basename(sp))
                if os.path.exists(local_path):
                    if local_path.lower() not in current_paths:
                        missing_paths.append(local_path)
                        
    if missing_paths:
        print("Restoring missing worksession files from manifest record...")
        rs.EnableRedraw(False)
        try:
            for p in missing_paths:
                print("Attaching reference model: {0}".format(os.path.basename(p)))
                rs.Command('-Worksession Attach "{0}" _Enter'.format(p), echo=False)
        finally:
            rs.EnableRedraw(True)
            sc.doc.Views.Redraw()

def get_active_detail():
    """
    Finds and returns the active page view and detail view object.
    Supports Rhino 8 and 9 CPython engines reliably.
    Returns:
        tuple: (RhinoPageView, DetailViewObject) or (None, None)
    """
    view = sc.doc.Views.ActiveView
    if isinstance(view, Rhino.Display.RhinoPageView):
        # Retrieve the currently active entered detail viewport
        detail_obj = view.ActiveDetail
        if detail_obj and isinstance(detail_obj, Rhino.DocObjects.DetailViewObject):
            return view, detail_obj
            
        # Safe fallback matching legacy identifiers if active property is deferred
        active_detail_id = view.ActiveDetailId
        if active_detail_id and active_detail_id != System.Guid.Empty:
            found_obj = sc.doc.Objects.FindId(active_detail_id)
            if isinstance(found_obj, Rhino.DocObjects.DetailViewObject):
                return view, found_obj
    return None, None

def get_manifest(detail_obj):
    """
    Safely retrieves the stored manifest of GUIDs from the detail's user strings.
    """
    id_string = detail_obj.Attributes.GetUserString("FrozenManifest")
    if not id_string:
        return []
    try:
        return [System.Guid(s.strip()) for s in id_string.split(",") if s.strip()]
    except Exception as e:
        print("Error parsing stored manifest: {0}".format(e))
        return []

def save_manifest(detail_obj, target_ids):
    """
    Saves a clean comma-separated list of object GUIDs directly into the detail object attributes,
    and stores paths of active worksession reference models in the document user text.
    """
    id_string = ",".join([str(i) for i in target_ids])
    detail_obj.Attributes.SetUserString("FrozenManifest", id_string)
    detail_obj.CommitChanges()
    
    # Store currently attached worksession model paths
    try:
        ws = sc.doc.Worksession
        if ws:
            paths = list(ws.ModelPaths)
            active_path = sc.doc.Path
            ref_paths = []
            for p in paths:
                if p and p != active_path:
                    ref_paths.append(p)
            if ref_paths:
                rs.SetDocumentUserText("WorksessionModelsManifest", ",".join(ref_paths))
    except Exception as e:
        print("Error saving worksession models to manifest: {0}".format(e))
        
    sc.doc.Views.Redraw()

def _apply_manifest_core(detail_obj):
    """
    Core logic to hide/show objects in a specific detail based on its manifest.
    Assumes the detail is already the active viewport for macro fallbacks to work correctly.
    """
    detail_id = detail_obj.Id
    manifest_ids = set(get_manifest(detail_obj))
    if not manifest_ids:
        return False
        
    # Query all normal, locked, and worksession reference objects
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.ActiveObjects = True
    settings.ReferenceObjects = True
    settings.NormalObjects = True
    settings.LockedObjects = True
    
    all_objs = sc.doc.Objects.GetObjectList(settings)
    
    failed_to_hide = []
    failed_to_show = []
    
    for obj in all_objs:
        if obj.Id == detail_id:
            continue
            
        is_in_manifest = obj.Id in manifest_ids
        
        if is_in_manifest:
            # Ensure objects in the manifest are visible (remove detail hide overrides)
            if obj.Attributes.HasHideInDetailOverrideSet(detail_id):
                try:
                    obj.Attributes.RemoveHideInDetailOverride(detail_id)
                    obj.CommitChanges()
                except Exception as e:
                    failed_to_show.append(obj.Id)
        else:
            # Ensure other objects are hidden in this detail (add detail hide overrides)
            if not obj.Attributes.HasHideInDetailOverrideSet(detail_id):
                try:
                    obj.Attributes.AddHideInDetailOverride(detail_id)
                    obj.CommitChanges()
                except Exception as e:
                    failed_to_hide.append(obj.Id)
                    
    # Worksession reference object attributes are write-protected; fall back to command line safely.
    if failed_to_hide:
        sc.doc.Objects.UnselectAll()
        for obj_id in failed_to_hide:
            obj = sc.doc.Objects.FindId(obj_id)
            if obj:
                obj.Select(True)
        rs.Command("_HideInDetail", echo=False)
        sc.doc.Objects.UnselectAll()
        
    if failed_to_show:
        sc.doc.Objects.UnselectAll()
        for obj_id in failed_to_show:
            obj = sc.doc.Objects.FindId(obj_id)
            if obj:
                obj.Select(True)
        rs.Command("_ShowInDetail", echo=False)
        sc.doc.Objects.UnselectAll()
        
    return True

def apply_manifest(detail_obj):
    """
    Wrapper to hide all objects in a SINGLE active detail EXCEPT those stored in the manifest.
    """
    manifest_ids = set(get_manifest(detail_obj))
    if not manifest_ids:
        print("No manifest found or manifest is empty for this detail.")
        return False
        
    rs.EnableRedraw(False)
    try:
        undo_record = sc.doc.BeginUndoRecord("Apply Single Detail Manifest")
        _apply_manifest_core(detail_obj)
        sc.doc.Views.Redraw()
        print("Detail Manifest Applied: {0} manifest objects verified visible.".format(len(manifest_ids)))
        return True
    finally:
        if 'undo_record' in locals():
            sc.doc.EndUndoRecord(undo_record)
        rs.EnableRedraw(True)

def apply_all_manifests():
    """
    Iterates through all layouts, collecting details with assigned manifests,
    and applies them sequentially.
    """
    page_views = sc.doc.Views.GetPageViews()
    details_to_process = []
    
    for page in page_views:
        details = page.GetDetailViews()
        for d in details:
            if get_manifest(d):
                details_to_process.append((page, d))
                
    if not details_to_process:
        print("No details found with a saved manifest.")
        return False
        
    print("Found {0} details with manifests. Applying...".format(len(details_to_process)))
    original_view = sc.doc.Views.ActiveView
    
    # Track the originally active detail to seamlessly restore user state
    original_detail_id = None
    if isinstance(original_view, Rhino.Display.RhinoPageView):
        original_detail_id = original_view.ActiveDetailId
        
    rs.EnableRedraw(False)
    try:
        undo_record = sc.doc.BeginUndoRecord("Apply All Detail Manifests")
        count = 0
        
        for page, detail_obj in details_to_process:
            # Activate the layout page
            sc.doc.Views.ActiveView = page
            page.SetPageAsActive()
            
            # Activate the specific detail viewport to permit macro fallback functionality
            page.SetActiveDetail(detail_obj.Id)
            
            # Apply the visibility filters
            if _apply_manifest_core(detail_obj):
                count += 1
                
            # Explicitly exit the detail viewport back to the layout page space
            # This prevents details from getting stuck in an "active" (entered) state
            page.SetPageAsActive()
                
        print("Successfully applied manifests to {0} details.".format(count))
        return True
    except Exception as e:
        print("Error applying manifests: {0}".format(e))
        return False
    finally:
        # Restore original view context
        if original_view:
            sc.doc.Views.ActiveView = original_view
            if isinstance(original_view, Rhino.Display.RhinoPageView):
                original_view.SetPageAsActive()
                # Safely restore the previously entered detail if there was one
                if original_detail_id and original_detail_id != System.Guid.Empty:
                    try:
                        original_view.SetActiveDetail(original_detail_id)
                    except Exception:
                        pass
                
        if 'undo_record' in locals():
            sc.doc.EndUndoRecord(undo_record)
            
        rs.EnableRedraw(True)
        sc.doc.Views.Redraw()

def _show_all_in_detail(detail_obj):
    """Helper to temporarily remove all hide-in-detail overrides for a specific detail."""
    detail_id = detail_obj.Id
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.ActiveObjects = True
    settings.ReferenceObjects = True
    settings.NormalObjects = True
    settings.LockedObjects = True
    
    all_objs = sc.doc.Objects.GetObjectList(settings)
    
    rs.EnableRedraw(False)
    failed_to_show = []
    try:
        for obj in all_objs:
            if obj.Attributes.HasHideInDetailOverrideSet(detail_id):
                try:
                    obj.Attributes.RemoveHideInDetailOverride(detail_id)
                    obj.CommitChanges()
                except Exception:
                    failed_to_show.append(obj.Id)
                    
        if failed_to_show:
            sc.doc.Objects.UnselectAll()
            for obj_id in failed_to_show:
                obj = sc.doc.Objects.FindId(obj_id)
                if obj:
                    obj.Select(True)
            rs.Command("_ShowInDetail", echo=False)
            sc.doc.Objects.UnselectAll()
            
        sc.doc.Views.Redraw()
    finally:
        rs.EnableRedraw(True)

def clear_manifest(detail_obj):
    """
    Clears the stored manifest user string and restores detail visibility for all objects.
    """
    detail_id = detail_obj.Id
    
    detail_obj.Attributes.DeleteUserString("FrozenManifest")
    detail_obj.CommitChanges()
    
    try:
        rs.SetDocumentUserText("WorksessionModelsManifest", None)
    except Exception as e:
        pass
    
    try:
        undo_record = sc.doc.BeginUndoRecord("Clear Detail Manifest")
        _show_all_in_detail(detail_obj)
        print("Manifest cleared and object visibility restored in detail.")
        return True
    finally:
        if 'undo_record' in locals():
            sc.doc.EndUndoRecord(undo_record)

class DetailManifestDialog(forms.Form):
    """
    Modeless form interface allowing seamless viewport navigation (double-clicking) 
    and document modification synchronization.
    """
    def __init__(self):
        super(DetailManifestDialog, self).__init__()
        self.Title = "WS Detail Manifest Manager"
        self.ClientSize = drawing.Size(380, 350)
        self.Padding = drawing.Padding(12)
        
        # Instantiate UI controls without keyword arguments to satisfy PythonNet runtime behavior
        self.lbl_info = forms.Label()
        self.lbl_info.Text = "Double-click inside a Detail View to activate it. You can interact with Rhino freely."
        
        self.lbl_status = forms.Label()
        self.lbl_status.Text = "Status: No Detail active."
        self.lbl_status.Font = drawing.Font("Arial", 10, drawing.FontStyle.Bold)
        
        self.btn_refresh = forms.Button()
        self.btn_refresh.Text = "Refresh Active Detail"
        
        self.btn_load_ws = forms.Button()
        self.btn_load_ws.Text = "Load References from .WS / .RWS"
        
        self.btn_save = forms.Button()
        self.btn_save.Text = "Set / Overwrite Manifest"
        
        self.btn_apply = forms.Button()
        self.btn_apply.Text = "SINGLE DETAIL APPLY MANIFEST (HIDE OTHERS)"
        
        self.btn_apply_all = forms.Button()
        self.btn_apply_all.Text = "ALL DETAILS APPLY MANIFEST"
        
        self.btn_add = forms.Button()
        self.btn_add.Text = "Add Selected to Manifest"
        
        self.btn_remove = forms.Button()
        self.btn_remove.Text = "Remove Selected from Manifest"
        
        self.btn_clear = forms.Button()
        self.btn_clear.Text = "Clear / Reset Manifest"
        
        # UI Event bindings directly associated in class constructor
        self.btn_refresh.Click += self.on_refresh_click
        self.btn_load_ws.Click += self.on_load_ws_click
        self.btn_save.Click += self.on_save_click
        self.btn_apply.Click += self.on_apply_click
        self.btn_apply_all.Click += self.on_apply_all_click
        self.btn_add.Click += self.on_add_click
        self.btn_remove.Click += self.on_remove_click
        self.btn_clear.Click += self.on_clear_click
        
        # Use GotFocus and MouseEnter to guarantee focus renewal
        try:
            self.GotFocus += self.on_form_activated
        except Exception as e:
            pass
            
        try:
            self.MouseEnter += self.on_form_activated
        except Exception as e:
            pass
        
        # Layout definition using standard null-row insertions
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(6, 6)
        
        layout.Add(self.lbl_info)
        layout.Add(None)
        layout.Add(self.lbl_status)
        layout.Add(None)
        
        layout.Add(self.btn_refresh)
        layout.Add(self.btn_load_ws)
        layout.Add(self.btn_save)
        layout.Add(self.btn_apply)
        layout.Add(self.btn_apply_all)
        layout.Add(self.btn_add)
        layout.Add(self.btn_remove)
        layout.Add(self.btn_clear)
        
        self.Content = layout
        
        # Check/restore missing worksession files once on initialization
        try:
            check_and_restore_worksessions()
        except Exception as e:
            print("Error checking/restoring worksession files: {0}".format(e))
            
        self.update_ui_state()

    def update_ui_state(self):
        page_view, detail_obj = get_active_detail()
        
        # "Apply All" is universally enabled regardless of what detail is currently active
        self.btn_apply_all.Enabled = True
        
        if not detail_obj:
            self.lbl_status.Text = "Status: No active entered detail viewport."
            self.lbl_status.TextColor = drawing.Colors.Red
            self.btn_save.Enabled = False
            self.btn_add.Enabled = False
            self.btn_remove.Enabled = False
            self.btn_apply.Enabled = False
            self.btn_clear.Enabled = False
        else:
            title = detail_obj.DescriptiveTitle
            manifest = get_manifest(detail_obj)
            status_text = "Active Detail: {0}\nManifest Items Count: {1}".format(title, len(manifest))
            self.lbl_status.Text = status_text
            self.lbl_status.TextColor = drawing.Colors.Green
            
            self.btn_save.Enabled = True
            has_items = len(manifest) > 0
            self.btn_add.Enabled = True
            self.btn_remove.Enabled = has_items
            self.btn_apply.Enabled = has_items
            self.btn_clear.Enabled = has_items

    def on_form_activated(self, sender, e):
        self.update_ui_state()

    def on_refresh_click(self, sender, e):
        self.update_ui_state()
        
    def on_load_ws_click(self, sender, e):
        # Allow selecting worksession files
        filter_str = "Rhino Worksession (*.ws;*.rws)|*.ws;*.rws|All Files (*.*)|*.*"
        ws_file = rs.OpenFileName("Open Worksession File", filter_str)
        if not ws_file:
            return
            
        extracted = parse_ws_file(ws_file)
        if not extracted:
            print("No reference model files discovered inside the selected worksession file.")
            return
            
        print("Found {0} reference paths inside worksession file. Resolving...".format(len(extracted)))
        
        resolved = []
        ws_dir = os.path.dirname(ws_file)
        doc_dir = os.path.dirname(sc.doc.Path) if sc.doc.Path else ""
        
        for path in extracted:
            # 1. Try absolute path
            if os.path.exists(path):
                resolved.append(path)
                continue
            # 2. Try relative to the selected .ws/.rws file's directory
            p_ws_rel = os.path.abspath(os.path.join(ws_dir, path))
            if os.path.exists(p_ws_rel):
                resolved.append(p_ws_rel)
                continue
            p_ws_base = os.path.abspath(os.path.join(ws_dir, os.path.basename(path)))
            if os.path.exists(p_ws_base):
                resolved.append(p_ws_base)
                continue
            # 3. Try relative to active document path
            if doc_dir:
                p_doc_rel = os.path.abspath(os.path.join(doc_dir, path))
                if os.path.exists(p_doc_rel):
                    resolved.append(p_doc_rel)
                    continue
                p_doc_base = os.path.abspath(os.path.join(doc_dir, os.path.basename(path)))
                if os.path.exists(p_doc_base):
                    resolved.append(p_doc_base)
                    continue
            print("Could not locate reference path for: {0}".format(path))
            
        if resolved:
            # Attach all successfully resolved paths
            current_paths = []
            try:
                ws = sc.doc.Worksession
                if ws:
                    current_paths = [p.lower() for p in ws.ModelPaths if p]
            except Exception as e:
                pass
                
            to_attach = [p for p in resolved if p.lower() not in current_paths]
            if to_attach:
                rs.EnableRedraw(False)
                try:
                    for p in to_attach:
                        print("Attaching model: {0}".format(os.path.basename(p)))
                        rs.Command('-Worksession Attach "{0}" _Enter'.format(p), echo=False)
                finally:
                    rs.EnableRedraw(True)
                    sc.doc.Views.Redraw()
            
            # Save resolved references to document user text so they load automatically on document open
            rs.SetDocumentUserText("WorksessionModelsManifest", ",".join(resolved))
            print("Successfully loaded and registered {0} references from worksession file.".format(len(resolved)))
            self.update_ui_state()

    def on_save_click(self, sender, e):
        page_view, detail_obj = get_active_detail()
        if not detail_obj:
            return

        msg = "Select objects to KEEP visible in this detail (Manifest) [Enter/Space to finish]"
        target_ids = rs.GetObjects(msg, preselect=True)

        if not target_ids:
            return

        save_manifest(detail_obj, target_ids)
        _apply_manifest_core(detail_obj)
        sc.doc.Views.Redraw()

        self.update_ui_state()
        
    def on_add_click(self, sender, e):
        page_view, detail_obj = get_active_detail()
        if not detail_obj:
            return
            
        current_manifest = set(get_manifest(detail_obj))
        
        # Capture pre-selected objects to preserve selection workflow
        selected_ids = [obj.Id for obj in sc.doc.Objects.GetSelectedObjects(False, False)]
        
        # Temporarily show all objects in model space for this detail
        _show_all_in_detail(detail_obj)
        
        # Restore selection state after the visibility toggle clears it
        if selected_ids:
            sc.doc.Objects.UnselectAll()
            for obj_id in selected_ids:
                obj = sc.doc.Objects.FindId(obj_id)
                if obj:
                    obj.Select(True)
                    
        msg = "Select objects to ADD to the manifest [Enter/Space to finish]"
        new_ids = rs.GetObjects(msg, preselect=True)
        
        if not new_ids:
            # User cancelled or picked nothing; restore the previous visibility state
            if current_manifest:
                _apply_manifest_core(detail_obj)
                sc.doc.Views.Redraw()
            return
            
        updated = current_manifest.union([System.Guid(str(i)) for i in new_ids])
        save_manifest(detail_obj, list(updated))
        
        # Apply the updated manifest to re-hide non-manifest items
        _apply_manifest_core(detail_obj)
        sc.doc.Views.Redraw()
        
        self.update_ui_state()
        
    def on_remove_click(self, sender, e):
        page_view, detail_obj = get_active_detail()
        if not detail_obj:
            return
        current_manifest = get_manifest(detail_obj)
        if not current_manifest:
            return
        msg = "Select objects to REMOVE from the manifest [Enter/Space to finish]"
        remove_ids = rs.GetObjects(msg, preselect=True)
        if not remove_ids:
            return
        remove_set = set([System.Guid(str(i)) for i in remove_ids])
        updated = [i for i in current_manifest if i not in remove_set]
        save_manifest(detail_obj, updated)
        self.update_ui_state()
        
    def on_apply_click(self, sender, e):
        page_view, detail_obj = get_active_detail()
        if not detail_obj:
            return
        apply_manifest(detail_obj)
        self.update_ui_state()
        
    def on_apply_all_click(self, sender, e):
        apply_all_manifests()
        self.update_ui_state()
        
    def on_clear_click(self, sender, e):
        page_view, detail_obj = get_active_detail()
        if not detail_obj:
            return
        clear_manifest(detail_obj)
        self.update_ui_state()

def main():
    sc.doc = Rhino.RhinoDoc.ActiveDoc
    
    # Establish a persistent key for the modeless form in sc.sticky
    sticky_key = "WS_Detail_Manifest_Manager_Form"
    if sticky_key in sc.sticky:
        try:
            existing_form = sc.sticky[sticky_key]
            existing_form.BringToFront()
            existing_form.update_ui_state()
            return
        except Exception as e:
            # Clean up stale references if the window was force-closed or disposed
            sc.sticky.pop(sticky_key, None)
            
    form = DetailManifestDialog()
    
    # Store reference in sticky to protect against CPython garbage collection
    sc.sticky[sticky_key] = form
    
    # Safely clear the sticky key when the window is closed by the user
    def on_closed(sender, e):
        sc.sticky.pop(sticky_key, None)
    form.Closed += on_closed
    
    # Assign the parent owner window to keep the form floating on top of Rhino
    try:
        form.Owner = Rhino.UI.RhinoEtoApp.MainWindow
    except Exception as e:
        pass
        
    # Display the form modelessly without arguments
    form.Show()

if __name__ == "__main__":
    main()