#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "${ROOT_DIR}/hack/lib/init.sh"

function download_and_build(){
  if [ -d "${ROOT_DIR}/openfst/build/lib" ] && [ -d "${ROOT_DIR}/openfst/build/include" ]; then
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
  ./configure --disable-dependency-tracking --disable-silent-rules --prefix="${PWD}/build"  --enable-fsts --enable-compress --enable-grm --enable-special
  make
  make install
  gpustack::log::info "OpenFst built and installed successfully."
  popd
}

gpustack::log::info "+++ BUILD_OPENFST +++"
download_and_build
gpustack::log::info "--- BUILD_OPENFST ---"
