import os
import tkinter as tk

# The .ico icon lives at <repo>/assets/u327as.ico regardless of the current working directory.
_ICON_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'u327as.ico')


def set_window_icon(window):
    """Apply the app icon, ignoring platforms where Tk can't load .ico files (e.g. Linux)."""
    try:
        window.wm_iconbitmap(_ICON_PATH)
    except tk.TclError:
        pass
