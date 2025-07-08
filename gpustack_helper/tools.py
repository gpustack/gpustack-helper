import os
import shutil
import re
import logging
from packaging.version import parse
from pathlib import Path
from typing import Dict, Tuple
from gpustack.worker.tools_manager import ToolsManager, BUILTIN_LLAMA_BOX_VERSION
from gpustack.utils.platform import system, arch, DeviceTypeEnum
from importlib.resources import files
from gpustack_helper.defaults import get_dac_filename, dac_download_link

LLAMA_BOX = 'llama-box'
LLAMA_BOX_VERSION = os.getenv("LLAMA_BOX_VERSION", BUILTIN_LLAMA_BOX_VERSION)
LLAMA_BOX_DOWNLOAD_REPO = os.getenv("LLAMA_BOX_DOWNLOAD_REPO", f"gpustack/{LLAMA_BOX}")
PREFERRED_BASE_URL = os.getenv("PREFERRED_BASE_URL", None)
VERSION_URL_PREFIX = f"{LLAMA_BOX_DOWNLOAD_REPO}/releases/download/{LLAMA_BOX_VERSION}"
TARGET_PREFIX = f"dl-{LLAMA_BOX}-{system()}-{arch()}-"
TOOLKIT_NAME = os.getenv("TOOLKIT_NAME", None)

logger = logging.getLogger(__name__)


def exe() -> str:
    return ".exe" if system() == "windows" else ""


def get_package_dir(package_name: str) -> str:
    paths = package_name.rsplit(".", 1)
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
        return ""


def split_filename(file_name: str) -> Tuple[str, str]:
    suffix = file_name.removeprefix(TARGET_PREFIX).split("-", 1)
    if len(suffix) < 2:
        device_name = suffix[0].removesuffix(".zip")
        version_suffix = ".zip"
    else:
        device_name, version_suffix = suffix[0], suffix[1]
    # e.g. get the toolkit name from mapping, metal -> mps, cuda -> cuda, etc.
    toolkit_name = get_toolkit_name(device_name)
    version_suffix = version_suffix.removesuffix(".zip")
    return toolkit_name, version_suffix


def verify_file_checksum(file_path: str, expected_checksum: str) -> bool:
    """Verify the checksum of a file against an expected value."""
    import hashlib

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest() == expected_checksum


def download_checksum(
    manager: ToolsManager, tmp_dir: Path
) -> Dict[str, Tuple[str, str, str]]:
    """
    return the directory for the llama-box files and their checksums.
    Will be filtered by version, os and arch.
    The key would be toolkit name and the value would be a tuple of
    (version_suffix, file_name, checksum).
    """
    checksum_filename = "sha256sum.txt"
    checksum_file_path = tmp_dir / checksum_filename
    url_path = f"{VERSION_URL_PREFIX}/{checksum_filename}"
    # e.g. <device>: (<version>, <file_name>, <checksum>)
    files_checksum: Dict[str, Tuple[str, str, str]] = {}
    try:
        manager._download_file(
            url_path, checksum_file_path, base_url=PREFERRED_BASE_URL
        )
        with open(checksum_file_path, "r") as f:
            for line in f:
                pair = re.split(r"\s+", line.strip(), 1)
                if len(pair) != 2:
                    continue
                if not pair[1].startswith(TARGET_PREFIX):
                    continue
                toolkit, version_suffix = split_filename(pair[1])
                if toolkit in files_checksum:
                    if version_suffix == "":
                        continue
                    version, _, _ = files_checksum[toolkit]
                    if parse(version_suffix) <= parse(version):
                        # Skip if the version is not newer than the existing one
                        continue
                # e.g. dl-llama-box-linux-amd64-cuda-12.4.zip
                files_checksum[toolkit] = (version_suffix, pair[1], pair[0])

    except Exception as e:
        raise RuntimeError(f"Failed to download checksum file: {e}")
    return files_checksum


def download_and_extract(manager: ToolsManager, file_path: Path, checksum: str) -> Path:
    try:
        manager._download_file(
            f"{VERSION_URL_PREFIX}/{file_path.name}",
            file_path,
            base_url=PREFERRED_BASE_URL,
        )
        if not verify_file_checksum(file_path, checksum):
            raise RuntimeError(f"Checksum verification failed for {file_path.name}")
        manager._extract_file(file_path, file_path.parent)
        os.remove(file_path)  # Remove the zip file after extraction
        return file_path.parent
    except Exception as e:
        raise RuntimeError(f"Failed to download or verify {file_path.name}: {e}")


def download_llama_box(manager: ToolsManager):
    if TOOLKIT_NAME is None:
        logger.info(
            "TOOLKIT_NAME environment variable is not set, skipping llama-box download."
        )
        return
    target_dir = manager.third_party_bin_path / LLAMA_BOX
    llama_box_tmp_dir = target_dir / f"tmp-{LLAMA_BOX}"
    if os.path.exists(llama_box_tmp_dir):
        shutil.rmtree(llama_box_tmp_dir)
    os.makedirs(llama_box_tmp_dir, exist_ok=True)
    files_checksum = download_checksum(manager, llama_box_tmp_dir)
    if TOOLKIT_NAME not in files_checksum:
        raise ValueError(
            f"Required toolkit '{TOOLKIT_NAME}' not found in the checksum file."
        )
    _, file_name, checksum = files_checksum[TOOLKIT_NAME]
    basedir = f"{LLAMA_BOX}-{LLAMA_BOX_VERSION}-{system()}-{arch()}"
    if TOOLKIT_NAME != "":
        basedir += f"-{TOOLKIT_NAME}"
    file_path = llama_box_tmp_dir / basedir / file_name
    try:
        os.makedirs(file_path.parent, exist_ok=True)
        logger.info(f"Downloading {file_path.parent.name} '{LLAMA_BOX_VERSION}'")
        versioned_dir = download_and_extract(manager, file_path, checksum)
        shutil.move(versioned_dir, target_dir)
        manager._update_versions_file(versioned_dir.name, LLAMA_BOX_VERSION)

    except Exception as e:
        raise RuntimeError(f"Failed to download or verify {file_name}: {e}")

    # remove tmp dir
    if os.path.exists(llama_box_tmp_dir):
        shutil.rmtree(llama_box_tmp_dir)


def download():
    manager = ToolsManager()
    try:
        manager.download_fastfetch()
        manager.download_gguf_parser()
        download_llama_box(manager)
    except Exception as e:
        print(f"Error downloading tools: {e}")
        raise


def download_dac(base_path: str) -> str:
    filename = get_dac_filename()
    download_link = dac_download_link()
    if download_link is None:
        raise ValueError(
            f"Could not find model with filename {filename} in the DAC repository."
        )
    local_path = Path(base_path) / filename
    if not local_path.exists():
        import requests

        response = requests.get(download_link)

        if response.status_code != 200:
            raise ValueError(
                f"Could not download model. Received response code {response.status_code}"
            )
        local_path.write_bytes(response.content)
    return str(local_path)


if __name__ == "__main__":
    try:
        download()
    except Exception as e:
        print(f"Failed to download tools: {e}")
        exit(1)
    print("Tools downloaded successfully.")
