# file: scripts/migrate-models.ps1
param()
$ErrorActionPreference = "Stop"

$target = Join-Path -Path (Get-Location) -ChildPath "outputs\models"
New-Item -ItemType Directory -Force -Path $target | Out-Null

if (Test-Path ".\models") {
    Copy-Item ".\models\*"  $target -Recurse -Force
}
if (Test-Path ".\modelos") {
    Copy-Item ".\modelos\*" $target -Recurse -Force
}
