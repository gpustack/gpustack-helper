import os
import certifi

if __name__ == "__main__":
    # Ensure the SSL_CERT_FILE environment variable is set to the path provided by certifi.
    # This guarantees that secure connections use the correct certificate file.
    # It is initialized early to ensure other modules use the correct configuration.
    if os.getenv("SSL_CERT_FILE", None) is None:
        os.environ["SSL_CERT_FILE"] = certifi.where()

from gpustack.main import main as gpustack
from vox_box.main import main as vox_box
import multiprocessing
import re
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.argv[0] = re.sub(r"(-script\.pyw|\.exe)?$", "", sys.argv[0])
    binary_name = os.path.basename(
        sys.argv[0]
    )  # Ensure the script name is set correctly
    if binary_name == "vox-box":
        sys.exit(vox_box())
    else:
        sys.exit(gpustack())
