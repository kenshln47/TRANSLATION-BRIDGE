# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['chat_bridge.py'],
    pathex=[],
    binaries=[],
    datas=[('assets\\logo.png', 'assets')],
    hiddenimports=['customtkinter', 'PIL', 'pystray', 'chat_bridge', 'chat_bridge.app', 'chat_bridge.translator', 'chat_bridge.config', 'chat_bridge.hotkey', 'chat_bridge.tray', 'chat_bridge.constants', 'chat_bridge.ui', 'chat_bridge.ui.theme', 'chat_bridge.ui.setup_screen', 'chat_bridge.ui.main_screen', 'chat_bridge.ui.settings', 'chat_bridge.ui.toast', 'chat_bridge.ui.history'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['keyboard', 'numpy', 'pandas', 'matplotlib', 'scipy', 'IPython', 'notebook', 'pytest', 'unittest', 'doctest', 'pdb', 'tkinter.test', 'lib2to3', 'xmlrpc', 'pydoc'],
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
    icon=['assets\\icon.ico'],
)
