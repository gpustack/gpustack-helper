# -*- mode: python ; coding: utf-8 -*-
import os
from pyinstaller_common import (
    datas, 
    binaries, 
    hiddenimports, 
    app_name,
    version,
    version_short,
)
from gpustack_helper.download_nssm import download_nssm, NSSM_VERSION


datas += [
  (f'./build/{NSSM_VERSION}/win64/nssm.exe', './'),
]

# download nssm to ${pwd}/build dir
download_nssm(os.path.join(os.getcwd(), 'build'))


gpustack = Analysis(
    ['gpustack_helper\\binary_entrypoint.py'],
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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['GPUStack.ico'],
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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['GPUStack.ico'],
)

helper = Analysis(
    ['gpustack_helper\\main.py'],
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
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['GPUStack.ico'],
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
