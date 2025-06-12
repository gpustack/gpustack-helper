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
  pip install poetry==1.8.3
  poetry install
  if [[ "${POETRY_ONLY:-false}" == "false" ]]; then
    pip install pre-commit==3.7.1
    pre-commit install
  fi
}

gpustack::log::info "+++ DEPENDENCIES +++"
download_deps
gpustack::log::info "--- DEPENDENCIES ---"
