#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

DEBUG="${DEBUG:-}"
if [[ -n "${DEBUG}" ]]; then
  set -o xtrace
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "${ROOT_DIR}/hack/lib/init.sh"

PREFIX="${INSTALL_PREFIX:-${ROOT_DIR}/openfst/build}"

function download_and_build(){
  if ls "${PREFIX}/lib/libfst"* 1>/dev/null 2>&1 && ls "${PREFIX}/lib/fst/"* 1>/dev/null 2>&1 && [ -d "${PREFIX}/include/fst" ]; then
    gpustack::log::info "OpenFst already exists and built, skipping download."
    return
  fi
  rm -rf "${ROOT_DIR}/openfst" || true
  target_url='https://openfst.org/twiki/pub/FST/FstDownload/openfst-1.8.3.tar.gz'
  mkdir -p "${ROOT_DIR}/openfst/build"
  curl --retry 3 --retry-connrefused --retry-delay 3 -sSfL "${target_url}" | tar -xz -C openfst --strip-components=1
  patch openfst/src/include/fst/bi-table.h < "${ROOT_DIR}/hack/patch/openfst.patch"
  pushd "${ROOT_DIR}/openfst"
  mkdir -p build
  ./configure --disable-dependency-tracking --disable-silent-rules --prefix="${PREFIX}"  --enable-fsts --enable-compress --enable-grm --enable-special
  make
  make install
  gpustack::log::info "OpenFst built and installed successfully."
  popd
}

gpustack::log::info "+++ BUILD_OPENFST +++"
download_and_build
gpustack::log::info "--- BUILD_OPENFST ---"
