#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "${ROOT_DIR}/hack/lib/init.sh"

gpustack::log::info "+++ EXPORTING VERSION +++"
# Export variables to GitHub Actions output if running in GitHub Actions
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    echo "GIT_VERSION=${GIT_VERSION}"
    echo "GIT_COMMIT=${GIT_COMMIT}"
    echo "GIT_TREE_STATE=${GIT_TREE_STATE}"
    echo "BUILD_DATE=${BUILD_DATE}"
  } >> "$GITHUB_OUTPUT"
fi

if [ -n "$(command -v poetry)" ]; then
  GPUSTACK_COMMIT="$(poetry export --without-hashes 2>/dev/null | grep 'gpustack' |grep -oE '@[0-9a-f]{7,40}' | head -n1 | cut -c2-8)"
  echo "GPUSTACK_COMMIT=${GPUSTACK_COMMIT}"
  # Use envsubst to replace variables in the template file
  GIT_VERSION=${GIT_VERSION#v} GIT_COMMIT=${GIT_COMMIT:0:7} GPUSTACK_COMMIT=${GPUSTACK_COMMIT} envsubst < "${ROOT_DIR}/hack/patch/_version.py.tmpl" > "${ROOT_DIR}/gpustack_helper/_version.py"
fi

# Print the variables
echo "${GIT_VERSION}" "${GIT_COMMIT}" "${GIT_TREE_STATE}" "${BUILD_DATE} ${GPUSTACK_COMMIT}"
gpustack::log::info "--- EXPORTING VERSION ---"
