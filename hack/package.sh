#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "${ROOT_DIR}/hack/lib/init.sh"

function package() {
  pushd dist
  PACKAGE_NAME="unmanaged_gpustack.pkg"
  OUTPUT_NAME="unsigned_gpustack-${GIT_VERSION}.pkg"
  rm -f "${PACKAGE_NAME}" "${OUTPUT_NAME}" Distribution.xml
  pkgbuild --component GPUStack.app --install-location "/Applications" --identifier "ai.gpustack.pkg" "${PACKAGE_NAME}"  --version "${GIT_VERSION#*v}" --scripts "${ROOT_DIR}/scripts"
  PACKAGE_NAME=${PACKAGE_NAME} GIT_VERSION=${GIT_VERSION} envsubst < ../Distribution.xml.tmpl > Distribution.xml
  productbuild --distribution ./Distribution.xml --package-path ./  "${OUTPUT_NAME}"
  popd
}

function sign_installer() {
  pushd dist
  TO_SIGN_NAME="unsigned_gpustack-${GIT_VERSION}.pkg"
  SIGNED_NAME="gpustack-${GIT_VERSION}.pkg"
  CERT_NAME="${CERT_NAME:-Developer ID Installer: Seal Software Co., Ltd. (33M7PPLX4U)}"
  APPLE_ID="${APPLE_ID:-}"
  TEAM_ID="${TEAM_ID:-33M7PPLX4U}"
  APP_PASSWORD="${APP_PASSWORD:-}"
  if ! security find-identity -v | grep -q "$CERT_NAME"; then
    gpustack::log::warn "Certificate '$CERT_NAME' not found. Skipping signing and rename installer."
    mv "${TO_SIGN_NAME}" "${SIGNED_NAME}"
    return 0
  fi
  # check for APPLE_ID, TEAM_ID and APP_PASSWORD
  if [[ -z "${APPLE_ID}" || -z "${TEAM_ID}" || -z "${APP_PASSWORD}" ]]; then
    gpustack::log::error "APPLE_ID, TEAM_ID and APP_PASSWORD must be set to sign and notarize the package."
    gpustack::log::error "You can set them in your environment or in the script."
    return 0
  fi
  if [[ ! -f "${TO_SIGN_NAME}" ]]; then
    gpustack::log::error "Package '${TO_SIGN_NAME}' not found. Cannot sign."
    return 1
  fi
  if [[ -f "${SIGNED_NAME}" ]]; then
    rm -f "${SIGNED_NAME}"
  fi
  gpustack::log::info "Signing package '${TO_SIGN_NAME}' with certificate '${CERT_NAME}'"
  if ! productsign --sign "${CERT_NAME}" "${TO_SIGN_NAME}" "${SIGNED_NAME}" ; then
    gpustack::log::error "Failed to sign package '${TO_SIGN_NAME}'"
    return 1
  fi
  gpustack::log::info "Package signed successfully: '${SIGNED_NAME}'"
  # notary package
  if ! xcrun notarytool submit "${SIGNED_NAME}" --apple-id "${APPLE_ID}" --team-id "${TEAM_ID}" --password "${APP_PASSWORD}" --wait; then
    gpustack::log::error "Failed to notarize package '${SIGNED_NAME}'"
    return 1
  fi
  if ! xcrun stapler staple "${SIGNED_NAME}"; then
    gpustack::log::error "Failed to staple package '${SIGNED_NAME}'"
    return 1
  fi
  gpustack::log::info "Package notarized and stapled successfully: '${SIGNED_NAME}'"
  # check notarization status with spctl
  if ! spctl -a -vvv -t install "${SIGNED_NAME}" 2>&1 | grep -q "accepted"; then
    gpustack::log::error "Package '${SIGNED_NAME}' failed notarization"
    spctl -a -vvv -t install "${SIGNED_NAME}"
    return 1
  fi
  popd
}

gpustack::log::info "+++ PACKAGE +++"
package
sign_installer
gpustack::log::info "--- PACKAGE ---"
