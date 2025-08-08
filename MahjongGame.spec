# MahjongGame.spec
from PyInstaller.utils.hooks import collect_submodules
import glob, os

# Include entire folders
datas = []
for folder in ["assets", "music", "sounds", "fonts"]:
    if os.path.isdir(folder):
        # (src, dest) pairs
        datas.append((folder, folder))

# If you use PySide/PyQt + Pygame, pull hidden imports (if needed)
hiddenimports = []
hiddenimports += collect_submodules("pygame")  # often not needed, but safe
# hiddenimports += collect_submodules("PyQt5")  # uncomment if Qt parts missed

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='MahjongGame',
    debug=False,
    strip=False,
    upx=True,          # if UPX installed; speeds load a bit
    console=False,     # no console window
    icon='assets/game.ico'  # optional
)
