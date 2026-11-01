# Puts the files a game folder needs besides the program into its UserData folder: the built-in HD texture pack
# (texture_pack\ScoobyHD, kept out of git) and the button prompt icons (tools\make-button-icons.py).
#   powershell -ExecutionPolicy Bypass -File tools\stage-userdata.ps1 -UserData <folder> [-Required]
# Used by build-no100f.ps1 (Play\UserData, after every build) and package-scooby.ps1 (the release). Only what changed
# is copied or rebuilt. -Required (packaging) stops on anything missing; without it a missing piece is a warning, so a
# test build still finishes.
[CmdletBinding()] param([Parameter(Mandatory)][string]$UserData, [switch]$Required)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Fail([string]$Text) {
    if ($Required) { throw $Text }
    Write-Warning $Text
}

New-Item -ItemType Directory -Force $UserData | Out-Null

# 1. HD texture pack: a mirror of texture_pack\ScoobyHD (other packs in texture_replacements are left alone).
$packSource = Join-Path $root 'texture_pack\ScoobyHD'
$pack = Join-Path $UserData 'texture_replacements\ScoobyHD'
if (Test-Path -LiteralPath $packSource) {
    New-Item -ItemType Directory -Force $pack | Out-Null
    robocopy $packSource $pack /MIR /NJH /NJS /NFL /NDL /NP /R:1 /W:1 | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "copying the HD pack failed (robocopy exit code $LASTEXITCODE)" }
    $global:LASTEXITCODE = 0
    Write-Host "HD pack: $pack ($((Get-ChildItem -LiteralPath $pack -File).Count) files)"
} else {
    Fail "texture_pack\ScoobyHD is missing (the built-in HD texture pack): $pack not updated"
}

# 2. Button prompt icons, drawn from tools\button-art over the HD pack's layout. Rebuilt when the tool or the art is
# newer than the icons (or the folder has the old layout).
$icons = Join-Path $UserData 'button_icons'
$layout = Join-Path $icons 'layout.txt'
$tool = Join-Path $root 'tools\make-button-icons.py'
$inputs = @(Get-Item -LiteralPath $tool) + @(Get-ChildItem -LiteralPath (Join-Path $root 'tools\button-art') -Recurse -File)
$newest = ($inputs | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1).LastWriteTimeUtc
if ((Test-Path -LiteralPath $layout) -and (Get-Item -LiteralPath $layout).LastWriteTimeUtc -ge $newest) {
    Write-Host "Button icons: $icons (up to date)"
    exit 0
}
$python = Get-Command python, py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not (Get-Command magick -CommandType Application -ErrorAction SilentlyContinue)) {
    # ImageMagick's installer doesn't always put itself on PATH.
    $im = Get-ChildItem "$env:ProgramFiles\ImageMagick-*" -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
    if ($im) { $env:PATH = "$($im.FullName);$env:PATH" }
}
if (-not $python -or -not (Get-Command magick -CommandType Application -ErrorAction SilentlyContinue)) {
    Fail "button icons need Python and ImageMagick (magick) on PATH: $icons not updated"
    exit 0
}
if (-not (Test-Path -LiteralPath $packSource)) { Fail "button icons need texture_pack\ScoobyHD: $icons not updated"; exit 0 }
Remove-Item -Recurse -Force $icons -ErrorAction SilentlyContinue
& $python.Source $tool --out $icons | Out-Null
if ($LASTEXITCODE -ne 0) { throw "make-button-icons.py failed" }
Write-Host "Button icons: $icons (rebuilt)"
