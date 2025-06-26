#!/usr/bin/env bash

##
# Inspired by github.com/kubernetes/kubernetes/hack/lib/version.sh
##

# -----------------------------------------------------------------------------
# Version management helpers. These functions help to set the
# following variables:
#
#    GIT_TREE_STATE  -  "clean" indicates no changes since the git commit id.
#                       "dirty" indicates source code changes after the git commit id.
#                       "archive" indicates the tree was produced by 'git archive'.
#                       "unknown" indicates cannot find out the git tree.
#        GIT_COMMIT  -  The git commit id corresponding to this
#                       source code.
#       GIT_VERSION  -  "vX.Y" used to indicate the last release version,
#                       it can be specified via "VERSION".
#        BUILD_DATE  -  The build date of the version.
DEBUG="${DEBUG:-}"
if [[ -n "${DEBUG}" ]]; then
  set -o xtrace
fi

function gpustack::version::get_version_vars() {
  #shellcheck disable=SC2034
  BUILD_DATE=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  GIT_TREE_STATE="unknown"
  GIT_COMMIT="unknown"
  GIT_VERSION="unknown"

  # get the git tree state if the source was exported through git archive.
  # shellcheck disable=SC2016,SC2050
  if [[ '$Format:%%$' == "%" ]]; then
    GIT_TREE_STATE="archive"
    GIT_COMMIT='$Format:%H$'
    # when a 'git archive' is exported, the '$Format:%D$' below will look
    # something like 'HEAD -> release-1.8, tag: v1.8.3' where then 'tag: '
    # can be extracted from it.
    if [[ '$Format:%D$' =~ tag:\ (v[^ ,]+) ]]; then
      GIT_VERSION="${BASH_REMATCH[1]}"
    else
      GIT_VERSION="${GIT_COMMIT:0:7}"
    fi
    # respect specified version.
    GIT_VERSION="${VERSION:-${GIT_VERSION}}"
    return
  fi

  # return directly if not found git client.
  if [[ -z "$(command -v git)" ]]; then
    # respect specified version.
    GIT_VERSION=${VERSION:-${GIT_VERSION}}
    return
  fi

  # find out git info via git client.
  if GIT_COMMIT=$(git rev-parse "HEAD^{commit}" 2>/dev/null); then
    # specify as dirty if the tree is not clean.
    if git_status=$(git status --porcelain --untracked-files=no 2>/dev/null) && [[ -n ${git_status} ]]; then
      GIT_TREE_STATE="dirty"
    else
      GIT_TREE_STATE="clean"
    fi

    # specify with the tag if the head is tagged.
    if GIT_VERSION="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"; then
      if git_tag=$(git tag -l --contains HEAD 2>/dev/null | head -n 1 2>/dev/null) && [[ -n ${git_tag} ]]; then
        GIT_VERSION="${git_tag}"
      fi
    fi

    # specify to v0.0.0 if the tree is dirty.
    if [[ "${GIT_TREE_STATE:-dirty}" == "dirty" ]]; then
      GIT_VERSION="v0.0.0.0"
    elif ! [[ "${GIT_VERSION}" =~ ^v([0-9]+)\.([0-9]+)(\.[0-9]+)?(\.[0-9]+)? ]]; then
      GIT_VERSION="v0.0.0.0"
    fi

    # respect specified version
    GIT_VERSION=${VERSION:-${GIT_VERSION}}
  fi

  if [[ "${GIT_VERSION}" == "v0.0.0.0" ]]; then
    LAST_TAG=$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || true)
    if [[ -z "${LAST_TAG}" ]]; then
      LAST_TAG="v0.0.0.0"
    fi
    # Keep 3 digits of the version number, and calculate the fourth digit with github.run_number
    if [[ "${LAST_TAG}" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
      major="${BASH_REMATCH[1]}"
      minor="${BASH_REMATCH[2]}"
      patch="${BASH_REMATCH[3]}"
      build="${BASH_REMATCH[4]}"
      # the build number must >=100 with 100 per step. but we don't need to validate it here.
      # the run_number will mod 100 and add to build.
      new_build=$((build + (${GITHUB_RUN_NUMBER:-99} % 100)))
      if [ "$new_build" -eq "$build" ]; then
        build=$((new_build + 100))
      else
        build=${new_build}
      fi
      GIT_VERSION="v${major}.${minor}.${patch}.${build}"
    elif [[ "${LAST_TAG}" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
      major="${BASH_REMATCH[1]}"
      minor="${BASH_REMATCH[2]}"
      patch="${BASH_REMATCH[3]}"
      # set to the maximum build number if not specified.
      build="${GITHUB_RUN_NUMBER:-999}"
      GIT_VERSION="v${major}.${minor}.${patch}.${build}"
    else
      GIT_VERSION="v0.0.1.${GITHUB_RUN_NUMBER:-999}"
    fi
  fi
}
