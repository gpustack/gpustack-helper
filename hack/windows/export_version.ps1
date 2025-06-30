# Requires PowerShell 5.0+
# Set error handling
$ErrorActionPreference = "Stop"

$ROOT_DIR = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent | Split-Path -Parent | Split-Path -Parent -Resolve

# Include the common functions
. "$ROOT_DIR/hack/lib/windows/init.ps1"

Write-Host '+++ EXPORTING VERSION +++'

# Export variables to GitHub Actions output if running in GitHub Actions
if ($env:GITHUB_OUTPUT) {
    Add-Content -Path $env:GITHUB_OUTPUT -Value "GIT_VERSION=$GIT_VERSION"
    Add-Content -Path $env:GITHUB_OUTPUT -Value "GIT_COMMIT=$GIT_COMMIT"
    Add-Content -Path $env:GITHUB_OUTPUT -Value "GIT_TREE_STATE=$GIT_TREE_STATE"
    Add-Content -Path $env:GITHUB_OUTPUT -Value "BUILD_DATE=$BUILD_DATE"
}

$versionFile = "$ROOT_DIR/gpustack_helper/_version.py"
if (-not (Test-Path $versionFile)) {
    Set-Content -Path $versionFile -Value "__version__ = 'v0.0.0.0'"
}

if (Get-Command poetry -ErrorAction SilentlyContinue) {
    poetry config warnings.export false
    $GPUSTACK_COMMIT = $(poetry export --without-hashes 2>$null | Select-String 'gpustack' | ForEach-Object { if ($_ -match '@([0-9a-f]{7,40})') { $matches[1].Substring(0,7) } })
    Write-Host "GPUSTACK_COMMIT=$GPUSTACK_COMMIT"
    # Use envsubst equivalent in PowerShell
    $template = Get-Content "$ROOT_DIR/hack/patch/_version.py.tmpl" -Raw
    $template = $template -replace '\$\{GIT_VERSION\}', $GIT_VERSION.TrimStart('v')
    $template = $template -replace '\$\{GIT_COMMIT\}', $GIT_COMMIT.Substring(0,7)
    $template = $template -replace '\$\{GPUSTACK_COMMIT\}', $GPUSTACK_COMMIT
    Set-Content -Path "$ROOT_DIR/gpustack_helper/_version.py" -Value $template
}

# Print the variables
Write-Host "$GIT_VERSION $GIT_COMMIT $GIT_TREE_STATE $BUILD_DATE $GPUSTACK_COMMIT"
Write-Host '--- EXPORTING VERSION ---'
