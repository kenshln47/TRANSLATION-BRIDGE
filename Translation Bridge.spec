# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)
from pathlib import Path
from PIL import Image
import importlib.util
import os
import runpy
import sys

one_dir = os.environ.get('TB_BUILD_ONEDIR') == '1'

# icon.ico is intentionally generated into the ignored build directory.  This
# keeps a clean clone buildable without relying on an untracked binary asset.
build_dir = Path('build')
build_dir.mkdir(exist_ok=True)
generated_icon = build_dir / 'translation-bridge.ico'
with Image.open('assets/logo.png') as image:
    image.save(
        generated_icon,
        format='ICO',
        sizes=[
            (16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
            (48, 48), (64, 64), (128, 128), (256, 256),
        ],
    )

# Both the app and Windows file properties read the same version module.
version_data = runpy.run_path('chat_bridge/version.py')
app_version = version_data['__version__']
version_tuple = tuple(version_data['VERSION_TUPLE'])
generated_version = build_dir / 'translation-bridge-version.txt'
generated_version.write_text(
    """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple}, prodvers={version_tuple}, mask=0x3f,
    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'Translation Bridge'),
    StringStruct('FileDescription', 'Fast in-game chat translation'),
    StringStruct('FileVersion', '{app_version}'),
    StringStruct('InternalName', 'Translation Bridge'),
    StringStruct('LegalCopyright', 'Copyright (c) 2026 Translation Bridge'),
    StringStruct('OriginalFilename', 'Translation Bridge.exe'),
    StringStruct('ProductName', 'Translation Bridge'),
    StringStruct('ProductVersion', '{app_version}')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)""".format(version_tuple=version_tuple, app_version=app_version),
    encoding='utf-8',
)

datas = [('assets/logo.png', 'assets'), (str(generated_icon), 'assets')]
binaries = []
hiddenimports = ['PIL', 'chat_bridge', '_tkinter']
hiddenimports += collect_submodules('tkinter')

# The portable Python runtime used by the local build has Tcl/Tk installed,
# but PyInstaller cannot discover its script libraries reliably.  tkinter's
# frozen runtime hook requires these exact destination names beside the
# unpacked application; without them the EXE fails before our code can run.
tcl_root = Path(sys.base_prefix) / 'tcl'
tcl_data_dir = tcl_root / 'tcl8.6'
tk_data_dir = tcl_root / 'tk8.6'
for source_dir, destination in (
    (tcl_data_dir, '_tcl_data'),
    (tk_data_dir, '_tk_data'),
):
    if not source_dir.is_dir():
        raise SystemExit(f'Missing {destination} source directory: {source_dir}')
    datas.append((str(source_dir), destination))

tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('darkdetect')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pystray')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# OCR is optional during development, but a release bundles every downloaded
# RapidOCR model plus ONNX Runtime's native DLLs. Avoid collect_all(onnxruntime):
# its developer/quantization tools are not used and would inflate the EXE.
if importlib.util.find_spec('rapidocr') is not None:
    rapid_spec = importlib.util.find_spec('rapidocr')
    rapid_dir = Path(next(iter(rapid_spec.submodule_search_locations)))
    # Include configuration/font data but only the runtime models we support;
    # collect_all() also bundled unused PP-OCRv6 and optional Torch/TensorRT
    # backends, inflating startup extraction and the release by tens of MB.
    datas += collect_data_files('rapidocr', excludes=['models/*', 'models/**'])
    required_models = [
        'ch_PP-OCRv5_det_mobile.onnx',
        'ch_ppocr_mobile_v2.0_cls_mobile.onnx',
        'latin_PP-OCRv5_rec_mobile.onnx',
        'arabic_PP-OCRv5_rec_mobile.onnx',
        'cyrillic_PP-OCRv5_rec_mobile.onnx',
        'devanagari_PP-OCRv5_rec_mobile.onnx',
        'japan_PP-OCRv4_rec_mobile.onnx',
        'korean_PP-OCRv5_rec_mobile.onnx',
        'ch_PP-OCRv5_rec_mobile.onnx',
    ]
    for model_name in required_models:
        model_path = rapid_dir / 'models' / model_name
        if not model_path.is_file():
            raise SystemExit(
                f'Missing OCR model {model_name}; run scripts/prepare_ocr_models.py first.'
            )
        datas.append((str(model_path), 'rapidocr/models'))
    hiddenimports += [
        'rapidocr.inference_engine.onnxruntime',
        'rapidocr.inference_engine.onnxruntime.main',
    ]
if importlib.util.find_spec('onnxruntime') is not None:
    binaries += collect_dynamic_libs('onnxruntime')
    hiddenimports.append('onnxruntime')


a = Analysis(
    ['chat_bridge.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['packaging_hooks'],
    hooksconfig={},
    runtime_hooks=[],
    # NumPy is required by the bundled OCR pipeline. Keep unrelated scientific
    # stacks excluded so the one-file release does not grow accidentally.
    excludes=[
        'pandas', 'matplotlib', 'scipy', 'pytest',
        'rapidocr.inference_engine.mnn',
        'rapidocr.inference_engine.openvino',
        'rapidocr.inference_engine.paddle',
        'rapidocr.inference_engine.pytorch',
        'rapidocr.inference_engine.tensorrt',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [] if one_dir else a.binaries,
    [] if one_dir else a.datas,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    name='Translation Bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Maintainers can request a console build for diagnosing frozen-only
    # import failures without editing the release configuration.
    console=os.environ.get('TB_BUILD_CONSOLE') == '1',
    exclude_binaries=one_dir,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(generated_icon)],
    version=str(generated_version),
)

if one_dir:
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Translation Bridge',
    )
