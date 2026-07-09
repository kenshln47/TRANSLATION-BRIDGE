# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
from PIL import Image

# icon.ico is intentionally generated into the ignored build directory.  This
# keeps a clean clone buildable without relying on an untracked binary asset.
build_dir = Path('build')
build_dir.mkdir(exist_ok=True)
generated_icon = build_dir / 'translation-bridge.ico'
with Image.open('assets/logo.png') as image:
    image.save(generated_icon, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

datas = [('assets/logo.png', 'assets'), (str(generated_icon), 'assets')]
binaries = []
hiddenimports = ['PIL', 'chat_bridge']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('darkdetect')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pystray')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['chat_bridge.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'pandas', 'matplotlib', 'scipy', 'pytest'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    name='Translation Bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(generated_icon)],
)
