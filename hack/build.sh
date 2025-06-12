#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "${ROOT_DIR}/hack/lib/init.sh"

function build() {
  pyinstaller darwin.spec -y
}

function package() {
  pushd dist
  PACKAGE_NAME="unmanaged_gpustack.pkg"
  pkgbuild --component GPUStack.app --install-location "/Applications" --identifier "ai.gpustack.pkg" ${PACKAGE_NAME}  --version "${GIT_VERSION#*v}"
  PACKAGE_NAME=${PACKAGE_NAME} GIT_VERSION=${GIT_VERSION} envsubst < ../Distribution.xml.tmpl > Distribution.xml
  productbuild --distribution ./Distribution.xml --package-path ./  gpustack.pkg
  popd
}

function prepare_dependencies() {
  POETRY_ONLY=true bash "${ROOT_DIR}/hack/install.sh"
}

#
# main
#

gpustack::log::info "+++ BUILD +++"
prepare_dependencies
build
package
gpustack::log::info "--- BUILD ---"
