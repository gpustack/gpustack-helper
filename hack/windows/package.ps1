# Set error handling
$ErrorActionPreference = "Stop"
$DebugPreference = "Continue"
$VerbosePreference = "Continue"
Set-PSDebug -Trace 1   # 显示每一行执行

$ROOT_DIR = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent | Split-Path -Parent | Split-Path -Parent -Resolve

# Include the common functions
. "$ROOT_DIR/hack/lib/windows/init.ps1"

function Build-Installer {
    Set-Location $ROOT_DIR
    $distDir = "dist/main"
    $buildDir = "build/_internal_files.wxs"
    # Use global GIT_VERSION and remove leading 'v' if present
    $productVersion = $global:GIT_VERSION -replace '^v', ''
    $outputMsi = "dist/GPUStackInstaller-$productVersion.msi"

    GPUStack.Log.Info "[1/3] Running heat.exe to generate wxs file..."
    heat.exe dir "$distDir" -o "$buildDir" -gg -sfrag -srd -sreg -ke -cg PyinstallerBuiltFiles -dr INSTALLFOLDER -var var.DistDir
    if ($LASTEXITCODE -ne 0) { throw "heat.exe failed, exit code $LASTEXITCODE" }

    GPUStack.Log.Info "[2/3] Running candle.exe to compile wxs..."
    candle.exe -dDistDir="$distDir" -dProductVersion="$productVersion" -dInstallationDir="." .\GPUStack.wxs $buildDir -ext WixUtilExtension -ext WixUIExtension
    if ($LASTEXITCODE -ne 0) { throw "candle.exe failed, exit code $LASTEXITCODE" }

    GPUStack.Log.Info "[3/3] Running light.exe to generate MSI installer..."
    light.exe -v -out "$outputMsi" .\GPUStack.wixobj .\_internal_files.wixobj -ext WixUIExtension -ext WixUtilExtension
    if ($LASTEXITCODE -ne 0) { throw "light.exe failed, exit code $LASTEXITCODE" }
}

GPUStack.Log.Info "+++ PACKAGE +++"
try {
    Build-Installer
}
catch {
    GPUStack.Log.Fatal "failed to build: $($_.Exception.Message)"
}
GPUStack.Log.Info "--- PACKAGE ---"
