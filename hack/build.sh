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

function build_i18n() {
  # shellcheck disable=SC2086
  poetry run pyside6-lupdate ${ROOT_DIR}/gpustack_helper/*.py "${ROOT_DIR}/gpustack_helper/status.py" ${ROOT_DIR}/gpustack_helper/quickconfig/*.py ${ROOT_DIR}/gpustack_helper/services/*.py -ts "${ROOT_DIR}/translations/zh_CN.ts" -ts "${ROOT_DIR}/translations/en_US.ts" -no-obsolete
  # 检查未翻译条目
  if grep 'type="unfinished"' "${ROOT_DIR}/translations/zh_CN.ts" > /dev/null; then
    gpustack::log::error "zh_CN 存在未翻译的条目，请先完成翻译！"
    grep 'type="unfinished"' "${ROOT_DIR}/translations/zh_CN.ts"
    exit 1
  fi
  if grep 'type="unfinished"' "${ROOT_DIR}/translations/en_US.ts" > /dev/null; then
    gpustack::log::error "en_US 存在未翻译的条目，请先完成翻译！"
    grep 'type="unfinished"' "${ROOT_DIR}/translations/en_US.ts"
    exit 1
  fi
  # 检查 ts 文件是否有未提交的更改
  if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
    gpustack::log::error "translations/zh_CN.ts 有未提交的更改，请先提交后再生成 qm 文件！"
    git status --short "${ROOT_DIR}/translations/zh_CN.ts"
    exit 1
  fi
  poetry run pyside6-lrelease "${ROOT_DIR}/translations/zh_CN.ts" -qm "${ROOT_DIR}/translations/zh_CN.qm"
  poetry run pyside6-lrelease "${ROOT_DIR}/translations/en_US.ts" -qm "${ROOT_DIR}/translations/en_US.qm"
}

#
# main
#

gpustack::log::info "+++ BUILD +++"
prepare_dependencies
download_ui
build_i18n
build
cleanup_ui
gpustack::log::info "--- BUILD ---"
