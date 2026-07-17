param(
    [string]$Output = "$PSScriptRoot\..\go2_x5_deployment.zip",
    [string]$CameraSdkRoot = "$env:USERPROFILE\Desktop\Linux_CameraSDK-2.1.1_MediaSDK-3.1.1\Linux_CameraSDK-2.1.1_MediaSDK-3.1.1"
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..").Path
$stage = Join-Path $env:TEMP "go2_x5_deployment"
if (Test-Path $stage) { Remove-Item -Recurse -Force -LiteralPath $stage }
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item -Recurse -Force "$root\*" $stage
Get-ChildItem $stage -Recurse -Directory | Where-Object Name -in @('.git', '__pycache__', '.pytest_cache') | Remove-Item -Recurse -Force
if (Test-Path $CameraSdkRoot) {
    New-Item -ItemType Directory -Path "$stage\vendor" -Force | Out-Null
    Copy-Item "$CameraSdkRoot\CameraSDK-2.1.1-Linux.tar.gz" "$stage\vendor\" -ErrorAction SilentlyContinue
    Copy-Item "$CameraSdkRoot\CameraSDK-2.1.1-gcc-arm-11.2-2022.02-x86_64-aarch64-none-linux-gnu.tar.gz" "$stage\vendor\" -ErrorAction SilentlyContinue
}
Compress-Archive -Path "$stage\*" -DestinationPath $Output -Force
Write-Output "Created $Output"
