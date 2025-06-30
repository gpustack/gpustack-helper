# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all
from pyinstaller_common import (
    datas, 
    binaries, 
    hiddenimports, 
    app_name,
    version,
    version_short,
)

if os.getenv('INSTALL_PREFIX', None) is None:
    binaries += [
        ('./openfst/build/lib/*', './'),
    ]
# use by cosyvioce/vox_box
hiddenimports += [
    'tn', 'itn', '_pywrapfst'
]
pkg_datas = collect_all('pynini')
datas += pkg_datas[0]
binaries += pkg_datas[1]
hiddenimports += pkg_datas[2]

identity = os.getenv('CODESIGN_IDENTITY', None)

gpustack = Analysis(
    ['gpustack_helper/binary_entrypoint.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
gpustack_pyz = PYZ(gpustack.pure)
gpustack_exe = EXE(
    gpustack_pyz,
    gpustack.scripts,
    [],
    exclude_binaries=True,
    name=app_name.lower(),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=identity,
    entitlements_file=None,
)

vox_box_exe = EXE(
    gpustack_pyz,
    gpustack.scripts,
    [],
    exclude_binaries=True,
    name='vox-box',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=identity,
    entitlements_file=None,
)


helper = Analysis(
    ['gpustack_helper/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

helper_pyz = PYZ(helper.pure)

helper_exe = EXE(
    helper_pyz,
    helper.scripts,
    [],
    exclude_binaries=True,
    name=f'{app_name}helper'.lower(),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=identity,
    entitlements_file=None,
)

coll = COLLECT(
    helper_exe,
    gpustack_exe,
    vox_box_exe,
    helper.binaries,
    helper.datas,
    gpustack.binaries,
    gpustack.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)

# 创建 .app 包
app = BUNDLE(
    coll,  # 将 coll 放入 BUNDLE 中
    name=f'{app_name}.app',
    icon=f'./{app_name}.icns',  # 图标文件路径
    bundle_identifier='ai.gpustack.gpustack',  # 应用标识符
    info_plist={
        'CFBundleName': app_name,
        'CFBundleDisplayName': app_name,
        'CFBundleVersion': version,
        'CFBundleShortVersionString': version_short,
        'NSHumanReadableCopyright': 'Copyright © 2025 Seal, Inc.',
        'LSMinimumSystemVersion': '14.0',  # 最低系统要求
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'LSUIElement': True,
    },
)
