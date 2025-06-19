#!/usr/bin/env bash

# Set error handling
set -o errexit
set -o nounset
set -o pipefail

# Get the root directory and third_party directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

# Include the common functions
source "${ROOT_DIR}/hack/lib/init.sh"

PREFIX="${INSTALL_PREFIX:-${ROOT_DIR}/openfst/build}"

function download_deps() {
  if [[ -z "$(command -v poetry)" ]]; then
    pip install poetry==1.8.3
  fi
  poetry install
  if [[ "${POETRY_ONLY:-false}" == "false" ]]; then
    pip install pre-commit==4.2.0
    pre-commit install
  fi
}

gpustack::log::info "+++ DEPENDENCIES +++"
source "${ROOT_DIR}/hack/build-openfst.sh"
export LIBRARY_PATH="${PREFIX}/lib:${LIBRARY_PATH:-}"
export CPLUS_INCLUDE_PATH="${PREFIX}/include:${CPLUS_INCLUDE_PATH:-}"
download_deps
gpustack::log::info "--- DEPENDENCIES ---"
