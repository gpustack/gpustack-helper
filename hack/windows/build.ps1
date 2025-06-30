# Set error handling
$ErrorActionPreference = "Stop"
$DebugPreference = "Continue"
$VerbosePreference = "Continue"
Set-PSDebug -Trace 1   # 显示每一行执行

$ROOT_DIR = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent | Split-Path -Parent | Split-Path -Parent -Resolve

# Include the common functions
. "$ROOT_DIR/hack/lib/windows/init.ps1"

function Build {
    $distDir = Join-Path -Path $ROOT_DIR -ChildPath "dist"
    Remove-Item -Path $distDir -Recurse -Force -ErrorAction SilentlyContinue

    $env:GIT_VERSION = $GIT_VERSION; poetry run pyinstaller windows.spec -y
    if ($LASTEXITCODE -ne 0) {
        GPUStack.Log.Fatal "failed to run pyinstaller."
    }
}

function Install-Dependency {
    & "$ROOT_DIR\hack\windows\install.ps1"
}

function Download-UI {
    $defaultTag = "latest"
    $poetryEnvPath = poetry env info --path | Select-Object -First 1
    $gpustackDir = Get-ChildItem -Path "$poetryEnvPath\lib" -Directory -Recurse -Filter gpustack | Select-Object -First 1
    $uiPath = Join-Path $gpustackDir.FullName "ui"
    $tmpUIPath = Join-Path $uiPath "tmp"
    $tag = if ($env:GIT_VERSION -and $env:GIT_VERSION -ne "v0.0.0.0") { $env:GIT_VERSION } else { $defaultTag }

    # 仅当 uiPath 不存在或为空时才下载
    if (Test-Path $uiPath -PathType Container) {
        $files = Get-ChildItem $uiPath -Force -ErrorAction SilentlyContinue
        if ($files | Where-Object { -not $_.PSIsContainer } | Measure-Object | Select-Object -ExpandProperty Count) {
            GPUStack.Log.Info "UI assets already exist in $uiPath, skipping download."
            return
        }
    }


    Remove-Item -Recurse -Force $uiPath -ErrorAction Ignore
    $null = New-Item -ItemType Directory -Path (Join-Path $tmpUIPath "ui") -Force

    GPUStack.Log.Info "downloading '$tag' UI assets"
    $url = "https://gpustack-ui-1303613262.cos.accelerate.myqcloud.com/releases/$tag.tar.gz"
    $tmpFile = Join-Path $tmpUIPath "ui.tar.gz"
    $downloaded = $false
    try {
        DownloadWithRetries -url $url -outFile $tmpFile -maxRetries 3
        & "$env:WINDIR/System32/tar" -xzf $tmpFile -C (Join-Path $tmpUIPath "ui")
        $downloaded = $true
    } catch {
        if ($tag -match '^v([0-9]+)\.([0-9]+)(\.[0-9]+)?(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$') {
            GPUStack.Log.Fatal "failed to download '$tag' ui archive"
        }
        GPUStack.Log.Warn "failed to download '$tag' ui archive, fallback to '$defaultTag' ui archive"
        $url = "https://gpustack-ui-1303613262.cos.accelerate.myqcloud.com/releases/$defaultTag.tar.gz"
        try {
            DownloadWithRetries -url $url -outFile $tmpFile -maxRetries 3
            & "$env:WINDIR/System32/tar" -xzf $tmpFile -C (Join-Path $tmpUIPath "ui")
            $downloaded = $true
        } catch {
            GPUStack.Log.Fatal "failed to download '$defaultTag' ui archive"
        }
    }
    if ($downloaded) {
        Copy-Item -Path (Join-Path $tmpUIPath "ui/dist/*") -Destination $uiPath -Recurse -Force
        Remove-Item -Recurse -Force (Join-Path $tmpUIPath "ui") -ErrorAction Ignore
        Remove-Item -Recurse -Force $tmpUIPath -ErrorAction Ignore
        Set-Content -Path (Join-Path $ROOT_DIR ".gpustack-ui-downloaded") -Value ""
    }
}

function DownloadWithRetries {
    param (
        [string]$url,
        [string]$outFile,
        [int]$maxRetries = 3
    )

    for ($i = 1; $i -le $maxRetries; $i++) {
        try {
            GPUStack.Log.Info "Attempting to download from $url (Attempt $i of $maxRetries)"
            Invoke-WebRequest -Uri $url -OutFile $outFile -ErrorAction Stop
            return
        }
        catch {
            GPUStack.Log.Warn "Download attempt $i failed: $($_.Exception.Message)"
            if ($i -eq $maxRetries) {
                throw $_
            }
        }
    }
}

function Cleanup-UI {
    $marker = Join-Path $ROOT_DIR ".gpustack-ui-downloaded"
    if (-not (Test-Path $marker)) {
        GPUStack.Log.Info "UI assets not downloaded, skipping cleanup."
        return
    }
    $poetryEnvPath = poetry env info --path | Select-Object -First 1
    $gpustackDir = Get-ChildItem -Path "$poetryEnvPath\lib" -Directory -Recurse -Filter gpustack | Select-Object -First 1
    $uiPath = Join-Path $gpustackDir.FullName "ui"
    if (Test-Path $uiPath -PathType Container) {
        Remove-Item -Recurse -Force $uiPath -ErrorAction Ignore
    }
    Remove-Item $marker -ErrorAction Ignore
}

#
# main
#

GPUStack.Log.Info "+++ BUILD +++"
try {
    Install-Dependency
    Download-UI
    Build
    Cleanup-UI
}
catch {
    GPUStack.Log.Fatal "failed to build: $($_.Exception.Message)"
}
GPUStack.Log.Info "--- BUILD ---"
