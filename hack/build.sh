#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "${ROOT_DIR}/hack/lib/init.sh"


function download_ui() {
  local default_tag="latest"
  local ui_path
  ui_path=$(find "$(poetry env info --path)/lib" -type d -name gpustack | head -n 1)
  ui_path="${ui_path}/ui"
  local tmp_ui_path="${ui_path}/tmp"
  local tag="latest"

  # Only download if ui_path does not exist or is empty
  if [[ -d "${ui_path}" && $(ls -A "${ui_path}" 2>/dev/null) ]]; then
    gpustack::log::info "UI assets already exist in ${ui_path}, skipping download."
    return
  fi

  if [[ "${GIT_VERSION}" != "v0.0.0.0" ]]; then
    tag="${GIT_VERSION}"
  fi

  rm -rf "${ui_path}"
  mkdir -p "${tmp_ui_path}/ui"

  gpustack::log::info "downloading '${tag}' UI assets"

  if ! curl --retry 3 --retry-connrefused --retry-delay 3 -sSfL "https://gpustack-ui-1303613262.cos.accelerate.myqcloud.com/releases/${tag}.tar.gz" 2>/dev/null |
    tar -xzf - --directory "${tmp_ui_path}/ui" 2>/dev/null; then

    if [[ "${tag:-}" =~ ^v([0-9]+)\.([0-9]+)(\.[0-9]+)?(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$ ]]; then
      gpustack::log::fatal "failed to download '${tag}' ui archive"
    fi

    gpustack::log::warn "failed to download '${tag}' ui archive, fallback to '${default_tag}' ui archive"
    if ! curl --retry 3 --retry-connrefused --retry-delay 3 -sSfL "https://gpustack-ui-1303613262.cos.accelerate.myqcloud.com/releases/${default_tag}.tar.gz" |
      tar -xzf - --directory "${tmp_ui_path}/ui" 2>/dev/null; then
      gpustack::log::fatal "failed to download '${default_tag}' ui archive"
    fi
  fi
  cp -a "${tmp_ui_path}/ui/dist/." "${ui_path}"

  rm -rf "${tmp_ui_path}"
  touch .gpustack-ui-downloaded
}

function cleanup_ui() {
  if [[ ! -f .gpustack-ui-downloaded ]]; then
    gpustack::log::info "UI assets not downloaded, skipping cleanup."
    return
  fi
  local ui_path
  ui_path=$(find "$(poetry env info --path)/lib" -type d -name gpustack | head -n 1)
  ui_path="${ui_path}/ui"
  if [[ -d "${ui_path}" ]]; then
    rm -rf "${ui_path}"
  fi
  rm .gpustack-ui-downloaded
}

function build() {
  GIT_VERSION=${GIT_VERSION} poetry run pyinstaller darwin.spec -y
}

function prepare_dependencies() {
  POETRY_ONLY=true bash "${ROOT_DIR}/hack/install.sh"
}

#
# main
#

gpustack::log::info "+++ BUILD +++"
prepare_dependencies
download_ui
build
cleanup_ui
gpustack::log::info "--- BUILD ---"
