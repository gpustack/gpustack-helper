import os
import requests
import zipfile
import shutil
from io import BytesIO

NSSM_VERSION = "nssm-2.24-101-g897c7ad"
OFFICIAL_NSSM_DOWNLOAD_URL = f"https://nssm.cc/ci/{NSSM_VERSION}.zip"
NSSM_DOWNLOAD_URL = os.getenv("NSSM_DOWNLOAD_URL", OFFICIAL_NSSM_DOWNLOAD_URL)


def download_nssm(target_dir: str) -> None:
    """Download and extract NSSM to the specified target directory."""
    shutil.rmtree(os.path.join(target_dir, NSSM_VERSION), ignore_errors=True)

    response = requests.get(NSSM_DOWNLOAD_URL)
    if response.status_code != 200:
        raise Exception(f"Failed to download NSSM from {NSSM_DOWNLOAD_URL}")

    with zipfile.ZipFile(BytesIO(response.content)) as z:
        z.extractall(target_dir)

    print(f"NSSM has been downloaded and extracted to {target_dir}")
