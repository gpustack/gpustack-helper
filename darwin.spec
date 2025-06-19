# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files
from gpustack_helper.tools import download, get_package_dir
import os
import sys

paths_to_insert = [
    os.path.join(get_package_dir('vox_box'), 'third_party/CosyVoice'),
    os.path.join(get_package_dir('vox_box'), 'third_party/dia'),
    os.path.join(get_package_dir('vox_box'), 'third_party/CosyVoice/third_party/Matcha-TTS'),
]

for path in paths_to_insert:
    sys.path.insert(0, path)

# 
version = os.getenv('GIT_VERSION', '0.99.0.0').removeprefix('v')
version_short = '.'.join(version.split('.')[0:3])
app_name = 'GPUStack'

datas = [
    (get_package_dir('gpustack.migrations'), './gpustack/migrations'),
    (get_package_dir('gpustack.ui'),'./gpustack/ui'),
    (get_package_dir('gpustack.assets'),'./gpustack/assets'),
    (get_package_dir('gpustack.third_party'),'./gpustack/third_party'),
    (os.path.join(get_package_dir('gpustack.detectors.fastfetch'),'*.jsonc'), './gpustack/detectors/fastfetch/'),
    ('./tray_icon.png', './'),
    *collect_data_files('inflect', include_py_files=True),
    *collect_data_files('typeguard', include_py_files=True),
    *collect_data_files('tn', include_py_files=True),
    *collect_data_files('itn', include_py_files=True),
    (os.path.join(get_package_dir('whisper'), 'assets'), './whisper/assets'),
]

# keep it for testing. Will be removed if ci is added.
download()
binaries = []
if os.getenv('INSTALL_PREFIX', None) is None:
    binaries += [
        ('./openfst/build/lib/*', './'),
    ]

hiddenimports = [
    'tn', 'itn', '_pywrapfst'
]

aiosqlite = collect_all('aiosqlite')
datas += aiosqlite[0]; binaries += aiosqlite[1]; hiddenimports += aiosqlite[2]
cosyvoice = collect_all('cosyvoice')
datas += cosyvoice[0]; binaries += cosyvoice[1]; hiddenimports += cosyvoice[2]
matcha = collect_all('matcha')
datas += matcha[0]; binaries += matcha[1]; hiddenimports += matcha[2]
dia = collect_all('dia')
datas += dia[0]; binaries += dia[1]; hiddenimports += dia[2]
pynini = collect_all('pynini')
datas += pynini[0]; binaries += pynini[1]; hiddenimports += pynini[2]


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
    codesign_identity=None,
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
    codesign_identity=None,
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
    codesign_identity=None,
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
