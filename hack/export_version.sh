#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "${ROOT_DIR}/hack/lib/init.sh"

# Print the variables
echo "${GIT_VERSION}" "${GIT_COMMIT}" "${GIT_TREE_STATE}" "${BUILD_DATE}"

# Export variables to GitHub Actions output if running in GitHub Actions
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    echo "GIT_VERSION=${GIT_VERSION}"
    echo "GIT_COMMIT=${GIT_COMMIT}"
    echo "GIT_TREE_STATE=${GIT_TREE_STATE}"
    echo "BUILD_DATE=${BUILD_DATE}"
  } >> "$GITHUB_OUTPUT"
fi
