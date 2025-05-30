# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from importlib.resources import files
from importlib.abc import Traversable
import os

app_name = 'GPUStack'

def get_package_dir(package_name: str) -> str:
    """获取包的目录路径（兼容开发模式、PyInstaller 和 zip 包）"""
    pkg_path: Traversable = files(package_name)
    if hasattr(pkg_path, '_paths'):
        # 如果是开发模式或PyInstaller打包的目录
        return pkg_path._paths[0]
    return pkg_path

datas = [
  (get_package_dir('gpustack.migrations'), './gpustack/migrations'),
  (get_package_dir('gpustack.ui'),'./gpustack/ui'),
  (get_package_dir('gpustack.assets'),'./gpustack/assets'),
  (get_package_dir('gpustack.third_party'),'./gpustack/third_party'),
  (os.path.join(get_package_dir('gpustack.detectors.fastfetch'),'*.jsonc'), './gpustack/detectors/fastfetch/'),
  ('./tray_icon.png', './'),
]

binaries = []
hiddenimports = []
# tmp_ret = collect_all('aiosqlite', 'gpustack')
tmp_ret = collect_all('aiosqlite')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


helper = Analysis(
    ['gpustackhelper/main.py'],
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

gpustack = Analysis(
    [os.path.join(get_package_dir('gpustack'),'main.py')],
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

coll = COLLECT(
    helper_exe,
    gpustack_exe,
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
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0',
        'NSHumanReadableCopyright': 'Copyright © 2025 Seal, Inc.',
        'LSMinimumSystemVersion': '14.0',  # 最低系统要求
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'LSUIElement': True,
    },
)
