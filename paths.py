# paths.py
from pathlib import Path
import sys

def _base_path() -> Path:
    # PyInstaller onefile extracts to _MEIPASS; onedir uses the exe's folder.
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR = _base_path()
ASSETS_DIR = BASE_DIR / "assets"

def asset(*parts) -> Path:
    """Join parts under assets/ and return a Path."""
    return ASSETS_DIR.joinpath(*parts)
