# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files
from gpustack_helper.tools import download, get_package_dir, download_dac
import os
import sys

paths_to_insert = [
    os.path.join(get_package_dir('vox_box'), 'third_party/CosyVoice'),
    os.path.join(get_package_dir('vox_box'), 'third_party/dia'),
    os.path.join(
        get_package_dir('vox_box'), 'third_party/CosyVoice/third_party/Matcha-TTS'
    ),
]

for path in paths_to_insert:
    sys.path.insert(0, path)

#
version = os.getenv('GIT_VERSION', '0.99.0.0').removeprefix('v')
version_short = '.'.join(version.split('.')[0:3])
app_name = 'GPUStack'

os.makedirs('./build', exist_ok=True)
dac_path = download_dac('./build')

datas = [
    (get_package_dir('gpustack.migrations'), './gpustack/migrations'),
    (get_package_dir('gpustack.ui'), './gpustack/ui'),
    (get_package_dir('gpustack.assets'), './gpustack/assets'),
    (get_package_dir('gpustack.third_party'), './gpustack/third_party'),
    (
        os.path.join(get_package_dir('gpustack.detectors.fastfetch'), '*.jsonc'),
        './gpustack/detectors/fastfetch/',
    ),
    ('./tray_icon.png', './'),
    *collect_data_files('inflect', include_py_files=True),
    *collect_data_files('typeguard', include_py_files=True),
    *collect_data_files('tn', include_py_files=True),
    *collect_data_files('itn', include_py_files=True),
    *collect_data_files('audiotools'),
    (os.path.join(get_package_dir('whisper'), 'assets'), './whisper/assets'),
    (dac_path, "./"),
    (
        os.path.join(get_package_dir('vox_box.backends.tts'), 'cosyvoice_spk2info.pt'),
        './vox_box/backends/tts/',
    ),
    ("./translations/*.qm", "./translations"),
]

download()
binaries = []
hiddenimports = []

for pkg in [
    'aiosqlite',
    'asyncmy',
    'asyncpg',
    'cosyvoice',
    'matcha',
    'dia',
    'dac',
    'transformers',
]:
    pkg_datas = collect_all(pkg)
    datas += pkg_datas[0]
    binaries += pkg_datas[1]
    hiddenimports += pkg_datas[2]
