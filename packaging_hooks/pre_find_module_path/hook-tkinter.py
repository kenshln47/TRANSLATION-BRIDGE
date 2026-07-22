"""Keep tkinter discoverable when PyInstaller cannot initialize host Tcl.

The project bundles Tcl/Tk data explicitly in Translation Bridge.spec, so a
failed host-side Tcl probe must not cause PyInstaller to exclude tkinter's
Python modules from the frozen application.
"""


def pre_find_module_path(hook_api):
    """Leave tkinter's standard-library search path unchanged."""

