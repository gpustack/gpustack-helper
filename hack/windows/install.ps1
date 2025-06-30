# Set error handling
$ErrorActionPreference = "Stop"

# Get the root directory and third_party directory
$ROOT_DIR = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent | Split-Path -Parent | Split-Path -Parent -Resolve

# Include the common functions
. "$ROOT_DIR/hack/lib/windows/init.ps1"

function Install-Dependency {
    pip install poetry==1.8.3
    if ($LASTEXITCODE -ne 0) {
        GPUStack.Log.Fatal "failed to install poetry."
    }

    poetry install
    if ($LASTEXITCODE -ne 0) {
        GPUStack.Log.Fatal "failed run poetry install."
    }

    poetry run pre-commit install
    if ($LASTEXITCODE -ne 0) {
        GPUStack.Log.Fatal "failed run pre-commit install."
    }
}


#
# main
#

GPUStack.Log.Info "+++ DEPENDENCIES +++"
try {
    Install-Dependency
    . "$ROOT_DIR/hack/windows/export_version.ps1"
}
catch {
    GPUStack.Log.Fatal "failed to download dependencies: $($_.Exception.Message)"
}
GPUStack.Log.Info "-- DEPENDENCIES ---"
