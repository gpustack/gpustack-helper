from gpustack.main import main as gpustack
from vox_box.main import main as vox_box
import multiprocessing
import re
import sys
import os

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.argv[0] = re.sub(r"(-script\.pyw|\.exe)?$", "", sys.argv[0])
    binary_name = os.path.basename(sys.argv[0])  # Ensure the script name is set correctly
    if binary_name == 'vox-box':
        sys.exit(vox_box())
    else:
        sys.exit(gpustack())
