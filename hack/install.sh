#!/usr/bin/env bash

# Set error handling
set -o errexit
set -o nounset
set -o pipefail

# Get the root directory and third_party directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

# Include the common functions
source "${ROOT_DIR}/hack/lib/init.sh"

function download_deps() {
  if [[ -z "$(command -v poetry)" ]]; then
    pip install poetry==1.8.3
  fi
  poetry install
  if [[ "${POETRY_ONLY:-false}" == "false" ]]; then
    pip install pre-commit==3.7.1
    pre-commit install
  fi
}

gpustack::log::info "+++ DEPENDENCIES +++"
if [ ! -d "${ROOT_DIR}/openfst/build/lib" ] || [ ! -d "${ROOT_DIR}/openfst/build/include" ]; then
  gpustack::log::info "OpenFst not found, downloading and building..."
  source "${ROOT_DIR}/hack/build-openfst.sh"
else
  gpustack::log::info "OpenFst already exists and built, skipping download."
fi
export LIBRARY_PATH="${ROOT_DIR}/openfst/build/lib:${LIBRARY_PATH:-}"
export CPLUS_INCLUDE_PATH="${ROOT_DIR}/openfst/build/include:${CPLUS_INCLUDE_PATH:-}"
download_deps
gpustack::log::info "--- DEPENDENCIES ---"
