#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "${ROOT_DIR}/hack/lib/init.sh"

function package() {
  pushd dist
  PACKAGE_NAME="unmanaged_gpustack.pkg"
  OUTPUT_NAME="gpustack-${GIT_VERSION}.pkg"
  rm -f "${PACKAGE_NAME}" "${OUTPUT_NAME}" Distribution.xml
  pkgbuild --component GPUStack.app --install-location "/Applications" --identifier "ai.gpustack.pkg" "${PACKAGE_NAME}"  --version "${GIT_VERSION#*v}" --scripts "${ROOT_DIR}/scripts"
  PACKAGE_NAME=${PACKAGE_NAME} GIT_VERSION=${GIT_VERSION} envsubst < ../Distribution.xml.tmpl > Distribution.xml
  productbuild --distribution ./Distribution.xml --package-path ./  "${OUTPUT_NAME}"
  popd
}

gpustack::log::info "+++ PACKAGE +++"
package
gpustack::log::info "--- PACKAGE ---"
