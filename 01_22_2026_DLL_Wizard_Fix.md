## Problem Description
When attempting to "Attach to a V18" TIA Portal instance, the application consistently forces the user to go through the DLL Wizard, even after a DLL has been successfully selected and accepted. This behavior indicates that the chosen DLL path is not being persistently stored or correctly retrieved by the application, leading to an infinite loop where the wizard is repeatedly launched.

## Plan to Fix
The core issue is a lack of persistence for the user-selected DLL path. The solution will involve identifying where configuration settings are stored, modifying the DLL Wizard's completion logic to save the selected path, and adjusting the "Attach to V18" process to first check for a saved path before launching the wizard.

### Itemized Checklist of Planned Changes

1.  **Investigate DLL Wizard Flow:**
    *   [ ] Examine `src/tia_tags_exporter/gui/dll_wizard_window.py` and `src/tia_tags_exporter/gui/wizard.py` to understand how the DLL selection is made and how the chosen path is communicated upon user acceptance.
2.  **Identify Configuration Storage Mechanism:**
    *   [ ] Review `src/tia_tags_exporter/config_store.py` and `src/tia_tags_exporter/settings.py` to identify the existing methods for persisting application settings, including functions for saving and loading configuration values.
3.  **Implement Persistent Storage for DLL Path:**
    *   [ ] Modify the relevant code (likely within `src/tia_tags_exporter/gui/wizard.py` or `src/tia_tags_exporter/gui/dll_wizard_window.py`, or the calling function in `src/tia_tags_exporter/app.py`) to save the user-selected DLL file path to the application's configuration store (`config_store.py` or `settings.py`) upon successful completion of the wizard.
4.  **Implement DLL Path Loading Logic:**
    *   [ ] In the section of the application responsible for initiating the "Attach to V18" process (e.g., `src/tia_tags_exporter/app.py`, `src/tia_tags_exporter/app_boot.py`, or `src/tia_tags_exporter/session.py`), add logic to attempt to load a previously saved DLL path from the configuration store *before* invoking the DLL Wizard.
5.  **Update Wizard Trigger Condition:**
    *   [ ] Adjust the conditional check that currently forces the DLL Wizard to run. This check should first verify if a valid DLL path is already present in the loaded configuration. The wizard should only be displayed if no valid, saved path is found.
6.  **Add Robustness (Optional but Recommended):**
    *   [ ] Implement a check to validate that the loaded DLL path still points to an existing and accessible file. If the file is missing or invalid, the wizard should be prompted again to allow the user to select a new DLL.