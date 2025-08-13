# MahjongGame.spec
# Build:  py -m PyInstaller MahjongGame.spec --noconfirm --clean

from pathlib import Path
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import collect_submodules

proj_dir = Path.cwd().resolve()

hiddenimports = []
try:
    hiddenimports += collect_submodules('pygame')
except Exception:
    pass

a = Analysis(
    ['main.py'],
    pathex=[str(proj_dir)],
    binaries=[],
    datas=[],                 # <-- no Tree here
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    name='MahjongGame',
    icon=str(proj_dir / 'assets' / 'game.ico'),
    console=True,            # set False to hide console
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    Tree(str(proj_dir / 'assets'), prefix='assets'),  # <-- include whole assets/ tree
    strip=False, upx=False, name='MahjongGame'
)
