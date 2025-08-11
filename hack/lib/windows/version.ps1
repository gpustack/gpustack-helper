# Define the function to get version variables
function Get-GPUStackVersionVar {
    # Get the build date
    $BUILD_DATE = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ'

    # Initialize other variables
    $GIT_TREE_STATE = "unknown"
    $GIT_COMMIT = "unknown"
    $GIT_VERSION = "unknown"

    # Check if the source was exported through git archive
    if ('%$Format:%' -eq '%') {
        $GIT_TREE_STATE = "archive"
        $GIT_COMMIT = '$Format:%H$'

        # Parse the version from '$Format:%D$'
        if ('%$Format:%D$' -match 'tag:\s+(v[^ ,]+)') {
            $GIT_VERSION = $matches[1]
        }
        else {
            $GIT_VERSION = $GIT_COMMIT.Substring(0, 7)
        }

        # Respect specified version
        $GIT_VERSION = $env:VERSION -or $GIT_VERSION
        return
    }

    # Return if git client is not found
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        $GIT_VERSION = $env:VERSION -or $GIT_VERSION
        return
    }

    # Find git info via git client
    $GIT_COMMIT = git rev-parse "HEAD^{commit}" 2>$null
    if ($LASTEXITCODE -eq 0) {
        # Check if the tree is clean or dirty
        $gitStatus = (git status --porcelain 2>$null)
        if ($gitStatus) {
            $GIT_TREE_STATE = "dirty"
        }
        else {
            $GIT_TREE_STATE = "clean"
        }

        # Get the version from HEAD
        $GIT_VERSION = git rev-parse --abbrev-ref HEAD 2>$null
        if ($LASTEXITCODE -eq 0) {
            # Check if HEAD is tagged
            $gitTag = git tag -l --contains HEAD 2>$null | Select-Object -First 1
            if (-not [string]::IsNullOrEmpty($gitTag)) {
                $GIT_VERSION = $gitTag
            }
        }

        # Set version to 'v0.0.0' if the tree is dirty or version format does not match
        if ($GIT_TREE_STATE -eq "dirty" -or -not ($GIT_VERSION -match '^v([0-9]+)\.([0-9]+)\.([0-9]+)$')) {
            $GIT_VERSION = "v0.0.0"
        }

        # Respect specified version
        if ($env:VERSION) {
            $GIT_VERSION = $env:VERSION
        }
    }

    $global:BUILD_DATE = $BUILD_DATE
    $global:GIT_TREE_STATE = $GIT_TREE_STATE
    $global:GIT_COMMIT = $GIT_COMMIT
    $global:GIT_VERSION = $GIT_VERSION

    # If GIT_VERSION is v0.0.0, try to increment patch and append GITHUB_RUN_NUMBER
    if ($GIT_VERSION -eq "v0.0.0") {
        try {
            $LAST_TAG = git describe --tags --abbrev=0 HEAD^ 2>$null
        } catch {
            $LAST_TAG = "v0.0.0"
        }

        if (-not $LAST_TAG) {
            $LAST_TAG = "v0.0.0"
        }
        $GITHUB_RUN_NUMBER = $env:GITHUB_RUN_NUMBER
        if (-not $GITHUB_RUN_NUMBER) { $GITHUB_RUN_NUMBER = "99" }
        if ($LAST_TAG -match '^v([0-9]+)\.([0-9]+)\.([0-9]+)$') {
            $major = $matches[1]
            $minor = $matches[2]
            $patch_base = [int]$matches[3]
            $patch_mod = [int]$GITHUB_RUN_NUMBER % 100
            $new_patch = $patch_base + $patch_mod
            if ($new_patch -eq $patch_base) {
                $new_patch = $patch_base + 100
            }
            $new_patch_fmt = "{0:D4}" -f $new_patch
            $GIT_VERSION = "v$major.$minor.$new_patch_fmt"
        } else {
            # If no tag, patch=1+mod
            $patch_mod = [int]$GITHUB_RUN_NUMBER % 100
            $patch = 1 + $patch_mod
            $GIT_VERSION = "v0.0.$patch"
        }
        $global:GIT_VERSION = $GIT_VERSION
    }
}
