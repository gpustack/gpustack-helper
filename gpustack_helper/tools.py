import os
import shutil
import re
import stat
from typing import Dict
from gpustack.worker.tools_manager import ToolsManager, BUILTIN_LLAMA_BOX_VERSION
from gpustack.utils.platform import system, arch, get_executable_suffix as exe, DeviceTypeEnum
from importlib.resources import files

LLAMA_BOX_VERSION = os.getenv("LLAMA_BOX_VERSION", BUILTIN_LLAMA_BOX_VERSION)
LLAMA_BOX_DOWNLOAD_REPO = os.getenv("LLAMA_BOX_DOWNLOAD_REPO", "gpustack/llama-box")
PREFERRED_BASE_URL = os.getenv("PREFERRED_BASE_URL", None)

def get_package_dir(package_name: str) -> str:
    paths = package_name.rsplit('.', 1)
    if len(paths) == 1:
        return str(files(package_name))
    package, subpackage = paths
    return str(files(package).joinpath(subpackage))


def get_toolkit_name(device: str) -> str:
    # Get the toolkit based on the device type.
    device_toolkit_mapper = {
        "cuda": DeviceTypeEnum.CUDA.value,
        "cann": DeviceTypeEnum.NPU.value,
        "metal": DeviceTypeEnum.MPS.value,
        "hip": DeviceTypeEnum.ROCM.value,
        "musa": DeviceTypeEnum.MUSA.value,
        "dtk": DeviceTypeEnum.DCU.value,
    }

    if device in device_toolkit_mapper:
        return device_toolkit_mapper[device]
    else:
        return device


def verify_file_checksum(file_path: str, expected_checksum: str) -> bool:
    """Verify the checksum of a file against an expected value."""
    import hashlib

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest() == expected_checksum

def download_llama_box(manager: ToolsManager):
    version = LLAMA_BOX_VERSION
    version_url_prefix = f'{LLAMA_BOX_DOWNLOAD_REPO}/releases/download/{version}'
    target_dir = manager.third_party_bin_path / "llama-box"
    llama_box_tmp_dir = target_dir / "tmp-llama-box"
    if os.path.exists(llama_box_tmp_dir):
        shutil.rmtree(llama_box_tmp_dir)
    os.makedirs(llama_box_tmp_dir, exist_ok=True)
    url_path = f"{version_url_prefix}/sha256sum.txt"
    checksum_file_path = llama_box_tmp_dir / "sha256sum.txt"
    files_checksum: Dict[str,str] = dict()
    target_prefix = f"llama-box-{system()}-{arch()}-"
    try:
        manager._download_file(url_path, checksum_file_path, base_url=PREFERRED_BASE_URL)
        with open(checksum_file_path, "r") as f:
            for line in f:
                pair = re.split(r'\s+', line.strip(), 1)
                if len(pair) != 2:
                    continue
                if not pair[1].startswith(target_prefix):
                    continue
                files_checksum[pair[1]]=pair[0]
                
    except Exception as e:
        raise RuntimeError(f"Failed to download checksum file: {e}")

    for file_name, checksum in files_checksum.items():
        file_path = llama_box_tmp_dir / file_name
        try:
            manager._download_file(f"{version_url_prefix}/{file_name}", file_path, base_url=PREFERRED_BASE_URL)
            if verify_file_checksum(file_path, checksum):
                manager._extract_file(file_path, llama_box_tmp_dir)
                source_binary = llama_box_tmp_dir / f'llama-box{exe()}'
                # e.g. llama-box-windows-amd64-cuda-12.4.zip -> cuda and 12.4.zip
                # e.g. llama-box-darwin-arm64-metal.zip -> metal and .zip
                suffix = file_name.removeprefix(target_prefix).split('-', 1)
                if len(suffix) < 2:
                    device_name = suffix[0].removesuffix('.zip')
                    version_suffix = '.zip'
                else:
                    device_name, version_suffix = suffix[0], suffix[1]
                # e.g. get the toolkit name from mapping, metal -> mps, cuda -> cuda, etc.
                toolkit_name = get_toolkit_name(device_name)
                # e.g. 12.4.zip -> 12.4
                version_suffix = version_suffix.removesuffix('.zip')
                if version_suffix != '':
                    version_suffix = '-' + version_suffix
                target_file_name = f'{target_prefix}{toolkit_name}{version_suffix}{exe()}'
                if not os.path.exists(source_binary):
                    raise RuntimeError(f"Expected binary {source_binary} not found after extraction.")
                if system() != 'windows':
                    st = os.stat(source_binary)
                    os.chmod(source_binary, st.st_mode | stat.S_IEXEC)
                shutil.move(source_binary, target_dir / target_file_name)
                manager._update_versions_file(target_file_name, version)
            else:
                raise RuntimeError(f"Checksum verification failed for {file_name}")
        except Exception as e:
            raise RuntimeError(f"Failed to download or verify {file_name}: {e}")

    # remove tmp dir
    if os.path.exists(llama_box_tmp_dir):
        shutil.rmtree(llama_box_tmp_dir)

def download():
    manager = ToolsManager()
    try:
        # cleanup third_party bin path
        manager.remove_cached_tools()
        manager.download_fastfetch()
        manager.download_gguf_parser()
        download_llama_box(manager)
    except Exception as e:
        print(f"Error downloading tools: {e}")
        raise

if __name__ == "__main__":
    try:
        download()
    except Exception as e:
        print(f"Failed to download tools: {e}")
        exit(1)
    print("Tools downloaded successfully.")
