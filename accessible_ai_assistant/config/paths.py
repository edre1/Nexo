"""Portable development paths and per-user paths for the installed edition."""
import os
from pathlib import Path
import sys


RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DATA_ROOT = (
    Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "AsistenteAccesibleWindows"
    if getattr(sys, "frozen", False) else RESOURCE_ROOT
)
